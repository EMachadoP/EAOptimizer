"""
EA Configuration Optimizer v1.2
Slippage Modeling Module
FR-12/12-B: Slippage Modeling + Liquidity Impact

Modela slippage baseado em:
- Horário do dia (liquidez variável)
- Volume do trade
- Volatilidade de mercado
- Execução em cadeia (impacto cumulativo)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from scipy import stats

@dataclass
class SlippageEstimate:
    """Estimativa de slippage para um trade"""
    expected_slippage_pips: float
    slippage_std: float
    confidence_interval: Tuple[float, float]
    factors: Dict[str, float]

class SlippageModel:
    """
    Modelo de slippage realista para simulação
    
    FR-12: Slippage por horário e volume
    FR-12-B: Impacto de liquidez em execução em cadeia
    """
    
    def __init__(self, symbol: str = "XAUUSD"):
        self.symbol = symbol
        self.pip_value = 0.1 if symbol == "XAUUSD" else 0.0001
        
        # Parâmetros base de slippage por horário (em pips)
        self.base_slippage_by_hour = {
            0: 2.5,   # Asia open - baixa liquidez
            1: 2.0,
            2: 1.8,
            3: 1.5,
            4: 1.5,
            5: 1.8,
            6: 2.0,
            7: 2.5,   # London pre-open
            8: 3.0,   # London open - volatilidade
            9: 2.5,
            10: 2.0,
            11: 1.8,
            12: 1.5,  # NY pre-open
            13: 2.5,  # NY open
            14: 2.0,
            15: 1.8,
            16: 1.5,
            17: 1.8,
            18: 2.0,
            19: 2.2,
            20: 2.5,
            21: 2.8,
            22: 3.0,  # Asia overlap - volatilidade
            23: 2.8
        }
        
        # Multiplicadores de volume
        self.volume_multipliers = {
            'micro': 0.5,      # < 0.1 lot
            'small': 0.8,      # 0.1 - 0.5 lot
            'medium': 1.0,     # 0.5 - 2.0 lot
            'large': 1.5,      # 2.0 - 5.0 lot
            'institutional': 2.5  # > 5.0 lot
        }
    
    def estimate_slippage(
        self,
        volume: float,
        hour_of_day: int,
        atr_14: Optional[float] = None,
        is_chain_execution: bool = False,
        chain_position: int = 0
    ) -> SlippageEstimate:
        """
        Estima slippage para um trade
        
        Args:
            volume: Volume em lotes
            hour_of_day: Hora do dia (0-23)
            atr_14: ATR de 14 períodos (opcional)
            is_chain_execution: Se é parte de execução em cadeia
            chain_position: Posição na cadeia (0 = primeiro)
        
        Returns:
            SlippageEstimate
        """
        # Slippage base por horário
        base_slippage = self.base_slippage_by_hour.get(hour_of_day, 2.0)
        
        # Multiplicador de volume
        volume_bucket = self._classify_volume(volume)
        volume_mult = self.volume_multipliers[volume_bucket]
        
        # Multiplicador de volatilidade
        volatility_mult = 1.0
        if atr_14 is not None:
            # ATR alto = mais slippage
            if atr_14 > 2.0:
                volatility_mult = 1.5
            elif atr_14 > 1.5:
                volatility_mult = 1.2
            elif atr_14 < 0.5:
                volatility_mult = 0.8
        
        # Impacto de execução em cadeia
        chain_mult = 1.0
        if is_chain_execution:
            # Cada trade subsequente na cadeia tem mais slippage
            chain_mult = 1.0 + (chain_position * 0.1)
        
        # Slippage esperado
        expected_slippage = base_slippage * volume_mult * volatility_mult * chain_mult
        
        # Desvio padrão (incerteza)
        slippage_std = expected_slippage * 0.3  # 30% de variabilidade
        
        # Intervalo de confiança (95%)
        ci_lower = max(0, expected_slippage - 1.96 * slippage_std)
        ci_upper = expected_slippage + 1.96 * slippage_std
        
        return SlippageEstimate(
            expected_slippage_pips=round(expected_slippage, 2),
            slippage_std=round(slippage_std, 2),
            confidence_interval=(round(ci_lower, 2), round(ci_upper, 2)),
            factors={
                'base_slippage': base_slippage,
                'volume_multiplier': volume_mult,
                'volatility_multiplier': volatility_mult,
                'chain_multiplier': chain_mult
            }
        )
    
    def estimate_chain_slippage(
        self,
        volumes: List[float],
        hour_of_day: int,
        atr_14: Optional[float] = None
    ) -> List[SlippageEstimate]:
        """
        Estima slippage para execução em cadeia (vários níveis do grid)
        
        FR-12-B: Execução em cadeia com impacto cumulativo
        """
        estimates = []
        
        for i, volume in enumerate(volumes):
            estimate = self.estimate_slippage(
                volume=volume,
                hour_of_day=hour_of_day,
                atr_14=atr_14,
                is_chain_execution=True,
                chain_position=i
            )
            estimates.append(estimate)
        
        return estimates
    
    def apply_slippage_to_trade(
        self,
        trade: Dict,
        slippage_estimate: SlippageEstimate,
        direction: str = 'entry'
    ) -> Dict:
        """
        Aplica slippage a um trade
        
        Args:
            trade: Dict com dados do trade
            slippage_estimate: Estimativa de slippage
            direction: 'entry' ou 'exit'
        
        Returns:
            Trade com slippage aplicado
        """
        trade = trade.copy()
        
        slippage_pips = slippage_estimate.expected_slippage_pips
        slippage_price = slippage_pips * self.pip_value
        
        # Aplicar slippage (desfavorável ao trader)
        if direction == 'entry':
            if trade.get('direction') == 'BUY':
                trade['price_open'] += slippage_price  # Compra mais caro
            else:
                trade['price_open'] -= slippage_price  # Vende mais barato
        else:  # exit
            if trade.get('direction') == 'BUY':
                trade['price_close'] -= slippage_price  # Vende mais barato
            else:
                trade['price_close'] += slippage_price  # Compra mais caro
        
        trade['slippage_pips'] = slippage_pips
        trade['slippage_cost'] = slippage_price * trade.get('volume', 0.01) * 100
        
        # Recalcular profit
        if trade.get('direction') == 'BUY':
            trade['profit'] = (trade['price_close'] - trade['price_open']) * trade.get('volume', 0.01) * 100
        else:
            trade['profit'] = (trade['price_open'] - trade['price_close']) * trade.get('volume', 0.01) * 100
        
        return trade
    
    def calibrate_from_historical(
        self,
        historical_trades: pd.DataFrame
    ) -> Dict:
        """
        Calibra modelo a partir de trades históricos reais
        
        Args:
            historical_trades: DataFrame com trades e slippage real
        
        Returns:
            Dict com parâmetros calibrados
        """
        calibration = {}
        
        # Calibrar por horário
        hourly_slippage = historical_trades.groupby(
            historical_trades['timestamp'].dt.hour
        )['slippage_pips'].agg(['mean', 'std', 'count'])
        
        calibration['hourly'] = hourly_slippage.to_dict()
        
        # Calibrar por volume
        historical_trades['volume_bucket'] = historical_trades['volume'].apply(
            self._classify_volume
        )
        volume_slippage = historical_trades.groupby('volume_bucket')['slippage_pips'].mean()
        
        calibration['by_volume'] = volume_slippage.to_dict()
        
        # Calibrar por volatilidade
        if 'atr_14' in historical_trades.columns:
            historical_trades['atr_bucket'] = pd.cut(
                historical_trades['atr_14'],
                bins=[0, 0.5, 1.0, 1.5, 2.0, np.inf],
                labels=['very_low', 'low', 'medium', 'high', 'very_high']
            )
            atr_slippage = historical_trades.groupby('atr_bucket')['slippage_pips'].mean()
            calibration['by_atr'] = atr_slippage.to_dict()
        
        return calibration
    
    def _classify_volume(self, volume: float) -> str:
        """Classifica volume em bucket"""
        if volume < 0.1:
            return 'micro'
        elif volume < 0.5:
            return 'small'
        elif volume < 2.0:
            return 'medium'
        elif volume < 5.0:
            return 'large'
        else:
            return 'institutional'
    
    def get_liquidity_score(self, hour_of_day: int) -> int:
        """
        Retorna score de liquidez (0-100) por horário
        
        Útil para evitar horários de baixa liquidez
        """
        # Horários de maior liquidez
        high_liquidity_hours = [8, 9, 12, 13, 14]  # London/NY overlap
        medium_liquidity_hours = [7, 10, 11, 15, 16]
        
        if hour_of_day in high_liquidity_hours:
            return 90
        elif hour_of_day in medium_liquidity_hours:
            return 70
        elif hour_of_day in range(20, 24):  # Asia open
            return 50
        else:
            return 30  # Baixa liquidez

class LiquidityImpactModel:
    """
    Modela impacto de liquidez em execução de múltiplos trades
    
    FR-12-B: Liquidity Impact (execução em cadeia)
    """
    
    def __init__(self):
        self.impact_decay_time = 300  # 5 minutos para decay do impacto
    
    def calculate_market_impact(
        self,
        volume: float,
        available_liquidity: float,
        order_book_depth: Optional[Dict] = None
    ) -> float:
        """
        Calcula impacto de mercado baseado em volume vs liquidez disponível
        
        Args:
            volume: Volume do trade
            available_liquidity: Liquidez disponível no book
            order_book_depth: Profundidade do book (opcional)
        
        Returns:
            Impacto em pips
        """
        if available_liquidity <= 0:
            return 5.0  # Impacto máximo se não há liquidez
        
        # Ratio de consumo de liquidez
        consumption_ratio = volume / available_liquidity
        
        # Impacto não-linear (quadrado do ratio)
        base_impact = consumption_ratio ** 2 * 2.0
        
        # Cap em 10 pips
        return min(base_impact, 10.0)
    
    def estimate_chain_impact(
        self,
        volumes: List[float],
        time_intervals: List[float],  # segundos entre trades
        base_liquidity: float = 10.0
    ) -> List[float]:
        """
        Estima impacto cumulativo de execução em cadeia
        
        O impacto de cada trade afeta o próximo (liquidez temporariamente reduzida)
        """
        impacts = []
        current_liquidity = base_liquidity
        
        for i, (volume, interval) in enumerate(zip(volumes, time_intervals)):
            # Recuperar liquidez desde o último trade
            if i > 0:
                recovery = min(1.0, interval / self.impact_decay_time)
                current_liquidity = base_liquidity * recovery + current_liquidity * (1 - recovery)
            
            # Calcular impacto
            impact = self.calculate_market_impact(volume, current_liquidity)
            impacts.append(impact)
            
            # Reduzir liquidez disponível
            current_liquidity = max(0.1, current_liquidity - volume * 0.5)
        
        return impacts
