import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { apiUrl } from '@/lib/api';
import { 
  TrendingUp, 
  TrendingDown, 
  Activity, 
  BarChart3, 
  Shield,
  Clock,
  DollarSign,
  Target
} from 'lucide-react';

interface DashboardStats {
  market_data_count: number;
  trades_count: number;
  baskets_count: number;
  optimization_configs: number;
  total_profit: number;
  avg_profit_factor: number;
  avg_win_rate: number;
}

interface RegimeStatus {
  current_regime: {
    regime_class: string;
    hurst_exponent: number;
    adx: number;
    timestamp: string;
  };
  interpretation: string;
}

export default function DashboardSummary() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [regime, setRegime] = useState<RegimeStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      // Fetch summary
      const summaryRes = await fetch(apiUrl('/api/dashboard/summary'));
      if (summaryRes.ok) {
        const summaryData = await summaryRes.json();
        setStats(summaryData);
      }

      // Fetch regime
      const regimeRes = await fetch(apiUrl('/api/regime/analyze'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: 'XAUUSD' })
      });
      if (regimeRes.ok) {
        const regimeData = await regimeRes.json();
        setRegime(regimeData);
      }
    } catch (e) {
      console.error('Error fetching dashboard data:', e);
    } finally {
      setLoading(false);
    }
  };

  const getRegimeColor = (regimeClass: string) => {
    if (regimeClass?.includes('MeanRev')) return 'bg-green-500';
    if (regimeClass?.includes('Trend_Strong')) return 'bg-red-500';
    if (regimeClass?.includes('Trend')) return 'bg-yellow-500';
    return 'bg-blue-500';
  };

  const getRegimeIcon = (regimeClass: string) => {
    if (regimeClass?.includes('MeanRev')) return <TrendingUp className="w-5 h-5" />;
    if (regimeClass?.includes('Trend_Strong')) return <TrendingDown className="w-5 h-5" />;
    return <Activity className="w-5 h-5" />;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Status Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="bg-slate-900 border-slate-800">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">Market Data</p>
                <p className="text-2xl font-bold text-white">
                  {stats?.market_data_count?.toLocaleString() || 0}
                </p>
                <p className="text-xs text-slate-500">bars imported</p>
              </div>
              <div className="p-3 bg-blue-500/10 rounded-lg">
                <BarChart3 className="w-6 h-6 text-blue-500" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">Trades</p>
                <p className="text-2xl font-bold text-white">
                  {stats?.trades_count?.toLocaleString() || 0}
                </p>
                <p className="text-xs text-slate-500">executed</p>
              </div>
              <div className="p-3 bg-green-500/10 rounded-lg">
                <Activity className="w-6 h-6 text-green-500" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">Baskets</p>
                <p className="text-2xl font-bold text-white">
                  {stats?.baskets_count?.toLocaleString() || 0}
                </p>
                <p className="text-xs text-slate-500">completed</p>
              </div>
              <div className="p-3 bg-purple-500/10 rounded-lg">
                <Target className="w-6 h-6 text-purple-500" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">Configs Tested</p>
                <p className="text-2xl font-bold text-white">
                  {stats?.optimization_configs?.toLocaleString() || 0}
                </p>
                <p className="text-xs text-slate-500">combinations</p>
              </div>
              <div className="p-3 bg-orange-500/10 rounded-lg">
                <Shield className="w-6 h-6 text-orange-500" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Current Regime & Performance */}
      <div className="grid grid-cols-2 gap-4">
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Activity className="w-5 h-5 text-blue-500" />
              Current Market Regime
            </CardTitle>
            <CardDescription>Real-time regime detection (Hurst + ADX)</CardDescription>
          </CardHeader>
          <CardContent>
            {regime?.current_regime ? (
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <div className={`p-4 rounded-xl ${getRegimeColor(regime.current_regime.regime_class)}`}>
                    {getRegimeIcon(regime.current_regime.regime_class)}
                  </div>
                  <div>
                    <p className="text-xl font-bold text-white">
                      {regime.current_regime.regime_class}
                    </p>
                    <p className="text-sm text-slate-400">
                      {regime.interpretation}
                    </p>
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4 pt-4 border-t border-slate-800">
                  <div>
                    <p className="text-sm text-slate-400">Hurst Exponent</p>
                    <p className="text-lg font-mono text-white">
                      {regime.current_regime.hurst_exponent?.toFixed(3) || 'N/A'}
                    </p>
                    <p className="text-xs text-slate-500">
                      {regime.current_regime.hurst_exponent < 0.5 ? 'Mean Reversion' : 
                       regime.current_regime.hurst_exponent > 0.5 ? 'Trending' : 'Random Walk'}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-400">ADX (14)</p>
                    <p className="text-lg font-mono text-white">
                      {regime.current_regime.adx?.toFixed(1) || 'N/A'}
                    </p>
                    <p className="text-xs text-slate-500">
                      {regime.current_regime.adx < 20 ? 'Weak Trend' : 
                       regime.current_regime.adx > 40 ? 'Strong Trend' : 'Moderate'}
                    </p>
                  </div>
                </div>

                <div className="pt-2">
                  <Badge 
                    variant={regime.current_regime.regime_class?.includes('MeanRev') ? 'default' : 'destructive'}
                    className="w-full justify-center py-2"
                  >
                    {regime.current_regime.regime_class?.includes('MeanRev') 
                      ? '✓ Grid Trading FAVORABLE' 
                      : '⚠ Grid Trading CAUTION'}
                  </Badge>
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-slate-500">
                No regime data available
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <DollarSign className="w-5 h-5 text-green-500" />
              Performance Summary
            </CardTitle>
            <CardDescription>Aggregated optimization results</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              <div>
                <div className="flex justify-between mb-2">
                  <span className="text-sm text-slate-400">Total Profit</span>
                  <span className={`font-mono font-bold ${(stats?.total_profit || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    ${stats?.total_profit?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}
                  </span>
                </div>
                <Progress 
                  value={Math.min(100, Math.abs(stats?.total_profit || 0) / 100)} 
                  className="h-2"
                />
              </div>

              <div>
                <div className="flex justify-between mb-2">
                  <span className="text-sm text-slate-400">Avg Profit Factor</span>
                  <span className="font-mono font-bold text-white">
                    {stats?.avg_profit_factor?.toFixed(2) || '0.00'}
                  </span>
                </div>
                <Progress 
                  value={Math.min(100, (stats?.avg_profit_factor || 0) / 3 * 100)} 
                  className="h-2"
                />
              </div>

              <div>
                <div className="flex justify-between mb-2">
                  <span className="text-sm text-slate-400">Avg Win Rate</span>
                  <span className="font-mono font-bold text-white">
                    {stats?.avg_win_rate?.toFixed(1) || '0.0'}%
                  </span>
                </div>
                <Progress 
                  value={stats?.avg_win_rate || 0} 
                  className="h-2"
                />
              </div>

              <div className="pt-4 border-t border-slate-800">
                <div className="flex items-center gap-2 text-sm">
                  <Clock className="w-4 h-4 text-slate-400" />
                  <span className="text-slate-400">Last updated: {new Date().toLocaleTimeString()}</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="text-lg">Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-4 gap-4">
            <button className="p-4 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors text-left">
              <TrendingUp className="w-6 h-6 text-blue-500 mb-2" />
              <p className="font-medium text-white">Analyze Regime</p>
              <p className="text-xs text-slate-400">Check current market conditions</p>
            </button>
            <button className="p-4 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors text-left">
              <Activity className="w-6 h-6 text-green-500 mb-2" />
              <p className="font-medium text-white">Survival Analysis</p>
              <p className="text-xs text-slate-400">Find optimal time stop</p>
            </button>
            <button className="p-4 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors text-left">
              <Shield className="w-6 h-6 text-purple-500 mb-2" />
              <p className="font-medium text-white">Check Robustness</p>
              <p className="text-xs text-slate-400">Validate parameter stability</p>
            </button>
            <button className="p-4 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors text-left">
              <BarChart3 className="w-6 h-6 text-orange-500 mb-2" />
              <p className="font-medium text-white">Run Optimization</p>
              <p className="text-xs text-slate-400">Find best parameters</p>
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
