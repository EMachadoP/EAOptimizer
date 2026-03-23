#!/usr/bin/env python3
"""
EA Configuration Optimizer v1.2
System Tests

Valida os principais componentes do sistema.
"""

import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Ensure Windows consoles can render status output without crashing.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add backend to path
sys.path.append('backend')

def test_database():
    """Test database initialization"""
    print("\n" + "="*60)
    print("TEST: Database Initialization")
    print("="*60)
    
    try:
        from models.database import init_database, get_session
        
        engine = init_database("test.db")
        session = get_session(engine)
        
        print("✓ Database initialized successfully")
        print("✓ All tables created")
        
        session.close()
        engine.dispose()
        if os.path.exists("test.db"):
            os.remove("test.db")
        return True
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        return False

def test_trade_reconstruction():
    """Test trade reconstruction engine"""
    print("\n" + "="*60)
    print("TEST: Trade Reconstruction Engine")
    print("="*60)
    
    try:
        from core.trade_reconstruction import TradeReconstructionEngine
        
        engine = TradeReconstructionEngine(symbol="XAUUSD")
        
        # Create sample trades
        sample_trades = pd.DataFrame({
            'ticket': [1, 2, 3],
            'time_open': pd.date_range('2024-01-01', periods=3, freq='h'),
            'time_close': pd.date_range('2024-01-01 02:00', periods=3, freq='h'),
            'type': [0, 0, 1],
            'volume': [0.01, 0.02, 0.01],
            'price_open': [2050.0, 2049.5, 2051.0],
            'price_close': [2051.0, 2050.5, 2050.0],
            'commission': [-0.07, -0.14, -0.07],
            'swap': [0, 0, 0],
            'profit': [10.0, 10.0, -10.0]
        })
        
        grid_params = {
            'grid_spacing': 300,
            'lot_multiplier': 1.3,
            'max_levels': 10,
            'atr_filter': 1.5
        }
        
        # Create sample market data
        market_data = pd.DataFrame({
            'open': [2050.0, 2049.5, 2050.0],
            'high': [2051.0, 2050.5, 2051.0],
            'low': [2049.0, 2048.5, 2049.0],
            'close': [2050.5, 2050.0, 2050.5],
            'volume': [1000, 1200, 1100]
        }, index=pd.date_range('2024-01-01', periods=3, freq='h'))
        
        basket = engine.reconstruct_basket_from_mt5(
            sample_trades,
            grid_params,
            market_data
        )
        
        print(f"✓ Basket reconstructed: {basket.basket_id}")
        print(f"  - Total trades: {basket.total_trades}")
        print(f"  - Total profit: ${basket.total_profit:.2f}")
        print(f"  - Basket_MAE: ${basket.basket_mae:.2f}")
        
        return True
    except Exception as e:
        print(f"✗ Trade reconstruction test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_regime_detection():
    """Test regime detection engine"""
    print("\n" + "="*60)
    print("TEST: Regime Detection Engine")
    print("="*60)
    
    try:
        from core.regime_detection import RegimeDetectionEngine, HurstExponentCalculator
        
        # Create sample market data with mean-reverting behavior
        np.random.seed(42)
        returns = np.random.normal(0, 0.001, 200)
        prices = 2050 * np.exp(np.cumsum(returns))
        
        market_data = pd.DataFrame({
            'open': prices,
            'high': prices * 1.001,
            'low': prices * 0.999,
            'close': prices,
            'volume': np.random.randint(1000, 2000, 200)
        }, index=pd.date_range('2024-01-01', periods=200, freq='h'))
        
        engine = RegimeDetectionEngine()
        result = engine.analyze(market_data)
        
        print(f"✓ Regime analysis completed")
        print(f"  - Hurst Exponent: {result['hurst_exponent'].iloc[-1]:.3f}")
        print(f"  - ADX: {result['adx'].iloc[-1]:.2f}")
        print(f"  - Regime: {result['regime_class'].iloc[-1]}")
        
        return True
    except Exception as e:
        print(f"✗ Regime detection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_survival_analysis():
    """Test survival analysis engine"""
    print("\n" + "="*60)
    print("TEST: Survival Analysis Engine")
    print("="*60)
    
    try:
        from core.survival_analysis import SurvivalAnalysisEngine
        
        # Create sample basket data
        np.random.seed(42)
        n_baskets = 100
        
        baskets = pd.DataFrame({
            'exposure_time_hours': np.random.exponential(8, n_baskets),
            'hit_stop_loss': np.random.choice([True, False], n_baskets, p=[0.3, 0.7]),
            'regime_at_start': np.random.choice(
                ['Range_MeanRev', 'Range_Neutral', 'Trend_Weak', 'Trend_Strong'],
                n_baskets
            )
        })
        
        engine = SurvivalAnalysisEngine()
        curve = engine.analyze_baskets(baskets)
        
        print(f"✓ Survival analysis completed")
        print(f"  - Sample size: {curve.sample_size}")
        print(f"  - Median survival: {curve.median_survival_time:.1f}h")
        print(f"  - S(4h): {curve.survival_prob[min(3, len(curve.survival_prob)-1)]:.2%}")
        
        suggestion = engine.generate_time_stop_suggestion(curve)
        print(f"  - Suggested time stop: {suggestion['suggested_time_stop']:.1f}h")
        
        return True
    except Exception as e:
        print(f"✗ Survival analysis test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_robustness_mapping():
    """Test robustness mapping"""
    print("\n" + "="*60)
    print("TEST: Robustness Mapping")
    print("="*60)
    
    try:
        from core.robustness_mapping import RobustnessLandscape
        
        # Create sample optimization results
        np.random.seed(42)
        n_configs = 100
        
        results = pd.DataFrame({
            'grid_pips': np.random.choice(range(200, 501, 10), n_configs),
            'multiplier': np.random.choice([1.2, 1.3, 1.4, 1.5, 1.6], n_configs),
            'atr_filter': np.random.choice([1.0, 1.5, 2.0], n_configs),
            'optimization_score': np.random.beta(2, 5, n_configs) * 100
        })
        
        landscape = RobustnessLandscape()
        robustness_data = landscape.build_landscape(results, fixed_atr=1.5)
        robust_zones = landscape.find_robust_zones(robustness_data)
        
        print(f"✓ Robustness mapping completed")
        print(f"  - Total configs: {len(robustness_data)}")
        print(f"  - Robust zones found: {len(robust_zones)}")
        
        if len(robust_zones) > 0:
            print(f"  - Best zone score: {robust_zones[0]['optimization_score']:.1f}")
        
        return True
    except Exception as e:
        print(f"✗ Robustness mapping test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_optimization_engine():
    """Test optimization engine"""
    print("\n" + "="*60)
    print("TEST: Optimization Engine")
    print("="*60)
    
    try:
        from core.optimization_engine import (
            OptimizationEngine, 
            OptimizationConfig,
            RiskMetricsCalculator
        )
        
        # Create sample market data
        np.random.seed(42)
        n_bars = 252
        
        returns = np.random.normal(0.0001, 0.01, n_bars)
        prices = 2050 * np.exp(np.cumsum(returns))
        
        market_data = pd.DataFrame({
            'open': prices,
            'high': prices * 1.01,
            'low': prices * 0.99,
            'close': prices,
            'volume': np.random.randint(1000, 2000, n_bars)
        }, index=pd.date_range('2024-01-01', periods=n_bars, freq='h'))
        
        # Test risk metrics
        risk_calc = RiskMetricsCalculator()
        
        sample_returns = np.random.normal(100, 200, 100)
        ulcer = risk_calc.calculate_ulcer_index(sample_returns)
        cvar = risk_calc.calculate_cvar(sample_returns)
        sharpe = risk_calc.calculate_sharpe_ratio(sample_returns)
        
        print(f"✓ Risk metrics calculated")
        print(f"  - Ulcer Index: {ulcer:.2f}")
        print(f"  - CVaR 95%: ${cvar:.2f}")
        print(f"  - Sharpe Ratio: {sharpe:.2f}")
        
        # Test optimization
        engine = OptimizationEngine(market_data)
        config = OptimizationConfig(
            grid_pips=300,
            multiplier=1.3,
            atr_filter=1.5,
            max_levels=10
        )
        
        metrics = engine.evaluate_config(config)
        
        print(f"✓ Config evaluated")
        print(f"  - Total Return: ${metrics.total_return:.2f}")
        print(f"  - Profit Factor: {metrics.profit_factor:.2f}")
        print(f"  - Optimization Score: {metrics.optimization_score:.1f}")
        
        return True
    except Exception as e:
        print(f"✗ Optimization engine test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_slippage_model():
    """Test slippage model"""
    print("\n" + "="*60)
    print("TEST: Slippage Model")
    print("="*60)
    
    try:
        from core.slippage_model import SlippageModel
        
        model = SlippageModel(symbol="XAUUSD")
        
        # Test single trade slippage
        estimate = model.estimate_slippage(
            volume=0.5,
            hour_of_day=14,
            atr_14=1.2
        )
        
        print(f"✓ Slippage estimate calculated")
        print(f"  - Expected slippage: {estimate.expected_slippage_pips:.2f} pips")
        print(f"  - Std dev: {estimate.slippage_std:.2f} pips")
        print(f"  - 95% CI: [{estimate.confidence_interval[0]:.2f}, {estimate.confidence_interval[1]:.2f}]")
        
        # Test chain execution
        volumes = [0.01, 0.013, 0.017, 0.022]
        estimates = model.estimate_chain_slippage(volumes, hour_of_day=14)
        
        print(f"✓ Chain slippage calculated")
        print(f"  - Trades in chain: {len(estimates)}")
        print(f"  - First trade: {estimates[0].expected_slippage_pips:.2f} pips")
        print(f"  - Last trade: {estimates[-1].expected_slippage_pips:.2f} pips")
        
        return True
    except Exception as e:
        print(f"✗ Slippage model test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("EA Configuration Optimizer v1.2 - System Tests")
    print("="*60)
    
    tests = [
        ("Database", test_database),
        ("Trade Reconstruction", test_trade_reconstruction),
        ("Regime Detection", test_regime_detection),
        ("Survival Analysis", test_survival_analysis),
        ("Robustness Mapping", test_robustness_mapping),
        ("Optimization Engine", test_optimization_engine),
        ("Slippage Model", test_slippage_model),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} test crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n🎉 All tests passed! System is ready.")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed. Please review.")
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
