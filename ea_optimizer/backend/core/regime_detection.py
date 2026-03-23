"""
EA Configuration Optimizer v1.2
Regime Detection Engine
FR-14: Regime Detection & Profit Matrix

Classificadores:
- Hurst Exponent (H < 0.5: Mean Reversion, H = 0.5: Random Walk, H > 0.5: Trending)
- ADX(14) + EMA Slope (ADX < 20: Range, ADX 20-40: Moderate Trend, ADX > 40: Strong Trend)
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, List, Optional
from dataclasses import dataclass
from scipy import stats
from enum import Enum

class RegimeType(Enum):
    """Tipos de regime de mercado"""
    RANGE_MEAN_REVERSION = "Range_MeanRev"      # H < 0.5, ADX < 20
    RANGE_NEUTRAL = "Range_Neutral"              # H ≈ 0.5, ADX < 20
    TREND_WEAK = "Trend_Weak"                    # H > 0.5, ADX 20-40
    TREND_STRONG = "Trend_Strong"                # H > 0.5, ADX > 40
    TREND_MODERATE = "Trend_Moderate"            # H < 0.5, ADX 20-40
    UNKNOWN = "Unknown"

@dataclass
class RegimeFeatures:
    """Features de regime calculadas"""
    hurst_exponent: float
    adx_value: float
    ema_slope: float
    regime_class: str
    
    # Metadados
    window_size: int
    calculation_time: Optional[pd.Timestamp] = None

class HurstExponentCalculator:
    """
    Calcula Hurst Exponent usando Rescaled Range (R/S) Analysis
    
    H < 0.5: Mean Reversion (favorável a grids)
    H = 0.5: Random Walk
    H > 0.5: Trending (perigoso para grids)
    """
    
    def __init__(self, max_lag: int = 100):
        self.max_lag = max_lag
    
    def calculate(self, prices: pd.Series, window: int = 100) -> pd.Series:
        """
        Calcula Hurst Exponent em janela móvel
        
        Args:
            prices: Série de preços
            window: Tamanho da janela móvel (padrão: 100 barras)
        
        Returns:
            Série com Hurst Exponent
        """
        hurst_values = []
        
        for i in range(len(prices)):
            if i < window - 1:
                hurst_values.append(np.nan)
                continue
            
            # Pegar janela de preços
            window_prices = prices.iloc[i - window + 1:i + 1]
            
            # Calcular Hurst para esta janela
            h = self._calculate_rs(window_prices.values)
            hurst_values.append(h)
        
        return pd.Series(hurst_values, index=prices.index)
    
    def _calculate_rs(self, series: np.ndarray) -> float:
        """
        Calcula Hurst Exponent via Rescaled Range Analysis
        
        Algoritmo R/S:
        1. Calcular desvios da média
        2. Calcular range acumulado
        3. Normalizar pelo desvio padrão
        4. Encontrar slope log-log
        """
        if len(series) < 10:
            return 0.5
        
        # Retornos logarítmicos
        returns = np.diff(np.log(series))
        
        if len(returns) < 10 or np.std(returns) == 0:
            return 0.5
        
        # Lags para análise
        lags = range(2, min(self.max_lag, len(returns) // 4))
        
        rs_values = []
        lag_values = []
        
        for lag in lags:
            # Dividir em chunks
            n_chunks = len(returns) // lag
            if n_chunks < 1:
                continue
            
            rs_chunks = []
            
            for i in range(n_chunks):
                chunk = returns[i * lag:(i + 1) * lag]
                
                # Mean adjustment
                mean_chunk = np.mean(chunk)
                adjusted = chunk - mean_chunk
                
                # Cumulative deviation
                cumulative = np.cumsum(adjusted)
                
                # Range
                R = np.max(cumulative) - np.min(cumulative)
                
                # Standard deviation
                S = np.std(chunk)
                
                if S > 0:
                    rs_chunks.append(R / S)
            
            if rs_chunks:
                rs_values.append(np.mean(rs_chunks))
                lag_values.append(lag)
        
        if len(rs_values) < 2:
            return 0.5
        
        # Regressão log-log para encontrar Hurst
        log_lags = np.log(lag_values)
        log_rs = np.log(rs_values)
        
        # Slope = Hurst Exponent
        slope, _, r_value, _, _ = stats.linregress(log_lags, log_rs)
        
        # Limitar entre 0 e 1
        hurst = max(0.0, min(1.0, slope))
        
        return hurst
    
    def interpret(self, hurst: float) -> str:
        """Interpreta valor do Hurst Exponent"""
        if hurst < 0.4:
            return "Strong Mean Reversion (Grid Favorable)"
        elif hurst < 0.5:
            return "Mean Reversion (Grid Favorable)"
        elif hurst < 0.55:
            return "Random Walk (Neutral)"
        elif hurst < 0.65:
            return "Trending (Grid Caution)"
        else:
            return "Strong Trend (Grid Avoid)"

class ADXCalculator:
    """
    Calcula ADX (Average Directional Index) e slope da EMA
    
    ADX < 20: Range/Consolidação
    ADX 20-40: Tendência moderada
    ADX > 40: Tendência forte (avoid zone)
    """
    
    def __init__(self, period: int = 14):
        self.period = period
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula ADX, +DI, -DI e slope da EMA
        
        Args:
            df: DataFrame com 'high', 'low', 'close'
        
        Returns:
            DataFrame com colunas adicionais: adx, plus_di, minus_di, ema_slope
        """
        df = df.copy()
        
        # True Range
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift(1))
        df['tr3'] = abs(df['low'] - df['close'].shift(1))
        df['true_range'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        
        # Directional Movement
        df['plus_dm'] = np.where(
            (df['high'] - df['high'].shift(1)) > (df['low'].shift(1) - df['low']),
            np.maximum(df['high'] - df['high'].shift(1), 0),
            0
        )
        df['minus_dm'] = np.where(
            (df['low'].shift(1) - df['low']) > (df['high'] - df['high'].shift(1)),
            np.maximum(df['low'].shift(1) - df['low'], 0),
            0
        )
        
        # Wilder's smoothing
        atr = df['true_range'].ewm(alpha=1/self.period, min_periods=self.period).mean()
        plus_di = 100 * df['plus_dm'].ewm(alpha=1/self.period, min_periods=self.period).mean() / atr
        minus_di = 100 * df['minus_dm'].ewm(alpha=1/self.period, min_periods=self.period).mean() / atr
        
        # ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.ewm(alpha=1/self.period, min_periods=self.period).mean()
        
        df['adx'] = adx
        df['plus_di'] = plus_di
        df['minus_di'] = minus_di
        
        # EMA Slope (ângulo da EMA20)
        ema_20 = df['close'].ewm(span=20, min_periods=20).mean()
        df['ema_20'] = ema_20
        df['ema_slope'] = (ema_20 - ema_20.shift(5)) / 5  # Slope over 5 periods
        
        # Limpar colunas temporárias
        df = df.drop(['tr1', 'tr2', 'tr3', 'plus_dm', 'minus_dm'], axis=1, errors='ignore')
        
        return df
    
    def interpret_adx(self, adx: float) -> str:
        """Interpreta valor do ADX"""
        if adx < 20:
            return "Weak Trend (Range)"
        elif adx < 40:
            return "Moderate Trend"
        else:
            return "Strong Trend (Avoid)"

class RegimeDetectionEngine:
    """
    Motor completo de detecção de regime
    Combina Hurst Exponent + ADX para classificação
    """
    
    def __init__(self, hurst_window: int = 100, adx_period: int = 14):
        self.hurst_calc = HurstExponentCalculator()
        self.adx_calc = ADXCalculator(adx_period)
        self.hurst_window = hurst_window
        self.adx_period = adx_period
    
    def analyze(self, market_data: pd.DataFrame) -> pd.DataFrame:
        """
        Analisa regime de mercado completo
        
        Args:
            market_data: DataFrame com 'open', 'high', 'low', 'close', 'volume'
        
        Returns:
            DataFrame com colunas de regime adicionadas
        """
        df = market_data.copy()
        
        # Calcular ADX e EMA slope
        df = self.adx_calc.calculate(df)
        
        # Calcular Hurst Exponent
        df['hurst_exponent'] = self.hurst_calc.calculate(df['close'], window=self.hurst_window)
        
        # Classificar regime
        df['regime_class'] = df.apply(self._classify_regime, axis=1)
        
        return df
    
    def _classify_regime(self, row: pd.Series) -> str:
        """
        Classifica regime baseado em Hurst e ADX
        
        Regras:
        - Range_MeanRev: H < 0.5, ADX < 20 (FAVORÁVEL A GRIDS)
        - Range_Neutral: H ≈ 0.5, ADX < 20
        - Trend_Weak: ADX 20-40 (tendência moderada)
        - Trend_Strong: ADX > 40 (EVITAR)
        """
        hurst = row.get('hurst_exponent', 0.5)
        adx = row.get('adx', 0)
        
        if pd.isna(hurst) or pd.isna(adx):
            return RegimeType.UNKNOWN.value
        
        # Classificação hierárquica
        if adx > 40:
            return RegimeType.TREND_STRONG.value
        elif adx > 20 and adx <= 40:
            if hurst > 0.55:
                return RegimeType.TREND_WEAK.value
            else:
                return RegimeType.TREND_MODERATE.value
        else:  # ADX < 20 (Range)
            if hurst < 0.45:
                return RegimeType.RANGE_MEAN_REVERSION.value
            else:
                return RegimeType.RANGE_NEUTRAL.value
    
    def get_regime_statistics(
        self,
        market_data: pd.DataFrame,
        trades_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Gera Profit Matrix por Regime
        
        Cruzamento:
        - Linhas: Regimes
        - Colunas: Métricas (Profit Factor, Basket_MAE, Win Rate, etc.)
        """
        if 'regime_class' not in market_data.columns:
            market_data = self.analyze(market_data)
        
        # Mapear trades para regimes
        regime_stats = []
        
        for regime in market_data['regime_class'].unique():
            if pd.isna(regime):
                continue
            
            # Filtrar períodos deste regime
            regime_periods = market_data[market_data['regime_class'] == regime]
            
            # Encontrar trades nestes períodos
            regime_trades = []
            for _, period in regime_periods.iterrows():
                period_trades = trades_data[
                    (trades_data['timestamp_open'] >= period.name) &
                    (trades_data['timestamp_open'] < period.name + pd.Timedelta(hours=1))
                ]
                regime_trades.append(period_trades)
            
            if regime_trades:
                all_regime_trades = pd.concat(regime_trades, ignore_index=True)
            else:
                all_regime_trades = pd.DataFrame()
            
            # Calcular métricas
            stats = self._calculate_regime_metrics(all_regime_trades, regime)
            regime_stats.append(stats)
        
        return pd.DataFrame(regime_stats)
    
    def _calculate_regime_metrics(
        self,
        trades: pd.DataFrame,
        regime: str
    ) -> Dict:
        """Calcula métricas para um regime específico"""
        if len(trades) == 0:
            return {
                'regime': regime,
                'trades_count': 0,
                'profit_factor': 0.0,
                'basket_mae_avg': 0.0,
                'win_rate': 0.0,
                'avg_exposure_hours': 0.0
            }
        
        profits = trades['profit'].values
        wins = profits[profits > 0]
        losses = profits[profits <= 0]
        
        profit_factor = abs(wins.sum() / losses.sum()) if len(losses) > 0 and losses.sum() != 0 else float('inf')
        win_rate = len(wins) / len(profits) * 100 if len(profits) > 0 else 0
        
        # Tempo médio de exposição
        if 'timestamp_close' in trades.columns and 'timestamp_open' in trades.columns:
            trades['exposure_time'] = pd.to_datetime(trades['timestamp_close']) - pd.to_datetime(trades['timestamp_open'])
            avg_exposure = trades['exposure_time'].dt.total_seconds().mean() / 3600  # horas
        else:
            avg_exposure = 0
        
        return {
            'regime': regime,
            'trades_count': len(trades),
            'profit_factor': round(profit_factor, 2),
            'basket_mae_avg': round(trades.get('basket_mae', pd.Series([0])).mean(), 2),
            'win_rate': round(win_rate, 2),
            'avg_exposure_hours': round(avg_exposure, 2)
        }
    
    def generate_insight(self, regime_matrix: pd.DataFrame) -> List[str]:
        """
        Gera insights automáticos baseados na Profit Matrix
        
        Exemplo:
        "Seu Grid ganha $15k em regime Range_MeanRev (H<0.4), mas perde $12k em Trend_Strong (ADX>40).
        Sugestão: Adicionar filtro de ADX < 25 ou H < 0.45 para bloqueio de novas entradas em tendência."
        """
        insights = []
        
        if len(regime_matrix) == 0:
            return insights
        
        # Encontrar melhor e pior regime
        best_regime = regime_matrix.loc[regime_matrix['profit_factor'].idxmax()]
        worst_regime = regime_matrix.loc[regime_matrix['profit_factor'].idxmin()]
        
        # Insight sobre diferença de performance
        if best_regime['profit_factor'] > 2.0 and worst_regime['profit_factor'] < 1.0:
            insight = (
                f"Seu Grid tem Profit Factor {best_regime['profit_factor']:.1f} em {best_regime['regime']} "
                f"mas cai para {worst_regime['profit_factor']:.1f} em {worst_regime['regime']}. "
            )
            
            # Sugestão específica
            if worst_regime['regime'] == RegimeType.TREND_STRONG.value:
                insight += "Sugestão: Adicionar filtro de ADX < 25 ou H < 0.45 para bloquear entradas em tendência forte."
            elif worst_regime['regime'] == RegimeType.TREND_WEAK.value:
                insight += "Sugestão: Reduzir tamanho do grid em 50% quando ADX > 20."
            
            insights.append(insight)
        
        # Insight sobre win rate
        if best_regime['win_rate'] > 60 and worst_regime['win_rate'] < 40:
            insights.append(
                f"Win rate varia de {best_regime['win_rate']:.0f}% ({best_regime['regime']}) "
                f"para {worst_regime['win_rate']:.0f}% ({worst_regime['regime']}). "
                f"Considere operar apenas no regime favorável."
            )
        
        return insights
