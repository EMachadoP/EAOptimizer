"""
EA Configuration Optimizer v1.2
Core Module

Módulos principais:
- trade_reconstruction: Reconstrução de trades e cálculo de Basket_MAE
- regime_detection: Detecção de regime (Hurst + ADX)
- survival_analysis: Análise de sobrevivência (Kaplan-Meier)
- robustness_mapping: Mapeamento de robustez (3D Surface)
- optimization_engine: Motor de otimização (Ulcer, CVaR)
- slippage_model: Modelo de slippage
- mt5_importer: Importação de dados MT5
"""

from .trade_reconstruction import (
    TradeReconstructionEngine,
    LookAheadBiasAuditor,
    TradeInfo,
    BasketMetrics
)

from .regime_detection import (
    RegimeDetectionEngine,
    HurstExponentCalculator,
    ADXCalculator,
    RegimeFeatures,
    RegimeType
)

from .survival_analysis import (
    SurvivalAnalysisEngine,
    KaplanMeierEstimator,
    SurvivalCurve
)

from .robustness_mapping import (
    RobustnessLandscape,
    RobustnessMetrics
)

from .optimization_engine import (
    OptimizationEngine,
    OptimizationConfig,
    PerformanceMetrics,
    RiskMetricsCalculator,
    MonteCarloSimulator
)

from .slippage_model import (
    SlippageModel,
    LiquidityImpactModel,
    SlippageEstimate
)

from .mt5_importer import (
    MT5DataImporter,
    MT5Config,
    DataPipeline
)

__all__ = [
    # Trade Reconstruction
    'TradeReconstructionEngine',
    'LookAheadBiasAuditor',
    'TradeInfo',
    'BasketMetrics',
    
    # Regime Detection
    'RegimeDetectionEngine',
    'HurstExponentCalculator',
    'ADXCalculator',
    'RegimeFeatures',
    'RegimeType',
    
    # Survival Analysis
    'SurvivalAnalysisEngine',
    'KaplanMeierEstimator',
    'SurvivalCurve',
    
    # Robustness Mapping
    'RobustnessLandscape',
    'RobustnessMetrics',
    
    # Optimization
    'OptimizationEngine',
    'OptimizationConfig',
    'PerformanceMetrics',
    'RiskMetricsCalculator',
    'MonteCarloSimulator',
    
    # Slippage
    'SlippageModel',
    'LiquidityImpactModel',
    'SlippageEstimate',
    
    # MT5 Import
    'MT5DataImporter',
    'MT5Config',
    'DataPipeline'
]
