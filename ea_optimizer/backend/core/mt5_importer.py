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
import re

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
            # Map numeric MT5 types and Portuguese values to canonical buy/sell
            _type_map = {
                "0": "buy", "1": "sell",
                "compra": "buy", "venda": "sell",
                "buy": "buy", "sell": "sell",
            }
            trades_df["type"] = trades_df["type"].map(_type_map).fillna(trades_df["type"])

        if "symbol" not in trades_df.columns:
            trades_df["symbol"] = fallback_symbol
        else:
            trades_df["symbol"] = trades_df["symbol"].fillna("").astype(str).str.strip()
            trades_df.loc[trades_df["symbol"] == "", "symbol"] = fallback_symbol

        required = ["ticket", "time_open", "type", "volume", "price_open", "profit"]
        for column in required:
            if column not in trades_df.columns:
                raise ValueError(f"Coluna obrigatória {column} não encontrada no CSV")

        total_before_filter = len(trades_df)
        print(f"[mt5_importer] Colunas detectadas: {list(trades_df.columns)}")
        print(f"[mt5_importer] Total de linhas antes do filtro: {total_before_filter}")
        print(f"[mt5_importer] Valores únicos em 'type': {trades_df['type'].unique().tolist()}")

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
        print(f"[mt5_importer] Trades válidos após filtro: {len(trades_df)} de {total_before_filter}")

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
        Importa relatório HTML do MT5 Strategy Tester.

        Usa pandas.read_html como motor principal (robusto para encoding,
        formatação numérica e detecção de tabelas).
        Suporta cabeçalhos em Inglês e Português.
        """
        from bs4 import BeautifulSoup

        # ---- 1. Ler o HTML com fallback de encoding ----
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except UnicodeDecodeError:
            with open(html_path, 'r', encoding='utf-16') as f:
                html_content = f.read()

        soup = BeautifulSoup(html_content, 'html.parser')

        # ---- 2. Tentar parser dedicado para relatórios reais do Strategy Tester ----
        result_df = self._extract_strategy_tester_transactions_table(soup, symbol)

        if len(result_df) > 0:
            print(f"[mt5_importer] Strategy Tester HTML: {len(result_df)} trades extraídos da seção 'Transações'")
            result_df["basket_id"] = self._build_basket_ids(result_df)

            output_columns = [
                "ticket", "basket_id", "time_open", "time_close",
                "symbol", "direction", "volume", "price_open",
                "price_close", "slippage_pips", "commission", "swap", "profit",
            ]
            result_df = result_df[[c for c in output_columns if c in result_df.columns]].rename(
                columns={
                    "time_open": "timestamp_open",
                    "time_close": "timestamp_close",
                }
            )

            self._save_trades(result_df)
            self._save_grid_sequences(result_df)
            metrics = self._extract_metrics_from_html(soup)

            return {
                'trades': result_df,
                'metrics': metrics,
                'total_trades': len(result_df)
            }

        # ---- 3. Extrair TODAS as tabelas via pandas como fallback ----
        try:
            all_dfs = pd.read_html(html_content, flavor='bs4')
        except Exception:
            try:
                all_dfs = pd.read_html(html_content)
            except Exception as e:
                raise ValueError(
                    f"Nenhuma tabela legível encontrada no HTML. "
                    f"Verifique se o arquivo é um relatório do Strategy Tester. Erro: {e}"
                )

        if not all_dfs:
            raise ValueError("Nenhuma tabela encontrada no relatório HTML.")

        # ---- 4. Identificar a tabela de deals/trades ----
        # Mapa de sinônimos: nome canônico -> possíveis variações (EN + PT)
        KNOWN_HEADERS = {
            "deal":       {"deal", "negócio", "negocio", "ticket", "#"},
            "time":       {"time", "hora", "tempo", "open time", "abertura"},
            "type":       {"type", "tipo"},
            "direction":  {"direction", "entry", "direção", "direcao", "entrada"},
            "volume":     {"volume", "lot", "lots", "lote", "lotes"},
            "price":      {"price", "preço", "preco"},
            "symbol":     {"symbol", "símbolo", "simbolo", "ativo"},
            "order":      {"order", "ordem"},
            "commission": {"commission", "comissão", "comissao", "fee", "taxa"},
            "swap":       {"swap"},
            "profit":     {"profit", "lucro", "resultado"},
            "balance":    {"balance", "saldo", "balanço", "balanco"},
        }

        # Conjunto plano de todas as keywords conhecidas
        all_keywords = set()
        for synonyms in KNOWN_HEADERS.values():
            all_keywords |= synonyms

        best_df = None
        best_score = 0

        for candidate in all_dfs:
            cols_lower = {str(c).strip().lower() for c in candidate.columns}
            score = len(cols_lower & all_keywords)
            if score > best_score and len(candidate) > 0:
                best_score = score
                best_df = candidate

        if best_df is None or best_score < 2:
            # Fallback: pegar a maior tabela como candidata
            best_df = max(all_dfs, key=len) if all_dfs else None

        if best_df is None or len(best_df) == 0:
            raise ValueError(
                "Tabela de trades/deals não encontrada no relatório HTML. "
                "Certifique-se de exportar o relatório pelo Strategy Tester do MT5."
            )

        # ---- 5. Normalizar nomes de colunas ----
        df = best_df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]

        def _find_col(canonical: str) -> str:
            """Retorna o nome real da coluna no df que corresponde ao canonical."""
            synonyms = KNOWN_HEADERS.get(canonical, set())
            for col in df.columns:
                if col in synonyms:
                    return col
            return ""

        col_deal = _find_col("deal")
        col_time = _find_col("time")
        col_type = _find_col("type")
        col_dir = _find_col("direction")
        col_vol = _find_col("volume")
        col_price = _find_col("price")
        col_commission = _find_col("commission")
        col_swap = _find_col("swap")
        col_profit = _find_col("profit")
        col_symbol = _find_col("symbol")

        # Identificar coluna de ticket/deal
        if not col_deal:
            # Tentar a primeira coluna numérica como ticket
            for c in df.columns:
                if pd.to_numeric(df[c], errors='coerce').notna().sum() > len(df) * 0.3:
                    col_deal = c
                    break

        # ---- 6. Montar DataFrame de trades ----
        trades_data = []

        for _, row in df.iterrows():
            # Ticket
            ticket_val = self._parse_mt5_number(row.get(col_deal)) if col_deal else np.nan
            if pd.isna(ticket_val) or ticket_val == 0:
                continue

            # Direção
            raw_type = str(row.get(col_type, "")).lower() if col_type else ""
            raw_dir = str(row.get(col_dir, "")).lower() if col_dir else ""
            combined = f"{raw_type} {raw_dir}"

            if "buy" in combined or "compra" in combined:
                direction = "BUY"
            elif "sell" in combined or "venda" in combined:
                direction = "SELL"
            else:
                continue  # pular balanço/depósito/saque

            # Tempo
            raw_time = row.get(col_time) if col_time else None
            try:
                time_open = pd.to_datetime(raw_time, errors='coerce')
            except Exception:
                time_open = pd.NaT
            if pd.isna(time_open):
                continue

            # Buscar segundo tempo (close) se existir coluna duplicada
            time_close = time_open
            for c in df.columns:
                if c != col_time and any(kw in c for kw in ["time", "hora", "tempo"]):
                    try:
                        tc = pd.to_datetime(row.get(c), errors='coerce')
                        if not pd.isna(tc):
                            time_close = tc
                    except Exception:
                        pass
                    break

            # Numéricos
            volume = self._parse_mt5_number(row.get(col_vol)) if col_vol else 0.01
            price_open = self._parse_mt5_number(row.get(col_price)) if col_price else 0.0

            # Buscar segundo preço (close) se existir coluna duplicada
            price_close = price_open
            for c in df.columns:
                if c != col_price and any(kw in c for kw in ["price", "preço", "preco"]):
                    val = self._parse_mt5_number(row.get(c))
                    if not pd.isna(val):
                        price_close = val
                    break

            commission = self._parse_mt5_number(row.get(col_commission)) if col_commission else 0.0
            swap_val = self._parse_mt5_number(row.get(col_swap)) if col_swap else 0.0
            profit_val = self._parse_mt5_number(row.get(col_profit)) if col_profit else 0.0
            deal_symbol = str(row.get(col_symbol, "")).strip() if col_symbol else ""

            trade = {
                'ticket': int(ticket_val),
                'time_open': time_open,
                'time_close': time_close if not pd.isna(time_close) else time_open,
                'direction': direction,
                'volume': volume if not pd.isna(volume) else 0.01,
                'price_open': price_open if not pd.isna(price_open) else 0.0,
                'price_close': price_close if not pd.isna(price_close) else (price_open if not pd.isna(price_open) else 0.0),
                'commission': commission if not pd.isna(commission) else 0.0,
                'swap': swap_val if not pd.isna(swap_val) else 0.0,
                'profit': profit_val if not pd.isna(profit_val) else 0.0,
                'symbol': deal_symbol if deal_symbol else symbol,
                'slippage_pips': 0.0,
            }
            trades_data.append(trade)

        result_df = pd.DataFrame(trades_data)

        print(f"[mt5_importer] HTML report: {len(result_df)} trades extraídos de {len(df)} linhas")
        print(f"[mt5_importer] Colunas da tabela HTML: {list(df.columns)}")

        if len(result_df) == 0:
            col_info = ', '.join(df.columns[:10])
            raise ValueError(
                f"Nenhum trade válido encontrado no relatório HTML. "
                f"Tabela detectada com {len(df)} linhas e colunas: [{col_info}]. "
                f"Verifique se o arquivo é um relatório do Strategy Tester com trades fechados."
            )

        result_df["basket_id"] = self._build_basket_ids(result_df)

        output_columns = [
            "ticket", "basket_id", "time_open", "time_close",
            "symbol", "direction", "volume", "price_open",
            "price_close", "slippage_pips", "commission", "swap", "profit",
        ]
        result_df = result_df[[c for c in output_columns if c in result_df.columns]].rename(
            columns={
                "time_open": "timestamp_open",
                "time_close": "timestamp_close",
            }
        )

        self._save_trades(result_df)
        self._save_grid_sequences(result_df)

        # Extrair métricas do relatório (usa BeautifulSoup)
        metrics = self._extract_metrics_from_html(soup)

        return {
            'trades': result_df,
            'metrics': metrics,
            'total_trades': len(result_df)
        }

    def _extract_strategy_tester_transactions_table(self, soup, fallback_symbol: str) -> pd.DataFrame:
        """Extrai trades da seção 'Transações' do relatório HTML do Strategy Tester do MT5."""
        tables = soup.find_all("table")
        transaction_table = None

        for table in tables:
            headings = table.find_all("th")
            if any(
                "transacoes" in self._normalize_html_label(heading.get_text(" ", strip=True))
                for heading in headings
            ):
                transaction_table = table
                break

        if transaction_table is None:
            return pd.DataFrame()

        rows = transaction_table.find_all("tr")
        header_index = None
        headers: List[str] = []

        for index, row in enumerate(rows):
            cells = row.find_all(["td", "th"])
            labels = [self._normalize_html_label(cell.get_text(" ", strip=True)) for cell in cells]
            if "horario" in labels and "lucro" in labels and "direcao" in labels:
                header_index = index
                headers = labels
                break

        if header_index is None:
            return pd.DataFrame()

        trades_data = []
        open_positions: Dict[Tuple[str, str], List[Dict]] = {}

        for row in rows[header_index + 1:]:
            cells = row.find_all("td")
            if len(cells) != len(headers):
                continue

            raw_row = {
                header: cell.get_text(" ", strip=True)
                for header, cell in zip(headers, cells)
            }

            row_type = self._normalize_html_label(raw_row.get("tipo", ""))
            direction = self._normalize_html_label(raw_row.get("direcao", ""))

            if row_type == "balance":
                continue
            if direction not in {"in", "out"}:
                continue

            symbol = raw_row.get("ativo", "").strip() or fallback_symbol
            raw_side = raw_row.get("tipo", "").strip().upper()
            if raw_side not in {"BUY", "SELL"}:
                continue

            # In MT5 Strategy Tester reports, `out` rows are the closing deal and
            # the displayed side is the opposite of the original position.
            side = raw_side if direction == "in" else ("SELL" if raw_side == "BUY" else "BUY")
            volume = self._parse_mt5_number(raw_row.get("volume"))
            price = self._parse_mt5_number(raw_row.get("preco"))
            ticket = self._parse_mt5_number(raw_row.get("ordem") or raw_row.get("oferta"))
            commission = self._parse_mt5_number(raw_row.get("comissao"))
            swap_val = self._parse_mt5_number(raw_row.get("swap"))
            profit = self._parse_mt5_number(raw_row.get("lucro"))
            timestamp = pd.to_datetime(raw_row.get("horario"), errors="coerce")
            comment = raw_row.get("comentario", "").strip()

            if pd.isna(timestamp) or pd.isna(volume) or pd.isna(price):
                continue

            trade_key = (symbol, side)

            if direction == "in":
                open_positions.setdefault(trade_key, []).append({
                    "time_open": timestamp,
                    "price_open": 0.0 if pd.isna(price) else float(price),
                    "volume": 0.01 if pd.isna(volume) else float(volume),
                    "comment": comment,
                    "ticket": int(ticket) if not pd.isna(ticket) else None,
                })
                continue

            # direction == out
            matched_open = None
            if trade_key in open_positions and open_positions[trade_key]:
                matched_open = open_positions[trade_key].pop(0)

            time_open = matched_open["time_open"] if matched_open else timestamp
            price_open = matched_open["price_open"] if matched_open else float(price)
            open_ticket = matched_open["ticket"] if matched_open else None
            open_comment = matched_open["comment"] if matched_open else ""

            trades_data.append({
                "ticket": int(ticket) if not pd.isna(ticket) else (open_ticket or 0),
                "time_open": time_open,
                "time_close": timestamp,
                "direction": side,
                "volume": float(volume),
                "price_open": float(price_open),
                "price_close": float(price),
                "commission": 0.0 if pd.isna(commission) else float(commission),
                "swap": 0.0 if pd.isna(swap_val) else float(swap_val),
                "profit": 0.0 if pd.isna(profit) else float(profit),
                "symbol": symbol,
                "slippage_pips": 0.0,
                "comment": open_comment or comment,
            })

        return pd.DataFrame(trades_data)

    def _normalize_html_label(self, text: str) -> str:
        """Normaliza cabeçalhos/labels do HTML do MT5 para comparação."""
        normalized = (text or "").strip().lower()
        replacements = {
            "á": "a",
            "à": "a",
            "ã": "a",
            "â": "a",
            "é": "e",
            "ê": "e",
            "í": "i",
            "ó": "o",
            "ô": "o",
            "õ": "o",
            "ú": "u",
            "ç": "c",
            "/": " ",
        }
        for source, target in replacements.items():
            normalized = normalized.replace(source, target)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.replace(" ", "")
    
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
