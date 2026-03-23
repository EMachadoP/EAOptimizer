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
from sqlalchemy import text

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
        "https://ea-optimizer-h2f54hu0z-eldons-projects-3194802d.vercel.app",
    ]


CORS(app, resources={r"/api/*": {"origins": get_allowed_origins()}})

# Inicializar banco de dados
DB_PATH = resolve_db_path()
engine = init_database(DB_PATH)

# Cache de dados
market_data_cache = {}
optimization_results_cache = None

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
    try:
        data = request.json
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

@app.route('/api/import/trades', methods=['POST'])
def import_trades():
    """Importa trades de CSV"""
    try:
        data = request.json
        csv_path = data.get('csv_path')
        symbol = data.get('symbol', 'XAUUSD')
        
        if not csv_path:
            return jsonify({'error': 'csv_path é obrigatório'}), 400
        
        importer = MT5DataImporter(DB_PATH)
        df = importer.import_trades_from_csv(csv_path, symbol)
        importer.disconnect()
        
        return jsonify({
            'success': True,
            'records_imported': len(df),
            'total_profit': float(df['profit'].sum()) if 'profit' in df.columns else 0
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        
        query = """
            SELECT * FROM market_data 
            WHERE symbol = ? 
            ORDER BY timestamp
        """
        df = pd.read_sql(query, session.bind, params=(symbol,))
        
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
        
        return jsonify({
            'current_regime': {
                'regime_class': str(latest['regime_class']),
                'hurst_exponent': float(latest['hurst_exponent']) if not pd.isna(latest['hurst_exponent']) else None,
                'adx': float(latest['adx']) if not pd.isna(latest['adx']) else None,
                'ema_slope': float(latest['ema_slope']) if not pd.isna(latest.get('ema_slope')) else None,
                'timestamp': df.index[-1].isoformat()
            },
            'regime_distribution': regime_stats.to_dict('records'),
            'interpretation': regime_engine.hurst_calc.interpret(latest['hurst_exponent']) if not pd.isna(latest['hurst_exponent']) else 'Unknown'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/regime/profit-matrix', methods=['GET'])
def get_profit_matrix():
    """Retorna Profit Matrix por Regime"""
    try:
        symbol = request.args.get('symbol', 'XAUUSD')
        
        session = get_session(engine)
        
        # Carregar dados
        market_query = """
            SELECT * FROM market_data 
            WHERE symbol = ? 
            ORDER BY timestamp
        """
        df_market = pd.read_sql(market_query, session.bind, params=(symbol,))
        
        trades_query = """
            SELECT * FROM trades 
            WHERE symbol = ?
        """
        df_trades = pd.read_sql(trades_query, session.bind, params=(symbol,))
        
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
        
        return jsonify({
            'profit_matrix': regime_matrix.to_dict('records'),
            'insights': insights
        })
    
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
        query = """
            SELECT * FROM grid_sequences 
            WHERE symbol = ?
        """
        df_baskets = pd.read_sql(query, session.bind, params=(symbol,))
        
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
        
        return jsonify({
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
        })
    
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
        
        # Construir landscape
        landscape_builder = RobustnessLandscape()
        landscape = landscape_builder.build_landscape(optimization_results_cache)
        
        # Encontrar zonas robustas
        robust_zones = landscape_builder.find_robust_zones(landscape)
        
        # Encontrar picos de overfitting
        overfitting_peaks = landscape_builder.find_overfitting_peaks(landscape)
        
        # Gerar recomendação
        current_config = data.get('current_config')
        recommendation = landscape_builder.generate_recommendation(landscape, current_config)
        
        return jsonify({
            'landscape_summary': {
                'total_configs': len(landscape),
                'robust_configs': len(landscape[landscape['is_robust'] == True]),
                'best_score': float(landscape['optimization_score'].max()),
                'avg_stability': float(landscape['neighbor_stability_pct'].mean())
            },
            'robust_zones': robust_zones[:5],
            'overfitting_warnings': overfitting_peaks[:5],
            'recommendation': recommendation
        })
    
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
        
        # Preparar dados para 3D
        df = optimization_results_cache
        
        # Agrupar por grid e multiplier (média de ATR)
        surface_data = df.groupby(['grid_pips', 'multiplier']).agg({
            'optimization_score': 'mean',
            'neighbor_stability_pct': 'mean',
            'is_robust': 'first'
        }).reset_index()
        
        return jsonify({
            'surface_data': surface_data.to_dict('records')
        })
    
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
        query = """
            SELECT * FROM market_data 
            WHERE symbol = ? 
            ORDER BY timestamp
        """
        df_market = pd.read_sql(query, session.bind, params=(symbol,))
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
        
        # Executar otimização
        opt_engine = OptimizationEngine(df_market)
        
        best_config, best_metrics, all_results = opt_engine.optimize(
            param_grid=param_grid,
            verbose=False
        )
        
        # Salvar resultados
        optimization_results_cache = all_results
        
        # Salvar no banco
        session = get_session(engine)
        all_results.to_sql('optimization_results', session.bind, if_exists='replace', index=False)
        session.close()
        
        return jsonify({
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
        })
    
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
        
        return jsonify({
            'results': results_page.to_dict('records'),
            'total': len(optimization_results_cache),
            'page': page,
            'per_page': per_page,
            'total_pages': (len(optimization_results_cache) + per_page - 1) // per_page
        })
    
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
        
        return jsonify(summary)
    
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
