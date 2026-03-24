import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { apiUrl } from '@/lib/api';
import {
  Activity,
  AlertTriangle,
  Bug,
  Clock,
  RefreshCw,
  ShieldAlert,
  SlidersHorizontal,
  Target,
  TrendingDown,
  Wrench,
} from 'lucide-react';

interface DiagnosticSummary {
  symbol: string;
  market_bars: number;
  trades: number;
  baskets: number;
  net_profit: number;
  trade_win_rate_pct: number;
  basket_win_rate_pct: number;
  median_basket_hours: number;
  stop_rate_pct: number;
  phantom_winner_pct: number;
  avg_basket_mae: number;
  worst_basket_profit: number;
}

interface ParameterSnapshot {
  avg_grid_pips: number;
  avg_multiplier: number;
  avg_max_levels_seen: number;
  avg_atr_filter: number;
}

interface BestConfig {
  grid_pips: number;
  multiplier: number;
  atr_filter: number;
  max_levels: number;
  score: number;
}

interface OptimizationContext {
  configs_tested: number;
  best_config: BestConfig | null;
}

interface RegimeBreakdown {
  regime: string;
  baskets: number;
  avg_profit: number;
  median_hours: number;
  stop_rate_pct: number;
}

interface TopLossBasket {
  basket_id: string;
  profit: number;
  mae: number;
  levels: number;
  duration_hours: number;
  regime: string;
}

interface Finding {
  severity: 'high' | 'medium' | 'low';
  title: string;
  evidence: string;
  mq5_hint: string;
}

interface Recommendation {
  priority: 'high' | 'medium' | 'low';
  title: string;
  rationale: string;
  mq5_change: string;
}

interface DiagnosticReport {
  summary: DiagnosticSummary;
  parameter_snapshot: ParameterSnapshot;
  optimization_context: OptimizationContext;
  regime_breakdown: RegimeBreakdown[];
  top_loss_baskets: TopLossBasket[];
  findings: Finding[];
  recommendations: Recommendation[];
}

