"""
EA Configuration Optimizer v1.2
Optimization Engine
FR-09: Optimization Engine com Ulcer Index e CVaR_95

Métricas de Performance:
- Total Return
- Profit Factor
- Sharpe Ratio
- Ulcer Index (penalização de drawdown)
- CVaR_95 (Conditional Value at Risk)
- Return/Ulcer Ratio
- Return/CVaR Ratio
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional, Callable
from dataclasses import dataclass
from scipy import stats
from scipy.optimize import minimize
import hashlib
import json

@dataclass
class PerformanceMetrics:
    """Métricas de performance de uma configuração"""
    # Retorno
    total_return: float
    total_return_pct: float
    
    # Métricas de risco
    max_drawdown: float
    max_drawdown_pct: float
    ulcer_index: float
    cvar_95: float
    volatility: float
    
    # Métricas de trade
    total_trades: int
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    
    # Métricas ajustadas
    sharpe_ratio: float
    sortino_ratio: float
    return_over_ulcer: float
    return_over_cvar: float
    
    # Score composto
    optimization_score: float

@dataclass
class OptimizationConfig:
    """Configuração de parâmetros do grid"""
    grid_pips: int
    multiplier: float
    atr_filter: float
    max_levels: int
    base_volume: float = 0.01
    take_profit_pips: int = 100
    stop_loss_pips: int = 500
    
    def to_dict(self) -> Dict:
        return {
            'grid_pips': self.grid_pips,
            'multiplier': self.multiplier,
            'atr_filter': self.atr_filter,
            'max_levels': self.max_levels,
            'base_volume': self.base_volume,
            'take_profit_pips': self.take_profit_pips,
            'stop_loss_pips': self.stop_loss_pips
        }
    
    def get_hash(self) -> str:
        """Gera hash único da configuração"""
        config_str = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()[:16]

class RiskMetricsCalculator:
    """
    Calculador de métricas de risco avançadas
    """
    
    @staticmethod
    def calculate_ulcer_index(returns: np.ndarray) -> float:
        """
        Calcula Ulcer Index - medida de drawdown que penaliza
        tanto a magnitude quanto a duração dos drawdowns
        
        UI = sqrt(mean((DD / peak)^2))
        onde DD = drawdown em cada ponto
        """
        if len(returns) == 0:
            return 0.0
        
        # Calcular equity curve
        equity = np.cumsum(returns)
        
        # Calcular running peak
        running_peak = np.maximum.accumulate(equity)
        
        # Calcular drawdown percentage
        drawdown_pct = np.where(
            running_peak > 0,
            (running_peak - equity) / running_peak * 100,
            0
        )
        
        # Ulcer Index (raiz quadrada da média dos quadrados)
        ulcer = np.sqrt(np.mean(drawdown_pct ** 2))
        
        return ulcer
    
    @staticmethod
    def calculate_cvar(returns: np.ndarray, confidence: float = 0.95) -> float:
        """
        Calcula Conditional Value at Risk (CVaR) / Expected Shortfall
        
        CVaR_95 = média dos piores 5% de retornos
        """
        if len(returns) == 0:
            return 0.0
        
        # Calcular VaR
        var = np.percentile(returns, (1 - confidence) * 100)
        
        # CVaR é a média dos retornos abaixo do VaR
        cvar = np.mean(returns[returns <= var]) if len(returns[returns <= var]) > 0 else var
        
        return abs(cvar)  # Retornar valor positivo
    
    @staticmethod
    def calculate_sharpe_ratio(
        returns: np.ndarray,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252
    ) -> float:
        """Calcula Sharpe Ratio anualizado"""
        if len(returns) == 0 or np.std(returns) == 0:
            return 0.0
        
        excess_returns = returns - risk_free_rate / periods_per_year
        sharpe = np.mean(excess_returns) / np.std(returns) * np.sqrt(periods_per_year)
        
        return sharpe
    
    @staticmethod
    def calculate_sortino_ratio(
        returns: np.ndarray,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252
    ) -> float:
        """Calcula Sortino Ratio (usa apenas desvio negativo)"""
        if len(returns) == 0:
            return 0.0
        
        downside_returns = returns[returns < 0]
        downside_std = np.std(downside_returns) if len(downside_returns) > 0 else 0.0
        
        if downside_std == 0:
            return 0.0
        
        excess_returns = np.mean(returns) - risk_free_rate / periods_per_year
        sortino = excess_returns / downside_std * np.sqrt(periods_per_year)
        
        return sortino

class OptimizationEngine:
    """
    Motor de otimização de configurações de grid
    """
    
    def __init__(
        self,
        market_data: pd.DataFrame,
        risk_free_rate: float = 0.0,
        objective_function: str = "ulcer_adjusted"
    ):
        """
        Args:
            market_data: DataFrame com dados de mercado (OHLCV)
            risk_free_rate: Taxa livre de risco anual
            objective_function: Função objetivo ('ulcer_adjusted', 'sharpe', 'cvar')
        """
        self.market_data = market_data
        self.risk_free_rate = risk_free_rate
        self.objective_function = objective_function
        self.risk_calc = RiskMetricsCalculator()
    
    def evaluate_config(
        self,
        config: OptimizationConfig,
        trades: Optional[pd.DataFrame] = None,
        equity_curve: Optional[np.ndarray] = None
    ) -> PerformanceMetrics:
        """
        Avalia uma configuração e retorna métricas completas
        
        Args:
            config: Configuração a avaliar
            trades: DataFrame com trades (opcional)
            equity_curve: Curva de equity (opcional)
        
        Returns:
            PerformanceMetrics
        """
        # Se não temos trades, simular
        if trades is None:
            trades, equity_curve = self._simulate_grid(config)
        
        if len(trades) == 0:
            return self._empty_metrics()
        
        # Calcular métricas básicas
        returns = trades['profit'].values
        total_return = np.sum(returns)
        
        # Win/Loss stats
        wins = returns[returns > 0]
        losses = returns[returns <= 0]
        
        win_rate = len(wins) / len(returns) * 100 if len(returns) > 0 else 0
        avg_win = np.mean(wins) if len(wins) > 0 else 0
        avg_loss = np.mean(losses) if len(losses) > 0 else 0
        
        # Profit Factor
        profit_factor = abs(np.sum(wins) / np.sum(losses)) if np.sum(losses) != 0 else float('inf')
        
        # Calcular equity curve se não fornecida
        if equity_curve is None:
            equity_curve = np.cumsum(returns)
        
        # Drawdown
        running_peak = np.maximum.accumulate(equity_curve)
        drawdowns = running_peak - equity_curve
        max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0
        max_dd_pct = (max_drawdown / running_peak.max() * 100) if running_peak.max() > 0 else 0
        
        # Métricas avançadas
        ulcer_index = self.risk_calc.calculate_ulcer_index(returns)
        cvar_95 = self.risk_calc.calculate_cvar(returns, 0.95)
        volatility = np.std(returns) * np.sqrt(252)  # Anualizado
        
        # Ratios
        sharpe = self.risk_calc.calculate_sharpe_ratio(returns, self.risk_free_rate)
        sortino = self.risk_calc.calculate_sortino_ratio(returns, self.risk_free_rate)
        
        # Return/Risk ratios
        return_over_ulcer = total_return / ulcer_index if ulcer_index > 0 else 0
        return_over_cvar = total_return / cvar_95 if cvar_95 > 0 else 0
        
        # Score composto (Ulcer-adjusted)
        optimization_score = self._calculate_composite_score(
            total_return=total_return,
            win_rate=win_rate,
            profit_factor=profit_factor,
            ulcer_index=ulcer_index,
            cvar_95=cvar_95,
            max_drawdown_pct=max_dd_pct
        )
        
        return PerformanceMetrics(
            total_return=total_return,
            total_return_pct=(equity_curve[-1] / equity_curve[0] - 1) * 100 if len(equity_curve) > 1 else 0,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_dd_pct,
            ulcer_index=ulcer_index,
            cvar_95=cvar_95,
            volatility=volatility,
            total_trades=len(trades),
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            return_over_ulcer=return_over_ulcer,
            return_over_cvar=return_over_cvar,
            optimization_score=optimization_score
        )
    
    def optimize(
        self,
        param_grid: Dict[str, List],
        n_jobs: int = 1,
        verbose: bool = True
    ) -> Tuple[OptimizationConfig, PerformanceMetrics, pd.DataFrame]:
        """
        Otimização completa de parâmetros
        
        Args:
            param_grid: Dict com listas de valores para cada parâmetro
            n_jobs: Número de jobs paralelos
            verbose: Mostrar progresso
        
        Returns:
            Tuple de (melhor_config, melhores_metricas, todos_resultados)
        """
        from itertools import product
        
        # Gerar todas as combinações
        param_names = list(param_grid.keys())
        param_combinations = list(product(*param_grid.values()))
        
        if verbose:
            print(f"Otimizando {len(param_combinations)} configurações...")
        
        results = []
        best_score = -np.inf
        best_config = None
        best_metrics = None
        
        for i, params in enumerate(param_combinations):
            if verbose and (i + 1) % 100 == 0:
                print(f"Avaliadas {i + 1}/{len(param_combinations)} configurações...")
            
            # Criar configuração
            config = OptimizationConfig(
                grid_pips=params[0],
                multiplier=params[1],
                atr_filter=params[2],
                max_levels=params[3]
            )
            
            # Avaliar
            metrics = self.evaluate_config(config)
            
            # Guardar resultado
            result = {
                'config_hash': config.get_hash(),
                'grid_pips': config.grid_pips,
                'multiplier': config.multiplier,
                'atr_filter': config.atr_filter,
                'max_levels': config.max_levels,
                'total_return': metrics.total_return,
                'profit_factor': metrics.profit_factor,
                'sharpe_ratio': metrics.sharpe_ratio,
                'ulcer_index': metrics.ulcer_index,
                'cvar_95': metrics.cvar_95,
                'max_drawdown_pct': metrics.max_drawdown_pct,
                'win_rate': metrics.win_rate,
                'total_trades': metrics.total_trades,
                'return_over_ulcer': metrics.return_over_ulcer,
                'return_over_cvar': metrics.return_over_cvar,
                'optimization_score': metrics.optimization_score
            }
            results.append(result)
            
            # Verificar se é melhor
            if metrics.optimization_score > best_score:
                best_score = metrics.optimization_score
                best_config = config
                best_metrics = metrics
        
        if verbose:
            print(f"Otimização completa. Melhor score: {best_score:.2f}")
        
        return best_config, best_metrics, pd.DataFrame(results)
    
    def _simulate_grid(
        self,
        config: OptimizationConfig
    ) -> Tuple[pd.DataFrame, np.ndarray]:
        """
        Simula operação do grid em dados históricos
        
        Simplificado - na implementação real, usar TradeReconstructionEngine
        """
        # Simulação básica para demonstração
        np.random.seed(42)
        
        n_trades = 100
        
        # Simular trades com características do grid
        win_prob = 0.55  # Grid tende a ter win rate > 50%
        avg_win = 50 * config.grid_pips / 300  # Ajustado pelo grid spacing
        avg_loss = 45 * config.multiplier / 1.3  # Ajustado pelo multiplier
        
        trades_data = []
        equity = [10000]  # Capital inicial
        
        for i in range(n_trades):
            is_win = np.random.random() < win_prob
            
            if is_win:
                profit = np.random.normal(avg_win, avg_win * 0.3)
            else:
                profit = -np.random.normal(avg_loss, avg_loss * 0.3)
            
            trades_data.append({
                'trade_id': i,
                'profit': profit,
                'timestamp': pd.Timestamp.now() + pd.Timedelta(hours=i)
            })
            
            equity.append(equity[-1] + profit)
        
        return pd.DataFrame(trades_data), np.array(equity)
    
    def _calculate_composite_score(
        self,
        total_return: float,
        win_rate: float,
        profit_factor: float,
        ulcer_index: float,
        cvar_95: float,
        max_drawdown_pct: float
    ) -> float:
        """
        Calcula score composto Ulcer-adjusted
        
        Fórmula ponderada que prioriza:
        - Retorno positivo
        - Baixo Ulcer Index (drawdown controlado)
        - Baixo CVaR (cauda controlada)
        - Win rate razoável
        """
        # Normalizar componentes
        return_score = min(total_return / 1000, 100)  # Cap em 100
        ulcer_penalty = min(ulcer_index / 10, 50)  # Penalidade por drawdown
        cvar_penalty = min(cvar_95 / 100, 30)  # Penalidade por risco de cauda
        dd_penalty = min(max_drawdown_pct / 5, 20)  # Penalidade por max DD
        
        # Win rate bonus
        wr_bonus = (win_rate - 50) * 0.5 if win_rate > 50 else 0
        
        # Profit factor bonus
        pf_bonus = (profit_factor - 1.5) * 10 if profit_factor > 1.5 else 0
        
        # Score final
        score = (
            return_score -
            ulcer_penalty -
            cvar_penalty -
            dd_penalty +
            wr_bonus +
            pf_bonus
        )
        
        return max(0, score)
    
    def _empty_metrics(self) -> PerformanceMetrics:
        """Retorna métricas vazias"""
        return PerformanceMetrics(
            total_return=0.0,
            total_return_pct=0.0,
            max_drawdown=0.0,
            max_drawdown_pct=0.0,
            ulcer_index=0.0,
            cvar_95=0.0,
            volatility=0.0,
            total_trades=0,
            win_rate=0.0,
            profit_factor=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            return_over_ulcer=0.0,
            return_over_cvar=0.0,
            optimization_score=0.0
        )

class MonteCarloSimulator:
    """
    FR-07: Parameter Simulator
    Simulação Monte Carlo de parâmetros Grid/Mult/ATR
    """
    
    def __init__(self, optimization_engine: OptimizationEngine):
        self.engine = optimization_engine
    
    def simulate(
        self,
        base_config: OptimizationConfig,
        n_simulations: int = 1000,
        param_variations: Optional[Dict[str, Tuple[float, float]]] = None
    ) -> pd.DataFrame:
        """
        Simula variações de parâmetros via Monte Carlo
        
        Args:
            base_config: Configuração base
            n_simulations: Número de simulações
            param_variations: Dict com (min, max) de variação para cada parâmetro
        
        Returns:
            DataFrame com resultados das simulações
        """
        if param_variations is None:
            param_variations = {
                'grid_pips': (0.9, 1.1),  # ±10%
                'multiplier': (0.95, 1.05),  # ±5%
                'atr_filter': (0.9, 1.1)  # ±10%
            }
        
        results = []
        
        for i in range(n_simulations):
            # Gerar configuração variada
            varied_config = OptimizationConfig(
                grid_pips=int(base_config.grid_pips * np.random.uniform(*param_variations['grid_pips'])),
                multiplier=base_config.multiplier * np.random.uniform(*param_variations['multiplier']),
                atr_filter=base_config.atr_filter * np.random.uniform(*param_variations['atr_filter']),
                max_levels=base_config.max_levels
            )
            
            # Avaliar
            metrics = self.engine.evaluate_config(varied_config)
            
            results.append({
                'simulation_id': i,
                'grid_pips': varied_config.grid_pips,
                'multiplier': varied_config.multiplier,
                'atr_filter': varied_config.atr_filter,
                'total_return': metrics.total_return,
                'ulcer_index': metrics.ulcer_index,
                'cvar_95': metrics.cvar_95,
                'optimization_score': metrics.optimization_score
            })
        
        return pd.DataFrame(results)
    
    def analyze_sensitivity(
        self,
        mc_results: pd.DataFrame
    ) -> Dict:
        """
        Analisa sensibilidade dos parâmetros
        
        Returns:
            Dict com análise de sensibilidade
        """
        return {
            'return_stats': {
                'mean': mc_results['total_return'].mean(),
                'std': mc_results['total_return'].std(),
                'min': mc_results['total_return'].min(),
                'max': mc_results['total_return'].max(),
                'var_95': mc_results['total_return'].quantile(0.05)
            },
            'score_stats': {
                'mean': mc_results['optimization_score'].mean(),
                'std': mc_results['optimization_score'].std(),
                'prob_positive': (mc_results['optimization_score'] > 0).mean()
            },
            'correlations': {
                'grid_vs_return': mc_results[['grid_pips', 'total_return']].corr().iloc[0, 1],
                'multiplier_vs_return': mc_results[['multiplier', 'total_return']].corr().iloc[0, 1],
                'atr_vs_return': mc_results[['atr_filter', 'total_return']].corr().iloc[0, 1]
            }
        }
