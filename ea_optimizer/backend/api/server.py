"""
EA Configuration Optimizer v1.2
Flask API Server

Endpoints REST para integração com frontend
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime, timedelta
import json
import tempfile
from sqlalchemy import text
from typing import Optional
import math

# Adicionar parent ao path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import (
    TradeReconstructionEngine,
    RegimeDetectionEngine,
    SurvivalAnalysisEngine,
    RobustnessLandscape,
    OptimizationEngine,
    OptimizationConfig,
    SlippageModel,
    MT5DataImporter,
    DataPipeline
)
from models.database import init_database, get_session, resolve_db_path

app = Flask(__name__)


def get_allowed_origins():
    configured = os.getenv("EAOPTIMIZER_CORS_ORIGINS")
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]

    vercel_frontend = os.getenv("EAOPTIMIZER_FRONTEND_URL")
    if vercel_frontend:
        return [vercel_frontend]

    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://ea-optimizer.vercel.app",
        "https://ea-optimizer-h2f54hu0z-eldons-projects-3194802d.vercel.app",
    ]


CORS(app, resources={r"/api/*": {"origins": get_allowed_origins()}})

# Inicializar banco de dados
DB_PATH = resolve_db_path()
engine = init_database(DB_PATH)

# Cache de dados
market_data_cache = {}
optimization_results_cache = None


def _persist_uploaded_file(uploaded_file):
    suffix = os.path.splitext(uploaded_file.filename or "")[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        uploaded_file.save(tmp.name)
        return tmp.name


def _normalize_symbol_family(symbol: str) -> str:
    """Use the broker-neutral symbol prefix so XAUUSD matches XAUUSDc/XAUUSDm."""
    raw = (symbol or "XAUUSD").strip().upper()
    for base in ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD"]:
        if raw.startswith(base):
            return base
    return raw


def _load_symbol_frame(session, table_name: str, symbol: str, order_by: Optional[str] = None):
    symbol_family = _normalize_symbol_family(symbol)
    query = f"SELECT * FROM {table_name} WHERE UPPER(symbol) LIKE :symbol_like"
    if order_by:
        query += f" ORDER BY {order_by}"
    return pd.read_sql(text(query), session.bind, params={"symbol_like": f"{symbol_family}%"})


def _build_robustness_landscape_frame(results_df: pd.DataFrame) -> pd.DataFrame:
    """Ensure robustness endpoints always work from raw optimization results."""
    if results_df is None or len(results_df) == 0:
        return pd.DataFrame()

    if {"neighbor_stability_pct", "is_robust"}.issubset(results_df.columns):
        return results_df.copy()

    landscape_builder = RobustnessLandscape()
    return landscape_builder.build_landscape(results_df)


def _json_safe(value):
    """Recursively replace NaN/inf with None so Flask emits valid JSON."""
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
    return value


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return default
        return int(value)
    except Exception:
        return default


def _build_diagnostic_findings(
    trades_df: pd.DataFrame,
    baskets_df: pd.DataFrame,
    market_df: pd.DataFrame,
    optimization_df: pd.DataFrame
):
    findings = []
    recommendations = []

    trades_profit = pd.to_numeric(trades_df.get('profit'), errors='coerce').fillna(0.0) if len(trades_df) else pd.Series(dtype=float)
    baskets_profit = pd.to_numeric(baskets_df.get('realized_profit', baskets_df.get('total_profit')), errors='coerce').fillna(0.0) if len(baskets_df) else pd.Series(dtype=float)
    basket_mae = pd.to_numeric(baskets_df.get('basket_mae'), errors='coerce').fillna(0.0) if len(baskets_df) else pd.Series(dtype=float)
    exposure_hours = baskets_df.get('exposure_time_hours', pd.Series(dtype=float))
    exposure_hours = pd.to_numeric(exposure_hours, errors='coerce').fillna(0.0) if len(baskets_df) else pd.Series(dtype=float)

    net_profit = _safe_float(trades_profit.sum())
    win_rate = _safe_float((trades_profit > 0).mean() * 100 if len(trades_profit) else 0.0)
    avg_levels = _safe_float(pd.to_numeric(baskets_df.get('total_trades'), errors='coerce').fillna(0.0).mean() if len(baskets_df) else 0.0)
    stop_rate = _safe_float(pd.to_numeric(baskets_df.get('hit_stop_loss'), errors='coerce').fillna(0.0).mean() * 100 if len(baskets_df) else 0.0)
    phantom_rate = _safe_float(pd.to_numeric(baskets_df.get('phantom_winner'), errors='coerce').fillna(0.0).mean() * 100 if len(baskets_df) else 0.0)
    median_exposure = _safe_float(exposure_hours.median() if len(exposure_hours) else 0.0)
    avg_mae = _safe_float(basket_mae.mean() if len(basket_mae) else 0.0)
    worst_basket = _safe_float(baskets_profit.min() if len(baskets_profit) else 0.0)
    cost_total = _safe_float(pd.to_numeric(trades_df.get('commission'), errors='coerce').fillna(0.0).sum() + pd.to_numeric(trades_df.get('swap'), errors='coerce').fillna(0.0).sum() if len(trades_df) else 0.0)
    best_score = _safe_float(pd.to_numeric(optimization_df.get('optimization_score'), errors='coerce').max() if len(optimization_df) else 0.0)
    robust_pct = _safe_float(
        pd.to_numeric(optimization_df.get('is_robust'), errors='coerce').fillna(0.0).mean() * 100
        if len(optimization_df) and 'is_robust' in optimization_df.columns else 0.0
    )

    def add_finding(severity: str, title: str, evidence: str, mq5_hint: str):
        findings.append({
            'severity': severity,
            'title': title,
            'evidence': evidence,
            'mq5_hint': mq5_hint,
        })

    def add_recommendation(priority: str, title: str, rationale: str, mq5_change: str):
        recommendations.append({
            'priority': priority,
            'title': title,
            'rationale': rationale,
            'mq5_change': mq5_change,
        })

    if net_profit < 0:
        add_finding(
            'high',
            'Resultado líquido negativo',
            f'Os trades importados somam {net_profit:.2f}, sinal de que a lógica atual do EA ainda não compensa o risco assumido.',
            'Reveja a lógica de entrada e o escape de baskets perdedores antes de ampliar lote ou níveis.'
        )
        add_recommendation(
            'high',
            'Adicionar freio de continuidade',
            'Quando o lucro líquido está negativo, insistir no mesmo grid costuma amplificar drawdown e custo.',
            'Implemente trava por perda diária/sequencial e bloqueio temporário após baskets de perda forte.'
        )

    if stop_rate >= 20:
        add_finding(
            'high',
            'Taxa de stop elevada',
            f'{stop_rate:.1f}% dos baskets bateram stop loss, indicando que o grid está sendo esticado demais em contexto adverso.',
            'Teste menos níveis, grid mais largo ou filtro de tendência antes de abrir novas camadas.'
        )
        add_recommendation(
            'high',
            'Reduzir agressividade do grid',
            'Muitos stops sugerem que o EA está insistindo em recuperação quando o mercado não voltou.',
            'Diminua `max_levels`, reavalie `grid spacing` e crie stop estrutural por distância/ADX.'
        )

    if avg_levels >= 4:
        add_finding(
            'medium',
            'Escalonamento frequente do basket',
            f'A média de {avg_levels:.1f} trades por basket mostra que o EA costuma aprofundar a grade para resolver a operação.',
            'Vale revisar a regra da segunda/terceira entrada e exigir confirmação antes de aumentar exposição.'
        )
        add_recommendation(
            'medium',
            'Endurecer gatilho de novas entradas',
            'Entradas adicionais muito fáceis elevam o risco em movimentos direcionais.',
            'No MQ5, adicione distância mínima dinâmica, filtro de volatilidade e limite de frequência entre níveis.'
        )

    if median_exposure >= 8:
        add_finding(
            'medium',
            'Baskets ficam tempo demais em aberto',
            f'A mediana de sobrevivência está em {median_exposure:.1f}h, o que aumenta swap, risco noturno e stress operacional.',
            'Teste timeout de basket, redução progressiva de risco ao longo do tempo ou saída parcial.'
        )
        add_recommendation(
            'medium',
            'Adicionar time stop operacional',
            'Baskets longos tendem a concentrar risco e depender demais da sorte do retorno à média.',
            'Crie no EA um limite máximo de horas por basket com redução de lote ou encerramento assistido.'
        )

    if phantom_rate >= 10:
        add_finding(
            'medium',
            'Presença relevante de phantom winners',
            f'{phantom_rate:.1f}% dos baskets parecem ter fechado no lucro mesmo após excursão adversa significativa.',
            'Isso costuma mascarar fragilidade do grid e esconder risco real de cauda.'
        )

    if avg_mae > max(abs(net_profit) * 0.1, 100):
        add_finding(
            'high',
            'Excursão adversa alta por basket',
            f'O Basket MAE médio está em {avg_mae:.2f}, sugerindo que o EA sofre bastante antes de recuperar.',
            'Use sizing mais conservador, spacing adaptativo e regras de desligamento em tendência forte.'
        )

    if worst_basket < -1000:
        add_finding(
            'high',
            'Cauda de perda pesada',
            f'O pior basket importado perdeu {worst_basket:.2f}, sinal claro de que eventos extremos ainda machucam demais a estratégia.',
            'Implemente kill switch por perda do basket e trava de abertura em ADX/tendência forte.'
        )

    if cost_total < -50:
        add_finding(
            'medium',
            'Custos operacionais relevantes',
            f'Comissões e swaps somados pesaram {cost_total:.2f} no resultado observado.',
            'Evite baskets longos e entradas excessivas em horários menos líquidos.'
        )

    if len(market_df) == 0:
        add_finding(
            'medium',
            'Sem contexto completo de mercado',
            'Há trades e baskets, mas faltam barras suficientes para cruzar regime, volatilidade e qualidade de entrada.',
            'Sincronize também market data do MT5 para calibrar filtros de regime no MQ5.'
        )

    if len(optimization_df) > 0 and robust_pct < 5:
        add_finding(
            'medium',
            'Região otimizada pouco robusta',
            f'Apenas {robust_pct:.1f}% das configurações ficaram robustas, indicando sensibilidade excessiva a pequenas mudanças.',
            'No MQ5, prefira parâmetros mais conservadores e filtros estáveis em vez do melhor score isolado.'
        )

    if len(optimization_df) > 0:
        add_recommendation(
            'medium',
            'Promover parâmetros robustos, não só o campeão',
            f'O melhor score atual foi {best_score:.1f}, mas a leitura útil para o EA é estabilidade da vizinhança.',
            'Ao ajustar o MQ5, teste a melhor configuração e também 2 ou 3 vizinhas próximas antes de escolher a final.'
        )

    if not recommendations:
        add_recommendation(
            'medium',
            'Coletar mais histórico real',
            'Sem mais dispersão de dados fica difícil separar problema estrutural de ruído amostral.',
            'Rode mais backtests reais e sincronize períodos diferentes antes da próxima rodada de tuning.'
        )

    return findings, recommendations


def _build_mq5_diagnostics_report(symbol: str):
    session = get_session(engine)
    try:
        df_market = _load_symbol_frame(session, 'market_data', symbol, order_by='timestamp')
        df_trades = _load_symbol_frame(session, 'trades', symbol, order_by='timestamp_open')
        df_baskets = _load_symbol_frame(session, 'grid_sequences', symbol, order_by='timestamp_start')
        try:
            df_optimization = pd.read_sql(
                text("SELECT * FROM optimization_results ORDER BY optimization_score DESC"),
                session.bind
            )
        except Exception:
            df_optimization = pd.DataFrame()
    finally:
        session.close()

    if len(df_trades) == 0 and len(df_baskets) == 0:
        raise ValueError('Não há trades ou baskets suficientes para montar o diagnóstico do MQ5.')

    if len(df_baskets) > 0:
        df_baskets['timestamp_start'] = pd.to_datetime(df_baskets['timestamp_start'], errors='coerce')
        df_baskets['timestamp_end'] = pd.to_datetime(df_baskets['timestamp_end'], errors='coerce')
        df_baskets['exposure_time_hours'] = (
            df_baskets['timestamp_end'] - df_baskets['timestamp_start']
        ).dt.total_seconds() / 3600

    trades_profit = pd.to_numeric(df_trades.get('profit'), errors='coerce').fillna(0.0) if len(df_trades) else pd.Series(dtype=float)
    baskets_profit = pd.to_numeric(df_baskets.get('realized_profit', df_baskets.get('total_profit')), errors='coerce').fillna(0.0) if len(df_baskets) else pd.Series(dtype=float)
    exposure_hours = pd.to_numeric(df_baskets.get('exposure_time_hours'), errors='coerce').fillna(0.0) if len(df_baskets) else pd.Series(dtype=float)

    if len(df_baskets) > 0 and 'regime_at_start' in df_baskets.columns:
        regime_breakdown = (
            df_baskets.assign(realized_profit=baskets_profit)
            .groupby('regime_at_start')
            .agg(
                baskets=('basket_id', 'count'),
                avg_profit=('realized_profit', 'mean'),
                median_hours=('exposure_time_hours', 'median'),
                stop_rate=('hit_stop_loss', 'mean'),
            )
            .reset_index()
            .sort_values('avg_profit')
        )
        regime_records = []
        for _, row in regime_breakdown.iterrows():
            regime_records.append({
                'regime': row['regime_at_start'] or 'Unknown',
                'baskets': _safe_int(row['baskets']),
                'avg_profit': _safe_float(row['avg_profit']),
                'median_hours': _safe_float(row['median_hours']),
                'stop_rate_pct': _safe_float(row['stop_rate'] * 100),
            })
    else:
        regime_records = []

    top_losses = []
    if len(df_baskets) > 0:
        worst_df = df_baskets.assign(realized_profit=baskets_profit).sort_values('realized_profit').head(5)
        for _, row in worst_df.iterrows():
            top_losses.append({
                'basket_id': row.get('basket_id'),
                'profit': _safe_float(row.get('realized_profit')),
                'mae': _safe_float(row.get('basket_mae')),
                'levels': _safe_int(row.get('total_trades')),
                'duration_hours': _safe_float(row.get('exposure_time_hours')),
                'regime': row.get('regime_at_start') or 'Unknown',
            })

    parameter_snapshot = {
        'avg_grid_pips': _safe_float(pd.to_numeric(df_baskets.get('grid_spacing_pips'), errors='coerce').mean() if len(df_baskets) else 0.0),
        'avg_multiplier': _safe_float(pd.to_numeric(df_baskets.get('lot_multiplier'), errors='coerce').mean() if len(df_baskets) else 0.0),
        'avg_max_levels_seen': _safe_float(pd.to_numeric(df_baskets.get('total_trades'), errors='coerce').mean() if len(df_baskets) else 0.0),
        'avg_atr_filter': _safe_float(pd.to_numeric(df_baskets.get('atr_filter'), errors='coerce').mean() if len(df_baskets) else 0.0),
    }

    best_config = None
    if len(df_optimization) > 0:
        best_row = df_optimization.iloc[0]
        best_config = {
            'grid_pips': _safe_int(best_row.get('grid_pips')),
            'multiplier': _safe_float(best_row.get('multiplier')),
            'atr_filter': _safe_float(best_row.get('atr_filter')),
            'max_levels': _safe_int(best_row.get('max_levels')),
            'score': _safe_float(best_row.get('optimization_score')),
        }

    findings, recommendations = _build_diagnostic_findings(
        df_trades, df_baskets, df_market, df_optimization
    )

    report = {
        'summary': {
            'symbol': symbol,
            'market_bars': _safe_int(len(df_market)),
            'trades': _safe_int(len(df_trades)),
            'baskets': _safe_int(len(df_baskets)),
            'net_profit': _safe_float(trades_profit.sum()),
            'trade_win_rate_pct': _safe_float((trades_profit > 0).mean() * 100 if len(trades_profit) else 0.0),
            'basket_win_rate_pct': _safe_float((baskets_profit > 0).mean() * 100 if len(baskets_profit) else 0.0),
            'median_basket_hours': _safe_float(exposure_hours.median() if len(exposure_hours) else 0.0),
            'stop_rate_pct': _safe_float(pd.to_numeric(df_baskets.get('hit_stop_loss'), errors='coerce').fillna(0.0).mean() * 100 if len(df_baskets) else 0.0),
            'phantom_winner_pct': _safe_float(pd.to_numeric(df_baskets.get('phantom_winner'), errors='coerce').fillna(0.0).mean() * 100 if len(df_baskets) else 0.0),
            'avg_basket_mae': _safe_float(pd.to_numeric(df_baskets.get('basket_mae'), errors='coerce').fillna(0.0).mean() if len(df_baskets) else 0.0),
            'worst_basket_profit': _safe_float(baskets_profit.min() if len(baskets_profit) else 0.0),
        },
        'parameter_snapshot': parameter_snapshot,
        'optimization_context': {
            'configs_tested': _safe_int(len(df_optimization)),
            'best_config': best_config,
        },
        'regime_breakdown': regime_records,
        'top_loss_baskets': top_losses,
        'findings': findings,
        'recommendations': recommendations,
    }

    return _json_safe(report)

# =============================================================================
# Health Check
# =============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'version': '1.2.0',
        'timestamp': datetime.now().isoformat()
    })

# =============================================================================
# Data Import Endpoints
# =============================================================================

@app.route('/api/import/market-data', methods=['POST'])
def import_market_data():
    """Importa dados de mercado de CSV"""
    temp_path = None
    try:
        if 'file' in request.files:
            uploaded_file = request.files['file']
            symbol = request.form.get('symbol', 'XAUUSD')
            if not uploaded_file or not uploaded_file.filename:
                return jsonify({'error': 'Arquivo é obrigatório'}), 400
            temp_path = _persist_uploaded_file(uploaded_file)
            csv_path = temp_path
        else:
            data = request.get_json(silent=True) or {}
            csv_path = data.get('csv_path')
            symbol = data.get('symbol', 'XAUUSD')
        
        if not csv_path:
            return jsonify({'error': 'csv_path é obrigatório'}), 400
        
        importer = MT5DataImporter(DB_PATH)
        df = importer.import_market_data_from_csv(csv_path, symbol)
        importer.disconnect()
        
        return jsonify({
            'success': True,
            'records_imported': len(df),
            'date_range': {
                'from': df['timestamp'].min().isoformat(),
                'to': df['timestamp'].max().isoformat()
            }
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

@app.route('/api/import/trades', methods=['POST'])
def import_trades():
    """Importa trades de CSV"""
    temp_path = None
    try:
        if 'file' in request.files:
            uploaded_file = request.files['file']
            symbol = request.form.get('symbol', 'XAUUSD')
            if not uploaded_file or not uploaded_file.filename:
                return jsonify({'error': 'Arquivo é obrigatório'}), 400
            temp_path = _persist_uploaded_file(uploaded_file)
            csv_path = temp_path
            original_name = (uploaded_file.filename or '').lower()
        else:
            data = request.get_json(silent=True) or {}
            csv_path = data.get('csv_path')
            symbol = data.get('symbol', 'XAUUSD')
            original_name = str(csv_path or '').lower()
        
        if not csv_path:
            return jsonify({'error': 'csv_path é obrigatório'}), 400
        
        importer = MT5DataImporter(DB_PATH)
        if original_name.endswith(('.html', '.htm')):
            result = importer.import_mt5_report(csv_path, symbol)
            df = result['trades']
        else:
            df = importer.import_trades_from_csv(csv_path, symbol)
        importer.disconnect()
        
        return jsonify({
            'success': True,
            'records_imported': len(df),
            'baskets_reconstructed': int(df['basket_id'].nunique()) if 'basket_id' in df.columns else 0,
            'total_profit': float(pd.to_numeric(df['profit'], errors='coerce').fillna(0).sum()) if 'profit' in df.columns else 0
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

# =============================================================================
# Regime Detection Endpoints
# =============================================================================

@app.route('/api/regime/analyze', methods=['POST'])
def analyze_regime():
    """Analisa regime de mercado"""
    try:
        data = request.json
        symbol = data.get('symbol', 'XAUUSD')
        
        # Carregar dados de mercado
        session = get_session(engine)
        
        df = _load_symbol_frame(session, 'market_data', symbol, order_by='timestamp')
        
        if len(df) == 0:
            return jsonify({'error': 'Dados de mercado não encontrados'}), 404
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        # Analisar regime
        regime_engine = RegimeDetectionEngine()
        df = regime_engine.analyze(df)
        
        # Último regime
        latest = df.iloc[-1]
        
        # Estatísticas por regime
        regime_stats = df.groupby('regime_class').agg({
            'hurst_exponent': 'mean',
            'adx': 'mean',
            'close': 'count'
        }).reset_index()
        
        session.close()
        
        return jsonify(_json_safe({
            'current_regime': {
                'regime_class': str(latest['regime_class']),
                'hurst_exponent': float(latest['hurst_exponent']) if not pd.isna(latest['hurst_exponent']) else None,
                'adx': float(latest['adx']) if not pd.isna(latest['adx']) else None,
                'ema_slope': float(latest['ema_slope']) if not pd.isna(latest.get('ema_slope')) else None,
                'timestamp': df.index[-1].isoformat()
            },
            'regime_distribution': regime_stats.to_dict('records'),
            'interpretation': regime_engine.hurst_calc.interpret(latest['hurst_exponent']) if not pd.isna(latest['hurst_exponent']) else 'Unknown'
        }))
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/regime/profit-matrix', methods=['GET'])
def get_profit_matrix():
    """Retorna Profit Matrix por Regime"""
    try:
        symbol = request.args.get('symbol', 'XAUUSD')
        
        session = get_session(engine)
        
        # Carregar dados
        df_market = _load_symbol_frame(session, 'market_data', symbol, order_by='timestamp')
        df_trades = _load_symbol_frame(session, 'trades', symbol)
        
        if len(df_market) == 0 or len(df_trades) == 0:
            return jsonify({'error': 'Dados insuficientes'}), 404
        
        # Analisar regime
        regime_engine = RegimeDetectionEngine()
        df_market['timestamp'] = pd.to_datetime(df_market['timestamp'])
        df_market.set_index('timestamp', inplace=True)
        df_market = regime_engine.analyze(df_market)
        
        # Gerar profit matrix
        df_trades['timestamp_open'] = pd.to_datetime(df_trades['timestamp_open'])
        
        regime_matrix = regime_engine.get_regime_statistics(df_market, df_trades)
        insights = regime_engine.generate_insight(regime_matrix)
        
        session.close()
        
        return jsonify(_json_safe({
            'profit_matrix': regime_matrix.to_dict('records'),
            'insights': insights
        }))
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =============================================================================
# Survival Analysis Endpoints
# =============================================================================

@app.route('/api/survival/analyze', methods=['POST'])
def analyze_survival():
    """Analisa sobrevivência de baskets"""
    try:
        data = request.json
        symbol = data.get('symbol', 'XAUUSD')
        regime_filter = data.get('regime_filter')  # Opcional
        
        session = get_session(engine)
        
        # Carregar baskets
        df_baskets = _load_symbol_frame(session, 'grid_sequences', symbol)
        
        if len(df_baskets) == 0:
            return jsonify({'error': 'Baskets não encontrados'}), 404
        
        # Calcular tempo de exposição
        df_baskets['timestamp_start'] = pd.to_datetime(df_baskets['timestamp_start'])
        df_baskets['timestamp_end'] = pd.to_datetime(df_baskets['timestamp_end'])
        
        df_baskets['exposure_time_hours'] = (
            df_baskets['timestamp_end'] - df_baskets['timestamp_start']
        ).dt.total_seconds() / 3600
        
        df_baskets['hit_stop_loss'] = df_baskets['hit_stop_loss'].fillna(False)
        
        # Analisar sobrevivência
        survival_engine = SurvivalAnalysisEngine()
        curve = survival_engine.analyze_baskets(df_baskets, regime_filter)
        
        # Gerar sugestão de time stop
        suggestion = survival_engine.generate_time_stop_suggestion(curve)
        
        session.close()
        
        return jsonify(_json_safe({
            'survival_curve': {
                'time_hours': curve.time_hours.tolist(),
                'survival_probability': curve.survival_prob.tolist(),
                'hazard_rate': curve.hazard_rate.tolist(),
                'confidence_lower': curve.confidence_lower.tolist(),
                'confidence_upper': curve.confidence_upper.tolist()
            },
            'statistics': {
                'sample_size': curve.sample_size,
                'median_survival_time': curve.median_survival_time,
                'regime_filter': curve.regime_filter
            },
            'time_stop_suggestion': suggestion
        }))
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =============================================================================
# Robustness Mapping Endpoints
# =============================================================================

@app.route('/api/robustness/analyze', methods=['POST'])
def analyze_robustness():
    """Analisa robustez paramétrica"""
    global optimization_results_cache
    
    try:
        data = request.json
        
        # Usar resultados em cache ou carregar do banco
        if optimization_results_cache is None:
            session = get_session(engine)
            query = "SELECT * FROM optimization_results"
            optimization_results_cache = pd.read_sql(query, session.bind)
            session.close()
        
        if len(optimization_results_cache) == 0:
            return jsonify({'error': 'Resultados de otimização não encontrados'}), 404
        
        landscape_builder = RobustnessLandscape()
        landscape = _build_robustness_landscape_frame(optimization_results_cache)
        
        # Encontrar zonas robustas
        robust_zones = landscape_builder.find_robust_zones(landscape)
        
        # Encontrar picos de overfitting
        overfitting_peaks = landscape_builder.find_overfitting_peaks(landscape)
        
        # Gerar recomendação
        current_config = data.get('current_config')
        recommendation = landscape_builder.generate_recommendation(landscape, current_config)
        
        return jsonify(_json_safe({
            'landscape_summary': {
                'total_configs': len(landscape),
                'robust_configs': len(landscape[landscape['is_robust'] == True]),
                'best_score': float(landscape['optimization_score'].max()),
                'avg_stability': float(landscape['neighbor_stability_pct'].mean())
            },
            'robust_zones': robust_zones[:5],
            'overfitting_warnings': overfitting_peaks[:5],
            'recommendation': recommendation
        }))
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/robustness/surface-data', methods=['GET'])
def get_surface_data():
    """Retorna dados para plotagem 3D da superfície"""
    try:
        global optimization_results_cache
        
        if optimization_results_cache is None:
            session = get_session(engine)
            query = "SELECT * FROM optimization_results"
            optimization_results_cache = pd.read_sql(query, session.bind)
            session.close()
        
        df = _build_robustness_landscape_frame(optimization_results_cache)
        if len(df) == 0:
            return jsonify({'surface_data': []})

        # Agrupar por grid e multiplier (média de ATR)
        surface_data = df.groupby(['grid_pips', 'multiplier']).agg({
            'optimization_score': 'mean',
            'neighbor_stability_pct': 'mean',
            'is_robust': 'first'
        }).reset_index()
        
        return jsonify(_json_safe({
            'surface_data': surface_data.to_dict('records')
        }))
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =============================================================================
# Optimization Endpoints
# =============================================================================

@app.route('/api/optimization/run', methods=['POST'])
def run_optimization():
    """Executa otimização de parâmetros"""
    global optimization_results_cache
    
    try:
        data = request.json
        symbol = data.get('symbol', 'XAUUSD')
        
        # Carregar dados de mercado
        session = get_session(engine)
        df_market = _load_symbol_frame(session, 'market_data', symbol, order_by='timestamp')
        df_baskets = _load_symbol_frame(session, 'grid_sequences', symbol)
        session.close()
        
        if len(df_market) == 0:
            return jsonify({'error': 'Dados de mercado não encontrados'}), 404
        
        df_market['timestamp'] = pd.to_datetime(df_market['timestamp'])
        df_market.set_index('timestamp', inplace=True)
        
        # Configurar espaço de busca
        param_grid = data.get('param_grid', {
            'grid_pips': list(range(200, 501, 20)),
            'multiplier': [round(x, 2) for x in np.arange(1.2, 1.61, 0.05)],
            'atr_filter': [round(x, 1) for x in np.arange(1.0, 2.1, 0.2)],
            'max_levels': [5, 8, 10, 12]
        })
        
        # Em produção, a otimização só deve usar evidência real do EA.
        historical_baskets = df_baskets if len(df_baskets) > 0 else None
        if historical_baskets is None or len(historical_baskets) < 10:
            return jsonify({
                'error': 'A otimização real exige baskets históricos suficientes do EA. Importe trades reais até gerar pelo menos 10 baskets.'
            }), 400

        opt_engine = OptimizationEngine(df_market, historical_baskets=historical_baskets)
        if opt_engine.historical_baskets is None or len(opt_engine.historical_baskets) < 10:
            return jsonify({
                'error': 'Os baskets foram encontrados, mas não têm lucro realizado/total utilizável para a otimização. Reimporte os trades reais ou regenere os baskets.'
            }), 400
        
        best_config, best_metrics, all_results = opt_engine.optimize(
            param_grid=param_grid,
            verbose=False
        )
        
        # Salvar resultados
        all_results['data_source'] = 'historical_baskets'
        optimization_results_cache = all_results
        
        # Salvar no banco
        session = get_session(engine)
        all_results.to_sql('optimization_results', session.bind, if_exists='replace', index=False)
        session.close()
        
        return jsonify(_json_safe({
            'data_source': 'historical_baskets',
            'historical_basket_count': int(len(historical_baskets)),
            'best_config': {
                'grid_pips': best_config.grid_pips,
                'multiplier': best_config.multiplier,
                'atr_filter': best_config.atr_filter,
                'max_levels': best_config.max_levels
            },
            'best_metrics': {
                'total_return': best_metrics.total_return,
                'profit_factor': best_metrics.profit_factor,
                'sharpe_ratio': best_metrics.sharpe_ratio,
                'ulcer_index': best_metrics.ulcer_index,
                'cvar_95': best_metrics.cvar_95,
                'max_drawdown_pct': best_metrics.max_drawdown_pct,
                'win_rate': best_metrics.win_rate,
                'optimization_score': best_metrics.optimization_score
            },
            'total_configs_tested': len(all_results)
        }))
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/optimization/results', methods=['GET'])
def get_optimization_results():
    """Retorna resultados da otimização"""
    try:
        global optimization_results_cache
        
        if optimization_results_cache is None:
            session = get_session(engine)
            query = "SELECT * FROM optimization_results ORDER BY optimization_score DESC"
            optimization_results_cache = pd.read_sql(query, session.bind)
            session.close()
        
        # Paginação
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        start = (page - 1) * per_page
        end = start + per_page
        
        results_page = optimization_results_cache.iloc[start:end]
        
        return jsonify(_json_safe({
            'results': results_page.to_dict('records'),
            'total': len(optimization_results_cache),
            'page': page,
            'per_page': per_page,
            'total_pages': (len(optimization_results_cache) + per_page - 1) // per_page
        }))
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =============================================================================
# Dashboard Endpoints
# =============================================================================

@app.route('/api/dashboard/summary', methods=['GET'])
def get_dashboard_summary():
    """Retorna resumo para dashboard"""
    try:
        session = get_session(engine)
        
        summary = {}
        
        # Contagens
        cursor = session.execute(text("SELECT COUNT(*) FROM market_data"))
        summary['market_data_count'] = cursor.fetchone()[0]
        
        cursor = session.execute(text("SELECT COUNT(*) FROM trades"))
        summary['trades_count'] = cursor.fetchone()[0]
        
        cursor = session.execute(text("SELECT COUNT(*) FROM grid_sequences"))
        summary['baskets_count'] = cursor.fetchone()[0]
        
        cursor = session.execute(text("SELECT COUNT(*) FROM optimization_results"))
        summary['optimization_configs'] = cursor.fetchone()[0]
        
        # Performance agregada
        cursor = session.execute(text("""
            SELECT 
                SUM(total_return) as total_profit,
                AVG(profit_factor) as avg_pf,
                AVG(win_rate) as avg_wr
            FROM optimization_results
            WHERE optimization_score > 0
        """))
        row = cursor.fetchone()
        summary['total_profit'] = float(row[0]) if row[0] else 0
        summary['avg_profit_factor'] = float(row[1]) if row[1] else 0
        summary['avg_win_rate'] = float(row[2]) if row[2] else 0
        
        session.close()
        
        return jsonify(_json_safe(summary))
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# MQ5 Diagnostics Endpoint
# =============================================================================

@app.route('/api/diagnostics/mq5', methods=['GET'])
def get_mq5_diagnostics():
    """Retorna diagnóstico operacional para melhorar o EA/MQ5."""
    try:
        symbol = request.args.get('symbol', 'XAUUSD')
        return jsonify(_build_mq5_diagnostics_report(symbol))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =============================================================================
# Main
# =============================================================================

if __name__ == '__main__':
    app.run(
        debug=os.getenv("FLASK_DEBUG", "").lower() == "true",
        host='0.0.0.0',
        port=int(os.getenv("PORT", "5000"))
    )