export default function DiagnosticsPanel() {
  const [report, setReport] = useState<DiagnosticReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDiagnostics = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(apiUrl('/api/diagnostics/mq5?symbol=XAUUSD'));
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || 'Nao foi possivel gerar o diagnostico do MQ5.');
        return;
      }
      setReport(data);
    } catch (e) {
      console.error('Error fetching diagnostics:', e);
      setError('Falha ao carregar o diagnostico do MQ5.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDiagnostics();
  }, []);

  const severityVariant = (severity: string) => {
    if (severity === 'high') return 'destructive';
    if (severity === 'medium') return 'secondary';
    return 'outline';
  };

  const executiveRead = report ? [
    `O simbolo ${report.summary.symbol} ja tem ${report.summary.trades.toLocaleString()} trades e ${report.summary.baskets.toLocaleString()} baskets suficientes para orientar mudancas reais no MQ5.`,
    report.summary.net_profit >= 0
      ? `O resultado liquido atual esta positivo em ${report.summary.net_profit.toFixed(2)}, mas o foco agora e descobrir o que esta sustentando esse ganho e onde ele pode quebrar.`
      : `O resultado liquido atual esta negativo em ${report.summary.net_profit.toFixed(2)}, entao o diagnostico prioriza primeiro o controle de risco e depois a melhoria de retorno.`,
    `A mediana de duracao do basket esta em ${report.summary.median_basket_hours.toFixed(1)}h e a taxa de stop em ${report.summary.stop_rate_pct.toFixed(1)}%. Isso aponta diretamente para ajustes de timing, niveis e filtros do EA.`,
  ] : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">MQ5 Diagnostics</h2>
          <p className="text-slate-400">Laudo operacional para evoluir a logica, risco e filtros do seu EA</p>
        </div>
        <Button onClick={fetchDiagnostics} disabled={loading} className="gap-2">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh Diagnostics
        </Button>
      </div>

      <Alert className="bg-slate-900 border-slate-800">
        <AlertDescription className="text-slate-300">
          Esta tela resume o que os dados reais do EA estao mostrando e traduz isso em mudancas praticas para o seu MQ5: filtros, niveis, timeout, sizing e travas de risco.
        </AlertDescription>
      </Alert>

      {error && (
        <Alert className="border-red-500/40 bg-red-500/10">
          <AlertDescription className="text-red-200">{error}</AlertDescription>
        </Alert>
      )}

      {report && (
        <Card className="bg-slate-900 border-slate-800 border-l-4 border-l-cyan-500">
          <CardHeader>
            <CardTitle className="text-lg">Executive Diagnostic Read</CardTitle>
            <CardDescription>What the current real history is saying about your EA</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4">
              {executiveRead.map((item, index) => (
                <div key={index} className="rounded-lg bg-slate-800/80 p-4 text-sm leading-6 text-slate-200">
                  {item}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {report && (
        <div className="grid grid-cols-4 gap-4">
          <Card className="bg-slate-900 border-slate-800">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-400">Net Profit</p>
                  <p className={`text-2xl font-bold ${report.summary.net_profit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {report.summary.net_profit.toFixed(2)}
                  </p>
                </div>
                <div className="p-3 bg-emerald-500/10 rounded-lg">
                  <Activity className="w-6 h-6 text-emerald-500" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-400">Median Basket Time</p>
                  <p className="text-2xl font-bold text-white">{report.summary.median_basket_hours.toFixed(1)}h</p>
                </div>
                <div className="p-3 bg-blue-500/10 rounded-lg">
                  <Clock className="w-6 h-6 text-blue-500" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-400">Stop Rate</p>
                  <p className="text-2xl font-bold text-white">{report.summary.stop_rate_pct.toFixed(1)}%</p>
                </div>
                <div className="p-3 bg-red-500/10 rounded-lg">
                  <ShieldAlert className="w-6 h-6 text-red-500" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-400">Worst Basket</p>
                  <p className="text-2xl font-bold text-red-400">{report.summary.worst_basket_profit.toFixed(2)}</p>
                </div>
                <div className="p-3 bg-orange-500/10 rounded-lg">
                  <TrendingDown className="w-6 h-6 text-orange-500" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {report && (
        <div className="grid grid-cols-2 gap-6">
          <Card className="bg-slate-900 border-slate-800">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Bug className="w-5 h-5 text-red-400" />
                Critical Findings
              </CardTitle>
              <CardDescription>What is hurting the EA most right now</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {report.findings.map((finding, index) => (
                <div key={`${finding.title}-${index}`} className="rounded-lg border border-slate-800 bg-slate-800/50 p-4">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <p className="font-semibold text-white">{finding.title}</p>
                    <Badge variant={severityVariant(finding.severity)}>{finding.severity}</Badge>
                  </div>
                  <p className="text-sm leading-6 text-slate-300">{finding.evidence}</p>
                  <div className="mt-3 rounded-md bg-red-500/10 p-3 text-sm text-red-100">
                    <span className="font-medium">Hint para o MQ5:</span> {finding.mq5_hint}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Wrench className="w-5 h-5 text-lime-400" />
                MQ5 Upgrade Plan
              </CardTitle>
              <CardDescription>Changes worth testing in the next MQ5 iteration</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {report.recommendations.map((recommendation, index) => (
                <div key={`${recommendation.title}-${index}`} className="rounded-lg border border-slate-800 bg-slate-800/50 p-4">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <p className="font-semibold text-white">{recommendation.title}</p>
                    <Badge variant={severityVariant(recommendation.priority)}>{recommendation.priority}</Badge>
                  </div>
                  <p className="text-sm leading-6 text-slate-300">{recommendation.rationale}</p>
                  <div className="mt-3 rounded-md bg-lime-500/10 p-3 text-sm text-lime-100">
                    <span className="font-medium">Mudanca sugerida:</span> {recommendation.mq5_change}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      )}

      {report && (
        <div className="grid grid-cols-2 gap-6">
          <Card className="bg-slate-900 border-slate-800">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <SlidersHorizontal className="w-5 h-5 text-blue-400" />
                Parameter Snapshot
              </CardTitle>
              <CardDescription>Observed behavior and current optimization context</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-lg bg-slate-800 p-4">
                  <p className="text-sm text-slate-400">Avg Grid</p>
                  <p className="text-xl font-bold text-white">{report.parameter_snapshot.avg_grid_pips.toFixed(1)} pips</p>
                </div>
                <div className="rounded-lg bg-slate-800 p-4">
                  <p className="text-sm text-slate-400">Avg Multiplier</p>
                  <p className="text-xl font-bold text-white">{report.parameter_snapshot.avg_multiplier.toFixed(2)}x</p>
                </div>
                <div className="rounded-lg bg-slate-800 p-4">
                  <p className="text-sm text-slate-400">Avg Levels Seen</p>
                  <p className="text-xl font-bold text-white">{report.parameter_snapshot.avg_max_levels_seen.toFixed(1)}</p>
                </div>
                <div className="rounded-lg bg-slate-800 p-4">
                  <p className="text-sm text-slate-400">Avg ATR Filter</p>
                  <p className="text-xl font-bold text-white">{report.parameter_snapshot.avg_atr_filter.toFixed(2)}</p>
                </div>
              </div>

              <Alert className="bg-slate-800 border-slate-700">
                <AlertDescription className="text-slate-300">
                  {report.optimization_context.best_config
                    ? `Melhor regiao atual: grid ${report.optimization_context.best_config.grid_pips}, mult ${report.optimization_context.best_config.multiplier.toFixed(2)}, ATR ${report.optimization_context.best_config.atr_filter.toFixed(1)}, max levels ${report.optimization_context.best_config.max_levels}, score ${report.optimization_context.best_config.score.toFixed(1)}.`
                    : 'Ainda nao ha contexto de otimizacao salvo para complementar o diagnostico.'}
                </AlertDescription>
              </Alert>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Target className="w-5 h-5 text-purple-400" />
                Worst Loss Baskets
              </CardTitle>
              <CardDescription>Where the EA most likely needs protection logic</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {report.top_loss_baskets.map((basket) => (
                  <div key={basket.basket_id} className="rounded-lg bg-slate-800/70 p-4">
                    <div className="mb-2 flex items-center justify-between gap-4">
                      <p className="font-medium text-white">{basket.regime}</p>
                      <Badge variant="destructive">{basket.profit.toFixed(2)}</Badge>
                    </div>
                    <div className="grid grid-cols-3 gap-3 text-sm text-slate-300">
                      <span>MAE: {basket.mae.toFixed(2)}</span>
                      <span>Levels: {basket.levels}</span>
                      <span>Hours: {basket.duration_hours.toFixed(1)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {report && (
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-400" />
              Regime Breakdown
            </CardTitle>
            <CardDescription>Which market context hurts or helps the EA most</CardDescription>
          </CardHeader>
          <CardContent>
            {report.regime_breakdown.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-slate-700">
                      <th className="py-3 px-4 text-left text-slate-400 font-medium">Regime</th>
                      <th className="py-3 px-4 text-right text-slate-400 font-medium">Baskets</th>
                      <th className="py-3 px-4 text-right text-slate-400 font-medium">Avg Profit</th>
                      <th className="py-3 px-4 text-right text-slate-400 font-medium">Median Hours</th>
                      <th className="py-3 px-4 text-right text-slate-400 font-medium">Stop Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.regime_breakdown.map((row) => (
                      <tr key={row.regime} className="border-b border-slate-800 hover:bg-slate-800/50">
                        <td className="py-3 px-4 text-slate-200">{row.regime}</td>
                        <td className="py-3 px-4 text-right text-slate-300">{row.baskets}</td>
                        <td className={`py-3 px-4 text-right ${row.avg_profit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {row.avg_profit.toFixed(2)}
                        </td>
                        <td className="py-3 px-4 text-right text-slate-300">{row.median_hours.toFixed(1)}h</td>
                        <td className="py-3 px-4 text-right text-slate-300">{row.stop_rate_pct.toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Alert className="bg-slate-800 border-slate-700">
                <AlertDescription className="text-slate-300">
                  Ainda nao ha regime suficiente gravado por basket para cruzar as perdas do EA com contexto de mercado.
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
