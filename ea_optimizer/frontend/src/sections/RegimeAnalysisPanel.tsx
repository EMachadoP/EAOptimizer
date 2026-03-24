import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { apiUrl } from '@/lib/api';
import { 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  ReferenceLine,
  Area,
  ComposedChart
} from 'recharts';
import { TrendingUp, Activity, AlertTriangle, RefreshCw } from 'lucide-react';

interface RegimeData {
  timestamp: string;
  hurst_exponent: number;
  adx: number;
  regime_class: string;
  close: number;
}

interface ProfitMatrixRow {
  regime: string;
  trades_count: number;
  profit_factor: number;
  basket_mae_avg: number;
  win_rate: number;
  avg_exposure_hours: number;
}

interface RegimeAnalysis {
  current_regime: {
    regime_class: string;
    hurst_exponent: number;
    adx: number;
    ema_slope: number;
    timestamp: string;
  };
  regime_distribution: Array<{
    regime_class: string;
    hurst_exponent: number;
    adx: number;
    close: number;
  }>;
  interpretation: string;
}

export default function RegimeAnalysisPanel() {
  const [regimeData, setRegimeData] = useState<RegimeData[]>([]);
  const [profitMatrix, setProfitMatrix] = useState<ProfitMatrixRow[]>([]);
  const [insights, setInsights] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const selectedSymbol = 'XAUUSD';

  const fetchRegimeData = async () => {
    setLoading(true);
    try {
      // Fetch regime analysis
      const regimeRes = await fetch(apiUrl('/api/regime/analyze'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: selectedSymbol })
      });

      if (regimeRes.ok) {
        const regimeResult: RegimeAnalysis = await regimeRes.json();
        setRegimeData(
          (regimeResult.regime_distribution || []).map((entry) => ({
            timestamp: regimeResult.current_regime.timestamp,
            hurst_exponent: entry.hurst_exponent,
            adx: entry.adx,
            regime_class: entry.regime_class,
            close: entry.close
          }))
        );
        
        // Fetch profit matrix
        const matrixRes = await fetch(apiUrl(`/api/regime/profit-matrix?symbol=${selectedSymbol}`));
        if (matrixRes.ok) {
          const matrixResult = await matrixRes.json();
          setProfitMatrix(matrixResult.profit_matrix || []);
          setInsights(matrixResult.insights || []);
        }
      }
    } catch (e) {
      console.error('Error fetching regime data:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRegimeData();
  }, []);

  const getRegimeBadge = (regime: string) => {
    if (regime?.includes('MeanRev')) {
      return <Badge className="bg-green-500">Grid Favorable</Badge>;
    }
    if (regime?.includes('Trend_Strong')) {
      return <Badge variant="destructive">Avoid</Badge>;
    }
    if (regime?.includes('Trend')) {
      return <Badge className="bg-yellow-500">Caution</Badge>;
    }
    return <Badge variant="secondary">Neutral</Badge>;
  };

  const latestRegime = regimeData[0]?.regime_class;
  const bestMatrixRow = profitMatrix.length
    ? [...profitMatrix].sort((a, b) => b.profit_factor - a.profit_factor)[0]
    : null;
  const worstMatrixRow = profitMatrix.length
    ? [...profitMatrix].sort((a, b) => a.profit_factor - b.profit_factor)[0]
    : null;
  const regimeSummary = [
    latestRegime
      ? `O regime mais recente foi classificado como ${latestRegime}. Isso descreve o tipo de mercado em que seu EA está operando agora.`
      : 'Ainda não há uma classificação de regime confiável para exibir.',
    bestMatrixRow
      ? `Seu melhor regime histórico no período analisado foi ${bestMatrixRow.regime}, com profit factor ${bestMatrixRow.profit_factor.toFixed(2)} e win rate de ${bestMatrixRow.win_rate.toFixed(1)}%.`
      : 'Ainda não há profit matrix suficiente para comparar a performance por regime.',
    worstMatrixRow
      ? `O regime mais fraco foi ${worstMatrixRow.regime}. Se esse contexto aparecer com frequência, vale reduzir agressividade do grid ou evitar entradas novas.`
      : 'Sem dados de regime suficientes para apontar o cenário mais arriscado.',
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Regime Detection & Profit Matrix</h2>
          <p className="text-slate-400">FR-14: Market regime classification using Hurst Exponent + ADX</p>
        </div>
        <Button 
          onClick={fetchRegimeData} 
          disabled={loading}
          className="gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh Analysis
        </Button>
      </div>

      <Card className="bg-slate-900 border-slate-800 border-l-4 border-l-emerald-500">
        <CardHeader>
          <CardTitle className="text-lg">How To Read This Screen</CardTitle>
          <CardDescription>Quick interpretation of regime and profit matrix</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4">
            {regimeSummary.map((item, index) => (
              <div key={index} className="rounded-lg bg-slate-800/80 p-4 text-sm leading-6 text-slate-200">
                {item}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Regime Classification Legend */}
      <Card className="bg-slate-900 border-slate-800">
        <CardContent className="p-4">
          <div className="grid grid-cols-4 gap-4">
            <div className="flex items-center gap-3 p-3 bg-green-500/10 rounded-lg border border-green-500/30">
              <div className="w-3 h-3 rounded-full bg-green-500"></div>
              <div>
                <p className="font-medium text-green-400">Range_MeanRev</p>
                <p className="text-xs text-slate-400">H &lt; 0.5, ADX &lt; 20</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-blue-500/10 rounded-lg border border-blue-500/30">
              <div className="w-3 h-3 rounded-full bg-blue-500"></div>
              <div>
                <p className="font-medium text-blue-400">Range_Neutral</p>
                <p className="text-xs text-slate-400">H ≈ 0.5, ADX &lt; 20</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-yellow-500/10 rounded-lg border border-yellow-500/30">
              <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
              <div>
                <p className="font-medium text-yellow-400">Trend_Weak/Moderate</p>
                <p className="text-xs text-slate-400">ADX 20-40</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-red-500/10 rounded-lg border border-red-500/30">
              <div className="w-3 h-3 rounded-full bg-red-500"></div>
              <div>
                <p className="font-medium text-red-400">Trend_Strong</p>
                <p className="text-xs text-slate-400">ADX &gt; 40</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Hurst & ADX Charts */}
      <div className="grid grid-cols-2 gap-4">
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Activity className="w-5 h-5 text-blue-500" />
              Hurst Exponent (H)
            </CardTitle>
            <CardDescription>Mean Reversion (H&lt;0.5) vs Trending (H&gt;0.5)</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={regimeData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis 
                    dataKey="timestamp" 
                    tickFormatter={(val) => new Date(val).toLocaleDateString()}
                    stroke="#64748b"
                  />
                  <YAxis domain={[0, 1]} stroke="#64748b" />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1e293b', border: 'none' }}
                    labelFormatter={(label) => new Date(label).toLocaleString()}
                  />
                  <ReferenceLine y={0.5} stroke="#94a3b8" strokeDasharray="3 3" label="Random Walk" />
                  <ReferenceLine y={0.4} stroke="#22c55e" strokeDasharray="3 3" label="Mean Rev" />
                  <Area 
                    type="monotone" 
                    dataKey="hurst_exponent" 
                    stroke="#3b82f6" 
                    fill="#3b82f6" 
                    fillOpacity={0.3}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-purple-500" />
              ADX (14)
            </CardTitle>
            <CardDescription>Trend Strength Indicator</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={regimeData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis 
                    dataKey="timestamp" 
                    tickFormatter={(val) => new Date(val).toLocaleDateString()}
                    stroke="#64748b"
                  />
                  <YAxis domain={[0, 60]} stroke="#64748b" />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1e293b', border: 'none' }}
                    labelFormatter={(label) => new Date(label).toLocaleString()}
                  />
                  <ReferenceLine y={20} stroke="#22c55e" strokeDasharray="3 3" label="Weak" />
                  <ReferenceLine y={40} stroke="#ef4444" strokeDasharray="3 3" label="Strong" />
                  <Area 
                    type="monotone" 
                    dataKey="adx" 
                    stroke="#a855f7" 
                    fill="#a855f7" 
                    fillOpacity={0.3}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Profit Matrix */}
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="text-lg">Profit Matrix by Regime</CardTitle>
          <CardDescription>Performance metrics segmented by market regime</CardDescription>
        </CardHeader>
        <CardContent>
          {profitMatrix.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-700">
                    <th className="text-left py-3 px-4 text-slate-400 font-medium">Regime</th>
                    <th className="text-right py-3 px-4 text-slate-400 font-medium">Trades</th>
                    <th className="text-right py-3 px-4 text-slate-400 font-medium">Profit Factor</th>
                    <th className="text-right py-3 px-4 text-slate-400 font-medium">Win Rate</th>
                    <th className="text-right py-3 px-4 text-slate-400 font-medium">Avg MAE</th>
                    <th className="text-right py-3 px-4 text-slate-400 font-medium">Avg Exposure</th>
                    <th className="text-center py-3 px-4 text-slate-400 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {profitMatrix.map((row, idx) => (
                    <tr key={idx} className="border-b border-slate-800 hover:bg-slate-800/50">
                      <td className="py-3 px-4 font-medium text-white">{row.regime}</td>
                      <td className="py-3 px-4 text-right text-slate-300">{row.trades_count}</td>
                      <td className="py-3 px-4 text-right">
                        <span className={`font-mono font-bold ${row.profit_factor >= 1.5 ? 'text-green-400' : row.profit_factor >= 1.0 ? 'text-yellow-400' : 'text-red-400'}`}>
                          {row.profit_factor.toFixed(2)}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <span className={`font-mono ${row.win_rate >= 55 ? 'text-green-400' : 'text-slate-300'}`}>
                          {row.win_rate.toFixed(1)}%
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right text-slate-300">${row.basket_mae_avg.toFixed(2)}</td>
                      <td className="py-3 px-4 text-right text-slate-300">{row.avg_exposure_hours.toFixed(1)}h</td>
                      <td className="py-3 px-4 text-center">
                        {getRegimeBadge(row.regime)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-8 text-slate-500">
              No profit matrix data available. Import trades to generate analysis.
            </div>
          )}
        </CardContent>
      </Card>

      {/* Insights */}
      {insights.length > 0 && (
        <Card className="bg-slate-900 border-slate-800 border-l-4 border-l-blue-500">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-blue-500" />
              Automated Insights
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {insights.map((insight, idx) => (
                <Alert key={idx} className="bg-slate-800 border-slate-700">
                  <AlertDescription className="text-slate-300">
                    {insight}
                  </AlertDescription>
                </Alert>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
