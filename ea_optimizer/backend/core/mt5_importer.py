"""
EA Configuration Optimizer v1.2
MT5 Data Importer
FR-01/02: Pipeline de importação MT5 (Ticks + Trades)

Importa dados do MetaTrader 5:
- Dados de mercado (OHLCV)
- Histórico de trades
- Informações de conta
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import sqlite3
import json
import hashlib
import csv

@dataclass
class MT5Config:
    """Configuração de conexão MT5"""
    account: int
    password: str
    server: str
    symbol: str = "XAUUSD"
    timeframe: str = "H1"

class MT5DataImporter:
    """
    Importador de dados do MetaTrader 5
    
    FR-01: Importação de ticks/dados de mercado
    FR-02: Importação de histórico de trades
    """
    
    def __init__(self, db_path: str = "ea_optimizer.db"):
        self.db_path = db_path
        self.connection = None
    
    def connect(self):
        """Conecta ao banco de dados"""
        self.connection = sqlite3.connect(self.db_path)
        return self
    
    def disconnect(self):
        """Desconecta do banco de dados"""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def import_market_data_from_csv(
        self,
        csv_path: str,
        symbol: str = "XAUUSD",
        timeframe: str = "H1"
    ) -> pd.DataFrame:
        """
        Importa dados de mercado de arquivo CSV
        
        Espera colunas: time, open, high, low, close, volume
        """
        df = pd.read_csv(csv_path)
        
        # Normalizar nomes de colunas
        df.columns = [col.lower().strip() for col in df.columns]
        
        # Converter timestamp
        if 'time' in df.columns:
            df['timestamp'] = pd.to_datetime(df['time'])
        elif 'datetime' in df.columns:
            df['timestamp'] = pd.to_datetime(df['datetime'])
        
        # Adicionar symbol
        df['symbol'] = symbol
        
        # Selecionar e renomear colunas
        column_mapping = {
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume'
        }
        
        for old_col, new_col in column_mapping.items():
            if old_col not in df.columns:
                raise ValueError(f"Coluna {old_col} não encontrada no CSV")
        
        df = df[['timestamp', 'symbol', 'open', 'high', 'low', 'close', 'volume']]
        
        # Salvar no banco
        self._save_market_data(df)
        
        return df
    
    def import_trades_from_csv(
        self,
        csv_path: str,
        symbol: str = "XAUUSD"
    ) -> pd.DataFrame:
        """
        Importa histórico de trades de arquivo CSV
        
        Aceita:
        - CSV limpo com colunas ticket/time_open/time_close/type/...
        - Export híbrido do histórico MT5 com colunas como
          Position/Time/Time.1/Price/Price.1 e linhas extras de deals
        """
        raw_df = self._read_trade_csv(csv_path)
        df = self._normalize_trades_dataframe(raw_df, symbol)

        if len(df) == 0:
            raise ValueError(
                "Nenhum trade fechado válido encontrado no arquivo. "
                "Verifique se o CSV exportado contém histórico fechado do MT5."
            )

        self._save_trades(df)
        self._save_grid_sequences(df)

        return df

    def _read_trade_csv(self, csv_path: str) -> pd.DataFrame:
        """Lê CSV de trades tentando preservar o formato bruto do MT5."""
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            try:
                delimiter = csv.Sniffer().sniff(sample, delimiters=";,").delimiter
            except csv.Error:
                delimiter = ";"

        return pd.read_csv(csv_path, sep=delimiter, dtype=str, encoding="utf-8-sig")

    def _normalize_trades_dataframe(
        self,
        df: pd.DataFrame,
        fallback_symbol: str
    ) -> pd.DataFrame:
        """Converte diferentes layouts de CSV do MT5 para o schema interno."""
        trades_df = df.copy()
        trades_df.columns = [col.strip() for col in trades_df.columns]
        column_mapping = {
            "Position": "ticket",
            "Ticket": "ticket",
            "Time": "time_open",
            "Time.1": "time_close",
            "Open Time": "time_open",
            "Close Time": "time_close",
            "Price": "price_open",
            "Price.1": "price_close",
            "Open Price": "price_open",
            "Close Price": "price_close",
            "S / L": "sl",
            "T / P": "tp",
            "Type": "type",
            "Volume": "volume",
            "Profit": "profit",
            "Commission": "commission",
            "Swap": "swap",
            "Symbol": "symbol",
            "Slippage": "slippage",
        }
        trades_df = trades_df.rename(columns=column_mapping)
        trades_df.columns = [col.lower().strip() for col in trades_df.columns]

        for column in ["time_open", "time_close"]:
            if column in trades_df.columns:
                trades_df[column] = pd.to_datetime(trades_df[column], errors="coerce")

        numeric_columns = [
            "ticket",
            "volume",
            "price_open",
            "price_close",
            "sl",
            "tp",
            "profit",
            "commission",
            "swap",
            "slippage",
        ]
        for column in numeric_columns:
            if column in trades_df.columns:
                trades_df[column] = trades_df[column].apply(self._parse_mt5_number)

        if "type" in trades_df.columns:
            trades_df["type"] = trades_df["type"].astype(str).str.strip().str.lower()

        if "symbol" not in trades_df.columns:
            trades_df["symbol"] = fallback_symbol
        else:
            trades_df["symbol"] = trades_df["symbol"].fillna("").astype(str).str.strip()
            trades_df.loc[trades_df["symbol"] == "", "symbol"] = fallback_symbol

        required = ["ticket", "time_open", "type", "volume", "price_open", "profit"]
        for column in required:
            if column not in trades_df.columns:
                raise ValueError(f"Coluna obrigatória {column} não encontrada no CSV")

        closed_mask = (
            trades_df["ticket"].notna()
            & trades_df["time_open"].notna()
            & trades_df["type"].isin(["buy", "sell"])
            & trades_df["volume"].notna()
            & trades_df["time_close"].notna()
            & trades_df["price_open"].notna()
            & trades_df["price_close"].notna()
        )
        trades_df = trades_df.loc[closed_mask].copy()

        if len(trades_df) == 0:
            return pd.DataFrame()

        trades_df["ticket"] = trades_df["ticket"].astype(int)
        trades_df["direction"] = trades_df["type"].str.upper()
        for column in ["commission", "swap", "slippage"]:
            if column not in trades_df.columns:
                trades_df[column] = 0.0
            trades_df[column] = trades_df[column].fillna(0.0)
        trades_df["basket_id"] = self._build_basket_ids(trades_df)
        trades_df = trades_df.drop_duplicates(
            subset=["ticket", "time_open", "time_close", "direction", "volume", "price_open", "price_close"]
        )

        output_columns = [
            "ticket",
            "basket_id",
            "time_open",
            "time_close",
            "symbol",
            "direction",
            "volume",
            "price_open",
            "price_close",
            "slippage",
            "commission",
            "swap",
            "profit",
        ]
        return trades_df[output_columns].rename(
            columns={
                "time_open": "timestamp_open",
                "time_close": "timestamp_close",
                "slippage": "slippage_pips",
            }
        )

    def _parse_mt5_number(self, value):
        """Converte números do MT5 com espaço milhar e vírgula decimal."""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return np.nan

        text = str(value).strip().replace("\xa0", " ")
        if not text:
            return np.nan

        if "," in text:
            text = text.replace(" ", "").replace(".", "").replace(",", ".")
        else:
            text = text.replace(" ", "")

        try:
            return float(text)
        except ValueError:
            return np.nan

    def _build_basket_ids(self, trades_df: pd.DataFrame) -> pd.Series:
        """
        Agrupa trades fechados em baskets usando símbolo, direção e segundo de fechamento.
        Isso captura bem grids fechados em bloco no histórico exportado do MT5.
        """
        basket_keys = trades_df.apply(
            lambda row: (
                f"{row['symbol']}|{row['direction']}|"
                f"{row['time_close'].strftime('%Y-%m-%d %H:%M:%S')}"
            ),
            axis=1,
        )
        return basket_keys.apply(lambda key: hashlib.md5(key.encode()).hexdigest()[:32])
    
    def import_mt5_report(
        self,
        html_path: str,
        symbol: str = "XAUUSD"
    ) -> Dict:
        """
        Importa relatório HTML do MT5 Strategy Tester
        
        Extrai trades e métricas do relatório HTML
        """
        from bs4 import BeautifulSoup
        
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except UnicodeDecodeError:
            with open(html_path, 'r', encoding='utf-16') as f:
                html_content = f.read()
                
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extrair tabela de trades
        trades_table = soup.find('table', {'class': 'trades'})
        
        if trades_table is None:
            # Tentar encontrar qualquer tabela
            tables = soup.find_all('table')
            for table in tables:
                if 'order' in table.get_text().lower() or 'trade' in table.get_text().lower():
                    trades_table = table
                    break
        
        if trades_table is None:
            raise ValueError("Tabela de trades não encontrada no relatório")
        
        # Parse trades
        trades_data = []
        rows = trades_table.find_all('tr')[1:]  # Pular header
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 10:
                continue
            
            try:
                trade = {
                    'ticket': int(cells[0].get_text().strip()),
                    'time_open': pd.to_datetime(cells[1].get_text().strip()),
                    'type': 0 if 'buy' in cells[2].get_text().lower() else 1,
                    'volume': float(cells[3].get_text().strip()),
                    'price_open': float(cells[4].get_text().strip()),
                    'sl': float(cells[5].get_text().strip()) if cells[5].get_text().strip() else 0,
                    'tp': float(cells[6].get_text().strip()) if cells[6].get_text().strip() else 0,
                    'time_close': pd.to_datetime(cells[7].get_text().strip()),
                    'price_close': float(cells[8].get_text().strip()),
                    'commission': float(cells[9].get_text().strip()) if len(cells) > 9 else 0,
                    'swap': float(cells[10].get_text().strip()) if len(cells) > 10 else 0,
                    'profit': float(cells[11].get_text().strip()) if len(cells) > 11 else 0,
                    'symbol': symbol
                }
                trades_data.append(trade)
            except Exception as e:
                print(f"Erro ao parsear trade: {e}")
                continue
        
        df = pd.DataFrame(trades_data)
        
        if len(df) > 0:
            df["ticket"] = df["ticket"].astype(int)
            df["direction"] = np.where(df["type"] == 0, "BUY", "SELL")
            df["slippage"] = 0.0
            
            df["basket_id"] = self._build_basket_ids(df)
            
            output_columns = [
                "ticket",
                "basket_id",
                "time_open",
                "time_close",
                "symbol",
                "direction",
                "volume",
                "price_open",
                "price_close",
                "slippage",
                "commission",
                "swap",
                "profit",
            ]
            df = df[output_columns].rename(
                columns={
                    "time_open": "timestamp_open",
                    "time_close": "timestamp_close",
                    "slippage": "slippage_pips",
                }
            )
            
            # Salvar no banco
            self._save_trades(df)
        
        # Extrair métricas do relatório
        metrics = self._extract_metrics_from_html(soup)
        
        return {
            'trades': df,
            'metrics': metrics,
            'total_trades': len(df)
        }
    
    def import_from_mt5_terminal(
        self,
        mt5_path: Optional[str] = None,
        symbol: str = "XAUUSD",
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict:
        """
        Importa dados diretamente do terminal MT5 (requer MetaTrader5 Python)
        
        Args:
            mt5_path: Caminho para o terminal MT5
            symbol: Símbolo
            date_from: Data inicial
            date_to: Data final
        """
        try:
            import MetaTrader5 as mt5
        except ImportError:
            raise ImportError("MetaTrader5 Python não instalado. Use: pip install MetaTrader5")
        
        # Inicializar MT5
        initialized = mt5.initialize(path=mt5_path) if mt5_path else mt5.initialize()
        if not initialized:
            raise ConnectionError("Falha ao inicializar MT5")
        
        # Definir datas padrão
        if date_to is None:
            date_to = datetime.now()
        if date_from is None:
            date_from = date_to - timedelta(days=180)
        
        # Importar dados de mercado
        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, date_from, date_to)
        
        if rates is None or len(rates) == 0:
            mt5.shutdown()
            raise ValueError(f"Nenhum dado encontrado para {symbol}")
        
        df_rates = pd.DataFrame(rates)
        df_rates['timestamp'] = pd.to_datetime(df_rates['time'], unit='s')
        df_rates['symbol'] = symbol
        df_rates = df_rates.rename(columns={
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'tick_volume': 'volume'
        })
        
        df_rates = df_rates[['timestamp', 'symbol', 'open', 'high', 'low', 'close', 'volume']]
        
        # Importar histórico de trades
        deals = mt5.history_deals_get(date_from, date_to)
        
        trades_data = []
        if deals:
            for deal in deals:
                trade = {
                    'ticket': deal.ticket,
                    'time_open': pd.to_datetime(deal.time, unit='s'),
                    'time_close': pd.to_datetime(deal.time, unit='s'),
                    'type': deal.type,
                    'volume': deal.volume,
                    'price_open': deal.price,
                    'price_close': deal.price,
                    'commission': deal.commission,
                    'swap': deal.swap,
                    'profit': deal.profit,
                    'symbol': deal.symbol
                }
                trades_data.append(trade)
        
        df_trades = pd.DataFrame(trades_data) if trades_data else pd.DataFrame()
        
        # Salvar no banco
        self._save_market_data(df_rates)
        if len(df_trades) > 0:
            self._save_trades(df_trades)
        
        mt5.shutdown()
        
        return {
            'market_data': df_rates,
            'trades': df_trades,
            'period': (date_from, date_to)
        }
    
    def _save_market_data(self, df: pd.DataFrame):
        """Salva dados de mercado no banco"""
        if self.connection is None:
            self.connect()
        
        df.to_sql('market_data', self.connection, if_exists='append', index=False)
        print(f"Salvos {len(df)} registros de market_data")
    
    def _save_trades(self, df: pd.DataFrame):
        """Salva trades no banco"""
        if self.connection is None:
            self.connect()

        trades_df = df.copy()
        trades_df.columns = [col.lower().strip() for col in trades_df.columns]

        if 'time_open' in trades_df.columns and 'timestamp_open' not in trades_df.columns:
            trades_df['timestamp_open'] = pd.to_datetime(trades_df['time_open'])
        if 'time_close' in trades_df.columns and 'timestamp_close' not in trades_df.columns:
            trades_df['timestamp_close'] = pd.to_datetime(trades_df['time_close'])

        if 'type' in trades_df.columns and 'direction' not in trades_df.columns:
            trades_df['direction'] = trades_df['type'].apply(
                lambda value: 'BUY' if str(value).lower() in {'0', 'buy'} else 'SELL'
            )

        if 'slippage' in trades_df.columns and 'slippage_pips' not in trades_df.columns:
            trades_df['slippage_pips'] = trades_df['slippage']

        if 'ticket' in trades_df.columns and 'basket_id' not in trades_df.columns:
            trades_df['basket_id'] = trades_df['ticket'].astype(str).apply(
                lambda ticket: hashlib.md5(ticket.encode()).hexdigest()[:32]
            )

        if 'symbol' not in trades_df.columns:
            trades_df['symbol'] = 'XAUUSD'

        if 'commission' not in trades_df.columns:
            trades_df['commission'] = 0.0
        if 'swap' not in trades_df.columns:
            trades_df['swap'] = 0.0
        if 'price_close' not in trades_df.columns:
            trades_df['price_close'] = trades_df.get('price_open')
        if 'timestamp_close' not in trades_df.columns:
            trades_df['timestamp_close'] = trades_df.get('timestamp_open')
        if 'slippage_pips' not in trades_df.columns:
            trades_df['slippage_pips'] = 0.0

        required_columns = [
            'basket_id',
            'timestamp_open',
            'timestamp_close',
            'symbol',
            'direction',
            'volume',
            'price_open',
            'price_close',
            'slippage_pips',
            'commission',
            'swap',
            'profit',
        ]

        for column in required_columns:
            if column not in trades_df.columns:
                raise ValueError(f"Coluna obrigatória ausente para salvar trades: {column}")

        trades_df = trades_df[required_columns]
        trades_df = trades_df.drop_duplicates()
        trades_df.to_sql('trades', self.connection, if_exists='append', index=False)
        print(f"Salvos {len(trades_df)} trades")

    def _save_grid_sequences(self, trades_df: pd.DataFrame):
        """Salva baskets heurísticos a partir de trades fechados importados."""
        if self.connection is None:
            self.connect()

        df = trades_df.copy()
        if "timestamp_open" not in df.columns or "timestamp_close" not in df.columns:
            raise ValueError("Trades precisam conter timestamp_open e timestamp_close para gerar baskets")

        grouped = (
            df.groupby("basket_id")
            .agg(
                symbol=("symbol", "first"),
                timestamp_start=("timestamp_open", "min"),
                timestamp_end=("timestamp_close", "max"),
                total_trades=("ticket", "count"),
                total_profit=("profit", "sum"),
                realized_profit=("profit", "sum"),
                floating_pnl=("profit", lambda _: 0.0),
                total_commission=("commission", "sum"),
                total_swap=("swap", "sum"),
                basket_mae=("profit", lambda series: abs(min(series.sum(), 0.0))),
                basket_mfe=("profit", lambda series: max(series.sum(), 0.0)),
                max_levels=("ticket", "count"),
                lot_multiplier=("volume", self._estimate_lot_multiplier),
                grid_spacing_pips=("price_open", self._estimate_grid_spacing_pips),
                hit_take_profit=("profit", lambda series: bool((series > 0).any())),
                hit_stop_loss=("profit", lambda series: series.sum() < 0),
            )
            .reset_index()
        )

        grouped["atr_filter"] = 1.5
        grouped["phantom_winner"] = (
            (grouped["total_profit"] > 0)
            & (grouped["total_trades"] > 1)
            & (grouped["basket_mfe"] > 0)
            & (grouped["total_profit"] < grouped["basket_mfe"] * 0.25)
        )
        grouped["regime_at_start"] = None

        required_columns = [
            "basket_id",
            "symbol",
            "timestamp_start",
            "timestamp_end",
            "grid_spacing_pips",
            "lot_multiplier",
            "max_levels",
            "atr_filter",
            "total_trades",
            "total_profit",
            "basket_mae",
            "basket_mfe",
            "realized_profit",
            "floating_pnl",
            "total_commission",
            "total_swap",
            "phantom_winner",
            "hit_take_profit",
            "hit_stop_loss",
            "regime_at_start",
        ]

        cursor = self.connection.cursor()
        cursor.executemany(
            "DELETE FROM grid_sequences WHERE basket_id = ?",
            [(basket_id,) for basket_id in grouped["basket_id"].tolist()],
        )
        self.connection.commit()

        grouped[required_columns].to_sql("grid_sequences", self.connection, if_exists="append", index=False)
        print(f"Salvos {len(grouped)} baskets heurísticos")

    def _estimate_lot_multiplier(self, volumes: pd.Series) -> float:
        clean_volumes = [float(v) for v in volumes.dropna().tolist() if float(v) > 0]
        if len(clean_volumes) < 2:
            return 1.0

        ordered = sorted(clean_volumes)
        ratios = []
        for previous, current in zip(ordered, ordered[1:]):
            if previous > 0 and current >= previous:
                ratios.append(current / previous)

        if not ratios:
            return 1.0

        return round(float(np.median(ratios)), 2)

    def _estimate_grid_spacing_pips(self, open_prices: pd.Series) -> int:
        prices = sorted({float(price) for price in open_prices.dropna().tolist()})
        if len(prices) < 2:
            return 0

        deltas = [abs(current - previous) for previous, current in zip(prices, prices[1:]) if current != previous]
        if not deltas:
            return 0

        median_delta = float(np.median(deltas))
        return int(round(median_delta / 0.1))
    
    def _extract_metrics_from_html(self, soup) -> Dict:
        """Extrai métricas do relatório HTML"""
        metrics = {}
        
        # Procurar por valores em tabelas de resumo
        summary_tables = soup.find_all('table', {'class': 'summary'})
        
        for table in summary_tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) == 2:
                    key = cells[0].get_text().strip().lower().replace(' ', '_')
                    value = cells[1].get_text().strip()
                    
                    # Tentar converter para número
                    try:
                        value = float(value.replace(',', '').replace('%', ''))
                    except:
                        pass
                    
                    metrics[key] = value
        
        return metrics
    
    def validate_imported_data(
        self,
        symbol: str = "XAUUSD",
        min_bars: int = 1000,
        min_trades: int = 10
    ) -> Dict:
        """
        Valida dados importados
        
        Returns:
            Dict com status de validação
        """
        if self.connection is None:
            self.connect()
        
        validation = {
            'is_valid': True,
            'issues': []
        }
        
        # Verificar market_data
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM market_data WHERE symbol = ?",
            (symbol,)
        )
        n_bars = cursor.fetchone()[0]
        
        if n_bars < min_bars:
            validation['is_valid'] = False
            validation['issues'].append(
                f"Dados de mercado insuficientes: {n_bars} barras (mínimo: {min_bars})"
            )
        
        # Verificar trades
        cursor.execute(
            "SELECT COUNT(*) FROM trades WHERE symbol = ?",
            (symbol,)
        )
        n_trades = cursor.fetchone()[0]
        
        if n_trades < min_trades:
            validation['is_valid'] = False
            validation['issues'].append(
                f"Trades insuficientes: {n_trades} trades (mínimo: {min_trades})"
            )
        
        # Verificar gaps nos dados
        if n_bars > 0:
            cursor.execute(
                """SELECT timestamp FROM market_data 
                   WHERE symbol = ? ORDER BY timestamp""",
                (symbol,)
            )
            timestamps = [row[0] for row in cursor.fetchall()]
            
            # Verificar gaps maiores que 2 horas
            for i in range(1, len(timestamps)):
                gap = pd.to_datetime(timestamps[i]) - pd.to_datetime(timestamps[i-1])
                if gap > timedelta(hours=2):
                    validation['issues'].append(
                        f"Gap encontrado: {timestamps[i-1]} a {timestamps[i]}"
                    )
        
        validation['market_data_count'] = n_bars
        validation['trades_count'] = n_trades
        
        return validation

class DataPipeline:
    """
    Pipeline completo de processamento de dados
    """
    
    def __init__(self, db_path: str = "ea_optimizer.db"):
        self.importer = MT5DataImporter(db_path)
        self.db_path = db_path
    
    def run_full_pipeline(
        self,
        market_data_csv: Optional[str] = None,
        trades_csv: Optional[str] = None,
        symbol: str = "XAUUSD"
    ) -> Dict:
        """
        Executa pipeline completo de importação e processamento
        """
        results = {}
        
        # Importar dados de mercado
        if market_data_csv:
            print("Importando dados de mercado...")
            df_market = self.importer.import_market_data_from_csv(market_data_csv, symbol)
            results['market_data'] = len(df_market)
        
        # Importar trades
        if trades_csv:
            print("Importando trades...")
            df_trades = self.importer.import_trades_from_csv(trades_csv, symbol)
            results['trades'] = len(df_trades)
        
        # Validar
        print("Validando dados...")
        validation = self.importer.validate_imported_data(symbol)
        results['validation'] = validation
        
        self.importer.disconnect()
        
        return results
