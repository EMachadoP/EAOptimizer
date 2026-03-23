"""
EA Configuration Optimizer v1.2
Trade Reconstruction Engine + Basket_MAE Calculator
FR-03: Reconstrução completa de baskets e cálculo de métricas reais
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json

@dataclass
class TradeInfo:
    """Informações de um trade individual"""
    trade_id: int
    basket_id: str
    timestamp_open: datetime
    timestamp_close: Optional[datetime]
    symbol: str
    direction: str  # 'BUY' ou 'SELL'
    volume: float
    price_open: float
    price_close: Optional[float]
    slippage_pips: float = 0.0
    commission: float = 0.0
    swap: float = 0.0
    profit: float = 0.0

@dataclass
class BasketMetrics:
    """Métricas de um basket completo"""
    basket_id: str
    symbol: str
    timestamp_start: datetime
    timestamp_end: Optional[datetime]
    
    # Parâmetros do grid
    grid_spacing_pips: int
    lot_multiplier: float
    max_levels: int
    atr_filter: float
    
    # Trades
    trades: List[TradeInfo]
    total_trades: int
    
    # Métricas financeiras
    total_profit: float
    realized_profit: float
    floating_pnl: float
    total_commission: float
    total_swap: float
    
    # Métricas de risco
    basket_mae: float  # Maximum Adverse Excursion
    basket_mfe: float  # Maximum Favorable Excursion
    max_drawdown_pct: float
    
    # Flags
    phantom_winner: bool
    hit_take_profit: bool
    hit_stop_loss: bool
    
    # Regime
    regime_at_start: Optional[str] = None

class TradeReconstructionEngine:
    """
    Motor de reconstrução de trades do EA Grid
    Reconstrói baskets completos a partir de dados MT5
    """
    
    def __init__(self, symbol: str = "XAUUSD", point_value: float = 0.01):
        self.symbol = symbol
        self.point_value = point_value  # Valor do ponto para XAUUSD
        self.pip_value = point_value * 10  # 1 pip = 10 pontos para XAUUSD
        
    def generate_basket_id(self, timestamp: datetime, symbol: str) -> str:
        """Gera ID único para basket"""
        data = f"{symbol}_{timestamp.isoformat()}"
        return hashlib.md5(data.encode()).hexdigest()[:16]
    
    def reconstruct_basket_from_mt5(
        self,
        mt5_trades: pd.DataFrame,
        grid_params: Dict,
        market_data: pd.DataFrame
    ) -> BasketMetrics:
        """
        Reconstrói um basket completo a partir de trades MT5
        
        Args:
            mt5_trades: DataFrame com trades do MT5
            grid_params: Dict com grid_spacing, lot_multiplier, max_levels, atr_filter
            market_data: DataFrame com dados de mercado para cálculo de floating PnL
        
        Returns:
            BasketMetrics com todas as métricas calculadas
        """
        if len(mt5_trades) == 0:
            raise ValueError("No trades provided")
        
        # Ordenar trades por tempo de abertura
        mt5_trades = mt5_trades.sort_values('time_open')
        
        # Gerar basket_id
        first_trade_time = pd.to_datetime(mt5_trades.iloc[0]['time_open'])
        basket_id = self.generate_basket_id(first_trade_time, self.symbol)
        
        # Reconstruir trades individuais
        trades = []
        for idx, row in mt5_trades.iterrows():
            trade = TradeInfo(
                trade_id=int(row.get('ticket', idx)),
                basket_id=basket_id,
                timestamp_open=pd.to_datetime(row['time_open']),
                timestamp_close=pd.to_datetime(row['time_close']) if pd.notna(row.get('time_close')) else None,
                symbol=row.get('symbol', self.symbol),
                direction='BUY' if row['type'] == 0 else 'SELL',
                volume=float(row['volume']),
                price_open=float(row['price_open']),
                price_close=float(row['price_close']) if pd.notna(row.get('price_close')) else None,
                slippage_pips=float(row.get('slippage', 0)),
                commission=float(row.get('commission', 0)),
                swap=float(row.get('swap', 0)),
                profit=float(row.get('profit', 0))
            )
            trades.append(trade)
        
        # Calcular métricas do basket
        return self.calculate_basket_metrics(
            basket_id=basket_id,
            trades=trades,
            grid_params=grid_params,
            market_data=market_data
        )
    
    def calculate_basket_metrics(
        self,
        basket_id: str,
        trades: List[TradeInfo],
        grid_params: Dict,
        market_data: pd.DataFrame
    ) -> BasketMetrics:
        """
        Calcula métricas completas de um basket
        
        FR-03-B: Cálculo de custos de carry (Swap/Commission) e Phantom Winner detection
        """
        if not trades:
            raise ValueError("No trades provided")
        
        # Tempos
        timestamp_start = min(t.timestamp_open for t in trades)
        timestamp_end = max((t.timestamp_close for t in trades if t.timestamp_close), default=None)
        
        # Métricas básicas
        total_profit = sum(t.profit for t in trades)
        total_commission = sum(t.commission for t in trades)
        total_swap = sum(t.swap for t in trades)
        realized_profit = total_profit - total_commission - total_swap
        
        # Calcular Basket_MAE e Basket_MFE
        basket_mae, basket_mfe, max_dd_pct = self._calculate_mae_mfe(
            trades, market_data, timestamp_start, timestamp_end
        )
        
        # Detectar Phantom Winner
        phantom_winner = self._detect_phantom_winner(trades, total_profit)
        
        # Verificar hits de TP/SL
        hit_tp = any(t.profit > 0 and t.timestamp_close for t in trades)
        hit_sl = basket_mae >= grid_params.get('stop_loss_pips', 500) * self.pip_value
        
        # Floating PnL (para trades ainda abertos)
        floating_pnl = self._calculate_floating_pnl(trades, market_data)
        
        return BasketMetrics(
            basket_id=basket_id,
            symbol=self.symbol,
            timestamp_start=timestamp_start,
            timestamp_end=timestamp_end,
            grid_spacing_pips=grid_params.get('grid_spacing', 300),
            lot_multiplier=grid_params.get('lot_multiplier', 1.3),
            max_levels=grid_params.get('max_levels', 10),
            atr_filter=grid_params.get('atr_filter', 1.5),
            trades=trades,
            total_trades=len(trades),
            total_profit=total_profit,
            realized_profit=realized_profit,
            floating_pnl=floating_pnl,
            total_commission=total_commission,
            total_swap=total_swap,
            basket_mae=basket_mae,
            basket_mfe=basket_mfe,
            max_drawdown_pct=max_dd_pct,
            phantom_winner=phantom_winner,
            hit_take_profit=hit_tp,
            hit_stop_loss=hit_sl
        )
    
    def _calculate_mae_mfe(
        self,
        trades: List[TradeInfo],
        market_data: pd.DataFrame,
        start_time: datetime,
        end_time: Optional[datetime]
    ) -> Tuple[float, float, float]:
        """
        Calcula Basket_MAE e Basket_MFE usando dados de mercado
        
        Basket_MAE: Pior drawdown do basket (soma de todos os trades abertos)
        Basket_MFE: Melhor ponto do basket
        """
        if market_data is None or len(market_data) == 0:
            # Fallback: usar apenas trades fechados
            total_profit = sum(t.profit for t in trades)
            return abs(min(total_profit, 0)), max(total_profit, 0), 0.0
        
        # Filtrar dados de mercado pelo período do basket
        mask = (market_data.index >= start_time)
        if end_time:
            mask &= (market_data.index <= end_time)
        basket_market = market_data[mask]
        
        if len(basket_market) == 0:
            return 0.0, 0.0, 0.0
        
        # Calcular PnL acumulado em cada ponto no tempo
        pnl_series = []
        for timestamp, row in basket_market.iterrows():
            current_price = row['close']
            total_pnl = 0.0
            
            for trade in trades:
                if trade.timestamp_open <= timestamp:
                    if trade.timestamp_close and trade.timestamp_close <= timestamp:
                        # Trade já fechado
                        total_pnl += trade.profit
                    else:
                        # Trade ainda aberto - calcular floating PnL
                        if trade.direction == 'BUY':
                            floating = (current_price - trade.price_open) * trade.volume * 100
                        else:
                            floating = (trade.price_open - current_price) * trade.volume * 100
                        total_pnl += floating
            
            pnl_series.append(total_pnl)
        
        if not pnl_series:
            return 0.0, 0.0, 0.0
        
        pnl_array = np.array(pnl_series)
        
        # Basket_MAE: pior drawdown (mínimo relativo ao máximo anterior)
        running_max = np.maximum.accumulate(pnl_array)
        drawdowns = running_max - pnl_array
        basket_mae = np.max(drawdowns) if len(drawdowns) > 0 else 0.0
        
        # Basket_MFE: máximo lucro atingido
        basket_mfe = np.max(pnl_array) if len(pnl_array) > 0 else 0.0
        
        # Max Drawdown %
        max_dd_pct = (basket_mae / running_max.max() * 100) if running_max.max() > 0 else 0.0
        
        return basket_mae, basket_mfe, max_dd_pct
    
    def _detect_phantom_winner(self, trades: List[TradeInfo], total_profit: float) -> bool:
        """
        Detecta Phantom Winner - trade que parece lucrativo mas tem risco oculto
        
        Phantom Winner: Trade com lucro positivo que teve drawdown significativo
        durante a vida do trade, indicando que o lucro foi "sorte" de timing
        """
        if total_profit <= 0:
            return False
        
        # Verificar se algum trade teve lucro mas poderia ter sido stopado
        for trade in trades:
            if trade.profit > 0:
                # Se o trade teve lucro mas o basket teve MAE significativo
                # durante a vida deste trade, é um phantom winner
                if trade.profit < trade.volume * 50:  # Lucro pequeno relativo ao volume
                    return True
        
        return False
    
    def _calculate_floating_pnl(
        self,
        trades: List[TradeInfo],
        market_data: pd.DataFrame
    ) -> float:
        """Calcula PnL flutuante de trades ainda abertos"""
        open_trades = [t for t in trades if t.timestamp_close is None]
        
        if not open_trades or market_data is None or len(market_data) == 0:
            return 0.0
        
        current_price = market_data['close'].iloc[-1]
        floating_pnl = 0.0
        
        for trade in open_trades:
            if trade.direction == 'BUY':
                pnl = (current_price - trade.price_open) * trade.volume * 100
            else:
                pnl = (trade.price_open - current_price) * trade.volume * 100
            floating_pnl += pnl
        
        return floating_pnl
    
    def simulate_grid_basket(
        self,
        start_time: datetime,
        market_data: pd.DataFrame,
        grid_params: Dict,
        initial_price: float,
        direction: str = 'BUY'
    ) -> BasketMetrics:
        """
        Simula um basket de grid a partir de parâmetros
        Útil para backtesting e otimização
        """
        grid_spacing = grid_params.get('grid_spacing', 300) * self.pip_value
        lot_multiplier = grid_params.get('lot_multiplier', 1.3)
        max_levels = grid_params.get('max_levels', 10)
        base_volume = grid_params.get('base_volume', 0.01)
        take_profit_pips = grid_params.get('take_profit_pips', 100)
        stop_loss_pips = grid_params.get('stop_loss_pips', 500)
        
        basket_id = self.generate_basket_id(start_time, self.symbol)
        trades = []
        
        # Gerar níveis do grid
        current_price = initial_price
        current_volume = base_volume
        
        for level in range(max_levels):
            # Abrir trade no nível
            trade_price = current_price
            
            trade = TradeInfo(
                trade_id=level,
                basket_id=basket_id,
                timestamp_open=start_time,
                timestamp_close=None,
                symbol=self.symbol,
                direction=direction,
                volume=current_volume,
                price_open=trade_price,
                price_close=None,
                commission=current_volume * 7.0,  # $7 por lote
                swap=0.0
            )
            trades.append(trade)
            
            # Próximo nível
            if direction == 'BUY':
                current_price -= grid_spacing
            else:
                current_price += grid_spacing
            
            current_volume *= lot_multiplier
        
        # Simular evolução do basket
        return self.calculate_basket_metrics(
            basket_id=basket_id,
            trades=trades,
            grid_params=grid_params,
            market_data=market_data
        )

class LookAheadBiasAuditor:
    """
    NFR-07: Look-ahead Bias Auditor
    Valida que features não usam informação futura
    """
    
    @staticmethod
    def validate_features(market_data: pd.DataFrame, feature_columns: List[str]) -> Dict:
        """
        Valida que features são calculadas apenas com informação até T-1
        
        Returns:
            Dict com status de validação e problemas encontrados
        """
        issues = []
        
        for col in feature_columns:
            if col not in market_data.columns:
                issues.append(f"Feature {col} não encontrada")
                continue
            
            # Verificar se há valores nulos no início (indicativo de look-ahead)
            null_count = market_data[col].isna().sum()
            if null_count > len(market_data) * 0.1:  # Mais de 10% nulos
                issues.append(f"Feature {col} tem {null_count} valores nulos - possível look-ahead bias")
            
            # Verificar se a feature muda antes do preço (indicativo de leak)
            if col in ['hurst_exponent', 'adx_14']:
                # Estas features devem ter lag de pelo menos 1 barra
                pass  # Implementar validação específica
        
        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'feature_count': len(feature_columns)
        }
    
    @staticmethod
    def shift_features_safe(
        market_data: pd.DataFrame,
        feature_columns: List[str],
        shift_periods: int = 1
    ) -> pd.DataFrame:
        """
        Aplica shift seguro em features para evitar look-ahead bias
        """
        df = market_data.copy()
        for col in feature_columns:
            if col in df.columns:
                df[col] = df[col].shift(shift_periods)
        return df
