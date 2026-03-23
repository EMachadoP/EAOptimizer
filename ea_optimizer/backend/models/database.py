"""
EA Configuration Optimizer v1.2
Database Models and Schema
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, DECIMAL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from typing import Optional
import os

Base = declarative_base()

DEFAULT_DB_PATH = "ea_optimizer.db"


def resolve_db_path(explicit_path: Optional[str] = None) -> str:
    """Resolve the SQLite path, preferring the deployment environment variable."""
    db_path = explicit_path or os.getenv("EAOPTIMIZER_DB_PATH") or DEFAULT_DB_PATH
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    return db_path

class MarketData(Base):
    """Tabela: market_data - Dados de mercado (OHLCV + indicadores)"""
    __tablename__ = 'market_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    symbol = Column(String(10), nullable=False, index=True)
    open = Column(DECIMAL(10, 5))
    high = Column(DECIMAL(10, 5))
    low = Column(DECIMAL(10, 5))
    close = Column(DECIMAL(10, 5))
    volume = Column(Integer)
    
    # Indicadores técnicos
    atr_14 = Column(DECIMAL(8, 5))
    ema_20 = Column(DECIMAL(10, 5))
    ema_50 = Column(DECIMAL(10, 5))
    adx_14 = Column(DECIMAL(6, 2))
    
    # Regime detection
    hurst_exponent = Column(DECIMAL(4, 3))
    
    __table_args__ = (
        # Índice composto para consultas eficientes
        {'sqlite_autoincrement': True}
    )

class Trade(Base):
    """Tabela: trades - Trades individuais do EA"""
    __tablename__ = 'trades'
    
    trade_id = Column(Integer, primary_key=True, autoincrement=True)
    basket_id = Column(String(32), nullable=False, index=True)
    timestamp_open = Column(DateTime, nullable=False)
    timestamp_close = Column(DateTime)
    symbol = Column(String(10), nullable=False)
    direction = Column(String(4), nullable=False)  # 'BUY' ou 'SELL'
    volume = Column(DECIMAL(10, 2))
    price_open = Column(DECIMAL(10, 5))
    price_close = Column(DECIMAL(10, 5))
    slippage_pips = Column(DECIMAL(6, 2))
    commission = Column(DECIMAL(10, 2))
    swap = Column(DECIMAL(10, 2))
    profit = Column(DECIMAL(12, 2))
    
    # Relacionamento
    grid_sequence_id = Column(Integer, ForeignKey('grid_sequences.sequence_id'))

class GridSequence(Base):
    """Tabela: grid_sequences - Sequências de trades (baskets)"""
    __tablename__ = 'grid_sequences'
    
    sequence_id = Column(Integer, primary_key=True, autoincrement=True)
    basket_id = Column(String(32), nullable=False, unique=True, index=True)
    symbol = Column(String(10), nullable=False)
    timestamp_start = Column(DateTime, nullable=False)
    timestamp_end = Column(DateTime)
    
    # Parâmetros do grid
    grid_spacing_pips = Column(Integer)
    lot_multiplier = Column(DECIMAL(3, 2))
    max_levels = Column(Integer)
    atr_filter = Column(DECIMAL(3, 2))
    
    # Métricas de performance
    total_trades = Column(Integer)
    total_profit = Column(DECIMAL(12, 2))
    basket_mae = Column(DECIMAL(12, 2))  # Maximum Adverse Excursion
    basket_mfe = Column(DECIMAL(12, 2))  # Maximum Favorable Excursion
    realized_profit = Column(DECIMAL(12, 2))
    floating_pnl = Column(DECIMAL(12, 2))
    total_commission = Column(DECIMAL(10, 2))
    total_swap = Column(DECIMAL(10, 2))
    
    # Flags
    phantom_winner = Column(Boolean, default=False)
    hit_take_profit = Column(Boolean, default=False)
    hit_stop_loss = Column(Boolean, default=False)
    
    # Regime no momento de abertura
    regime_at_start = Column(String(20))

class RegimeAnalysis(Base):
    """Tabela: regime_analysis - Análise de regime de mercado"""
    __tablename__ = 'regime_analysis'
    
    analysis_id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    symbol = Column(String(10))
    
    # Classificadores
    hurst_exponent = Column(DECIMAL(4, 3))  # H value
    adx_value = Column(DECIMAL(6, 2))
    ema_slope = Column(DECIMAL(8, 5))
    regime_class = Column(String(20))  # 'Range_MeanRev', 'Trend_Strong', etc.
    
    # Performance acumulada neste regime (rolling window)
    trades_in_regime = Column(Integer)
    profit_factor_regime = Column(DECIMAL(5, 2))
    basket_mae_avg = Column(DECIMAL(10, 2))
    win_rate_regime = Column(DECIMAL(5, 2))

class SurvivalCurve(Base):
    """Tabela: survival_curves - Curvas de sobrevivência Kaplan-Meier"""
    __tablename__ = 'survival_curves'
    
    curve_id = Column(Integer, primary_key=True)
    config_hash = Column(String(32), nullable=False, index=True)
    survival_time_hours = Column(Integer, nullable=False)  # t
    survival_probability = Column(DECIMAL(5, 4))  # S(t)
    hazard_rate = Column(DECIMAL(6, 4))  # h(t)
    confidence_lower = Column(DECIMAL(5, 4))
    confidence_upper = Column(DECIMAL(5, 4))
    
    # Metadados
    regime_filter = Column(String(20))  # 'All', 'Trend_Strong', etc.
    sample_size = Column(Integer)  # número de baskets naquela curva
    median_survival_time = Column(DECIMAL(6, 2))
    created_at = Column(DateTime, default=datetime.utcnow)

class RobustnessLandscape(Base):
    """Tabela: robustness_landscape - Análise de robustez paramétrica"""
    __tablename__ = 'robustness_landscape'
    
    landscape_id = Column(Integer, primary_key=True, autoincrement=True)
    grid_pips = Column(Integer, nullable=False)
    multiplier = Column(DECIMAL(3, 2), nullable=False)
    atr_filter = Column(DECIMAL(3, 2))
    
    # Métricas de estabilidade
    optimization_score = Column(DECIMAL(5, 2))  # Score central
    neighbor_stability_pct = Column(DECIMAL(5, 2))  # % de vizinhos com >80% do score
    is_robust = Column(Boolean)  # TRUE se stability_pct >= 80%
    
    # Vizinhança calculada
    score_std_dev = Column(DECIMAL(5, 2))  # Desvio padrão dos scores vizinhos
    score_gradient = Column(DECIMAL(5, 2))  # Taxa de mudança (slope) ao redor
    
    __table_args__ = (
        # Constraint única para combinação de parâmetros
        {'sqlite_autoincrement': True}
    )

class OptimizationResult(Base):
    """Tabela: optimization_results - Resultados de otimização"""
    __tablename__ = 'optimization_results'
    
    result_id = Column(Integer, primary_key=True, autoincrement=True)
    config_hash = Column(String(32), nullable=False, unique=True, index=True)
    
    # Parâmetros
    grid_pips = Column(Integer)
    multiplier = Column(DECIMAL(3, 2))
    atr_filter = Column(DECIMAL(3, 2))
    max_levels = Column(Integer)
    
    # Métricas de performance
    total_return = Column(DECIMAL(10, 2))
    profit_factor = Column(DECIMAL(5, 2))
    sharpe_ratio = Column(DECIMAL(5, 2))
    ulcer_index = Column(DECIMAL(5, 2))
    cvar_95 = Column(DECIMAL(10, 2))
    max_drawdown = Column(DECIMAL(10, 2))
    win_rate = Column(DECIMAL(5, 2))
    total_trades = Column(Integer)
    
    # Métricas de risco ajustadas
    return_over_ulcer = Column(DECIMAL(5, 2))
    return_over_cvar = Column(DECIMAL(5, 2))
    
    # Score composto (Ulcer-adjusted)
    optimization_score = Column(DECIMAL(5, 2))
    
    created_at = Column(DateTime, default=datetime.utcnow)

class SlippageModel(Base):
    """Tabela: slippage_model - Modelo de slippage por horário e volume"""
    __tablename__ = 'slippage_model'
    
    model_id = Column(Integer, primary_key=True, autoincrement=True)
    hour_of_day = Column(Integer, nullable=False)
    volume_bucket = Column(String(10), nullable=False)  # 'low', 'medium', 'high'
    avg_slippage_pips = Column(DECIMAL(6, 2))
    std_slippage_pips = Column(DECIMAL(6, 2))
    sample_size = Column(Integer)

# Database initialization
def init_database(db_path: Optional[str] = None):
    """Initialize database with all tables"""
    db_path = resolve_db_path(db_path)
    engine = create_engine(f'sqlite:///{db_path}', echo=False)
    Base.metadata.create_all(engine)
    return engine

def get_session(engine):
    """Get database session"""
    Session = sessionmaker(bind=engine)
    return Session()
