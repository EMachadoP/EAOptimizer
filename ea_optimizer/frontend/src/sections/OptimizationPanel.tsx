import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { apiUrl } from '@/lib/api';
import { 
  BarChart,
  CartesianGrid,
  Bar,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';
import { 
  Play, 
  TrendingDown, 
  Activity,
  Shield,
  RefreshCw,
  CheckCircle
} from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface OptimizationResult {
  config_hash: string;
  grid_pips: number;
  multiplier: number;
  atr_filter: number;
  max_levels: number;
  total_return: number;
  profit_factor: number;
  sharpe_ratio: number;
  ulcer_index: number;
  cvar_95: number;
  max_drawdown_pct: number;
  win_rate: number;
  total_trades: number;
  return_over_ulcer: number;
  return_over_cvar: number;
  optimization_score: number;
}

interface BestConfig {
  grid_pips: number;
  multiplier: number;
  atr_filter: number;
  max_levels: number;
}

interface BestMetrics {
  total_return: number;
  profit_factor: number;
  sharpe_ratio: number;
  ulcer_index: number;
  cvar_95: number;
  max_drawdown_pct: number;
  win_rate: number;
  optimization_score: number;
}

interface OptimizationResponse {
  data_source?: string;
  historical_basket_count?: number;
  best_config: BestConfig;
  best_metrics: BestMetrics;
  total_configs_tested: number;
}

export default function OptimizationPanel() {
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState<OptimizationResult[]>([]);
  const [bestResult, setBestResult] = useState<OptimizationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runOptimization = async () => {
    setIsRunning(true);
    setProgress(0);
    setError(null);
    
    try {
      const res = await fetch(apiUrl('/api/optimization/run'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: 'XAUUSD',
          param_grid: {
            grid_pips: [200, 250, 300, 350, 400, 450, 500],
            multiplier: [1.2, 1.3, 1.4, 1.5, 1.6],
            atr_filter: [1.0, 1.5, 2.0],
            max_levels: [8, 10, 12]
          }
        })
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.error || 'Nao foi possivel executar a otimizacao real.');
        return;
      }

      setBestResult(data as OptimizationResponse);
      setProgress(100);
      
      // Fetch all results
      fetchResults();
    } catch (e) {
      console.error('Error running optimization:', e);
      setError('Falha ao executar a otimizacao real do EA.');
    } finally {
      setIsRunning(false);
    }
  };

  const fetchResults = async () => {
    setLoading(true);
    try {
      const res = await fetch(apiUrl('/api/optimization/results?page=1&per_page=50'));
      if (res.ok) {
        const data = await res.json();
        setResults(data.results || []);
      }
    } catch (e) {
      console.error('Error fetching results:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchResults();
  }, []);

  const getScoreColor = (score: number) => {
    if (score >= 80) return '#22c55e';
    if (score >= 60) return '#3b82f6';
    if (score >= 40) return '#eab308';
    return '#ef4444';
  };

  const getMetricStatus = (value: number, type: string) => {
    switch (type) {
      case 'profit_factor':
        return value >= 1.5 ? 'good' : value >= 1.0 ? 'neutral' : 'bad';
      case 'sharpe':
        return value >= 1.0 ? 'good' : value >= 0.5 ? 'neutral' : 'bad';
      case 'ulcer':
        return value <= 5 ? 'good' : value <= 10 ? 'neutral' : 'bad';
      case 'win_rate':
        return value >= 55 ? 'good' : value >= 45 ? 'neutral' : 'bad';
      default:
        return 'neutral';
    }
  };

  const optimizationInsights = bestResult ? [
    `Este ranking foi guiado pelos baskets reais importados do seu EA. Nesta execucao foram usados ${bestResult.historical_basket_count ?? 0} baskets historicos.`,
    `A melhor combinação encontrada foi grid ${bestResult.best_config.grid_pips} pips, multiplicador ${bestResult.best_config.multiplier.toFixed(2)}x e máximo de ${bestResult.best_config.max_levels} níveis.`,
    `O score ${bestResult.best_metrics.optimization_score.toFixed(1)} resume retorno e risco juntos. Quanto maior, melhor o equilíbrio entre ganho, drawdown e consistência.`,
    bestResult.best_metrics.max_drawdown_pct <= 3
      ? 'O drawdown ficou controlado no melhor cenário encontrado, o que é um bom sinal para continuar investigando essa região de parâmetros.'
      : 'O melhor cenário ainda carrega drawdown relevante. Antes de usar em conta real, vale confirmar se esse risco cabe no seu perfil.',
  ] : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Optimization Engine</h2>
          <p className="text-slate-400">FR-09: Ulcer Index + CVaR_95 optimization based on real EA history</p>
        </div>
        <div className="flex gap-2">
          <Button 
            onClick={runOptimization} 
            disabled={isRunning}
            className="gap-2"
          >
            {isRunning ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            {isRunning ? 'Running...' : 'Run Optimization'}
          </Button>
          <Button 
            variant="outline" 
            onClick={fetchResults}
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      <Alert className="bg-slate-900 border-slate-800">
        <AlertDescription className="text-slate-300">
          Esta tela agora opera apenas com historico real do EA. Se faltarem baskets suficientes, a otimizacao para e avisa em vez de usar simulacao.
        </AlertDescription>
      </Alert>

      {error && (
        <Alert className="border-red-500/40 bg-red-500/10">
          <AlertDescription className="text-red-200">
            {error}
          </AlertDescription>
        </Alert>
      )}

      {bestResult && (
        <Card className="bg-slate-900 border-slate-800 border-l-4 border-l-lime-500">
          <CardHeader>
            <CardTitle className="text-lg">Optimization Summary</CardTitle>
            <CardDescription>How to interpret the winner and ranking</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4">
              {optimizationInsights.map((item, index) => (
                <div key={index} className="rounded-lg bg-slate-800/80 p-4 text-sm leading-6 text-slate-200">
                  {item}
                </div>
              ))}
            </div>
            <Alert className="mt-4 bg-lime-500/10 border-lime-500/30">
              <AlertDescription className="text-slate-300">
                Use this ranking as a shortlist of promising parameter regions. The next check is robustness: a high score alone is not enough if nearby configurations collapse.
              </AlertDescription>
            </Alert>
          </CardContent>
        </Card>
      )}

      {/* Progress */}
      {isRunning && (
        <Card className="bg-slate-900 border-slate-800">
          <CardContent className="p-6">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-slate-400">Optimization Progress</span>
                <span className="text-white">{progress}%</span>
              </div>
              <Progress value={progress} className="h-2" />
              <p className="text-xs text-slate-500">
                Testing parameter combinations with Ulcer-adjusted scoring...
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Best Result */}
      {bestResult && (
        <Card className="bg-slate-900 border-slate-800 border-l-4 border-l-green-500">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-green-500" />
              Best Configuration Found
            </CardTitle>
            <CardDescription>
              Tested {bestResult.total_configs_tested} combinations
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Config */}
              <div className="grid grid-cols-4 gap-4">
                <div className="p-4 bg-slate-800 rounded-lg text-center">
                  <p className="text-sm text-slate-400">Grid Spacing</p>
                  <p className="text-2xl font-bold text-white">
                    {bestResult.best_config.grid_pips}
                  </p>
                  <p className="text-xs text-slate-500">pips</p>
                </div>
                <div className="p-4 bg-slate-800 rounded-lg text-center">
                  <p className="text-sm text-slate-400">Multiplier</p>
                  <p className="text-2xl font-bold text-white">
                    {bestResult.best_config.multiplier.toFixed(2)}
                  </p>
                  <p className="text-xs text-slate-500">x</p>
                </div>
                <div className="p-4 bg-slate-800 rounded-lg text-center">
                  <p className="text-sm text-slate-400">ATR Filter</p>
                  <p className="text-2xl font-bold text-white">
                    {bestResult.best_config.atr_filter.toFixed(1)}
                  </p>
                  <p className="text-xs text-slate-500">x ATR</p>
                </div>
                <div className="p-4 bg-slate-800 rounded-lg text-center">
                  <p className="text-sm text-slate-400">Max Levels</p>
                  <p className="text-2xl font-bold text-white">
                    {bestResult.best_config.max_levels}
                  </p>
                  <p className="text-xs text-slate-500">orders</p>
                </div>
              </div>

              {/* Metrics */}
              <div className="grid grid-cols-4 gap-4">
                <div className="p-4 bg-slate-800 rounded-lg">
                  <p className="text-sm text-slate-400">Total Return</p>
                  <p className={`text-xl font-bold ${bestResult.best_metrics.total_return >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    ${bestResult.best_metrics.total_return.toFixed(0)}
                  </p>
                </div>
                <div className="p-4 bg-slate-800 rounded-lg">
                  <p className="text-sm text-slate-400">Profit Factor</p>
                  <p className={`text-xl font-bold ${getMetricStatus(bestResult.best_metrics.profit_factor, 'profit_factor') === 'good' ? 'text-green-400' : 'text-yellow-400'}`}>
                    {bestResult.best_metrics.profit_factor.toFixed(2)}
                  </p>
                </div>
                <div className="p-4 bg-slate-800 rounded-lg">
                  <p className="text-sm text-slate-400">Sharpe Ratio</p>
                  <p className={`text-xl font-bold ${getMetricStatus(bestResult.best_metrics.sharpe_ratio, 'sharpe') === 'good' ? 'text-green-400' : 'text-yellow-400'}`}>
                    {bestResult.best_metrics.sharpe_ratio.toFixed(2)}
                  </p>
                </div>
                <div className="p-4 bg-slate-800 rounded-lg">
                  <p className="text-sm text-slate-400">Optimization Score</p>
                  <p className="text-xl font-bold text-blue-400">
                    {bestResult.best_metrics.optimization_score.toFixed(1)}
                  </p>
                </div>
              </div>

              {/* Risk Metrics */}
              <div className="grid grid-cols-3 gap-4">
                <div className="p-4 bg-slate-800 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <Shield className="w-4 h-4 text-slate-400" />
                    <p className="text-sm text-slate-400">Ulcer Index</p>
                  </div>
                  <p className={`text-xl font-bold ${getMetricStatus(bestResult.best_metrics.ulcer_index, 'ulcer') === 'good' ? 'text-green-400' : 'text-yellow-400'}`}>
                    {bestResult.best_metrics.ulcer_index.toFixed(2)}
                  </p>
                  <p className="text-xs text-slate-500">Drawdown penalty</p>
                </div>
                <div className="p-4 bg-slate-800 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingDown className="w-4 h-4 text-slate-400" />
                    <p className="text-sm text-slate-400">CVaR 95%</p>
                  </div>
                  <p className="text-xl font-bold text-white">
                    ${bestResult.best_metrics.cvar_95.toFixed(0)}
                  </p>
                  <p className="text-xs text-slate-500">Expected shortfall</p>
                </div>
                <div className="p-4 bg-slate-800 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <Activity className="w-4 h-4 text-slate-400" />
                    <p className="text-sm text-slate-400">Max Drawdown</p>
                  </div>
                  <p className="text-xl font-bold text-red-400">
                    {bestResult.best_metrics.max_drawdown_pct.toFixed(1)}%
                  </p>
                  <p className="text-xs text-slate-500">Peak to trough</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Results Table */}
      {results.length > 0 && (
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="text-lg">Top Results</CardTitle>
            <CardDescription>Ranked by Ulcer-adjusted optimization score</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-700">
                    <th className="text-left py-3 px-4 text-slate-400 font-medium">Rank</th>
                    <th className="text-right py-3 px-4 text-slate-400 font-medium">Grid</th>
                    <th className="text-right py-3 px-4 text-slate-400 font-medium">Mult</th>
                    <th className="text-right py-3 px-4 text-slate-400 font-medium">ATR</th>
                    <th className="text-right py-3 px-4 text-slate-400 font-medium">Return</th>
                    <th className="text-right py-3 px-4 text-slate-400 font-medium">PF</th>
                    <th className="text-right py-3 px-4 text-slate-400 font-medium">Sharpe</th>
                    <th className="text-right py-3 px-4 text-slate-400 font-medium">Ulcer</th>
                    <th className="text-right py-3 px-4 text-slate-400 font-medium">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {results.slice(0, 10).map((row, idx) => (
                    <tr key={row.config_hash} className="border-b border-slate-800 hover:bg-slate-800/50">
                      <td className="py-3 px-4">
                        {idx === 0 ? (
                          <Badge className="bg-yellow-500">#1</Badge>
                        ) : idx === 1 ? (
                          <Badge className="bg-slate-400">#2</Badge>
                        ) : idx === 2 ? (
                          <Badge className="bg-orange-400">#3</Badge>
                        ) : (
                          <span className="text-slate-500">#{idx + 1}</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right text-slate-300">{row.grid_pips}</td>
                      <td className="py-3 px-4 text-right text-slate-300">{row.multiplier.toFixed(2)}</td>
                      <td className="py-3 px-4 text-right text-slate-300">{row.atr_filter.toFixed(1)}</td>
                      <td className="py-3 px-4 text-right">
                        <span className={row.total_return >= 0 ? 'text-green-400' : 'text-red-400'}>
                          ${row.total_return.toFixed(0)}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <span className={row.profit_factor >= 1.5 ? 'text-green-400' : 'text-slate-300'}>
                          {row.profit_factor.toFixed(2)}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right text-slate-300">{row.sharpe_ratio.toFixed(2)}</td>
                      <td className="py-3 px-4 text-right">
                        <span className={row.ulcer_index <= 5 ? 'text-green-400' : 'text-yellow-400'}>
                          {row.ulcer_index.toFixed(2)}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <span className="font-bold" style={{ color: getScoreColor(row.optimization_score) }}>
                          {row.optimization_score.toFixed(1)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Score Distribution */}
      {results.length > 0 && (
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="text-lg">Score Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={results.slice(0, 20)}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis 
                    dataKey="config_hash" 
                    tickFormatter={() => ''}
                    stroke="#64748b"
                  />
                  <YAxis stroke="#64748b" />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1e293b', border: 'none' }}
                    formatter={(value: number) => value.toFixed(1)}
                  />
                  <Bar dataKey="optimization_score">
                    {results.slice(0, 20).map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={getScoreColor(entry.optimization_score)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
