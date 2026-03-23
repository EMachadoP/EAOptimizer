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
        
        Espera colunas: ticket, time_open, time_close, type, volume, 
                       price_open, price_close, commission, swap, profit
        """
        df = pd.read_csv(csv_path)
        
        # Normalizar nomes de colunas
        df.columns = [col.lower().strip() for col in df.columns]
        
        # Converter timestamps
        df['time_open'] = pd.to_datetime(df['time_open'])
        if 'time_close' in df.columns:
            df['time_close'] = pd.to_datetime(df['time_close'])
        
        # Adicionar symbol
        df['symbol'] = symbol
        
        # Calcular slippage se não existir
        if 'slippage' not in df.columns:
            df['slippage'] = 0.0
        
        # Garantir colunas necessárias
        required_cols = ['ticket', 'time_open', 'type', 'volume', 'price_open', 'profit']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Coluna obrigatória {col} não encontrada no CSV")
        
        # Salvar no banco
        self._save_trades(df)
        
        return df
    
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
        
        with open(html_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
        
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
        if not mt5.initialize(mt5_path):
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
        
        df.to_sql('trades', self.connection, if_exists='append', index=False)
        print(f"Salvos {len(df)} trades")
    
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
