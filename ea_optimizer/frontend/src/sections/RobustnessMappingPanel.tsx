import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  ScatterChart, 
  Scatter, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  ZAxis,
  Cell,
  ReferenceLine
} from 'recharts';
import { Shield, AlertTriangle, CheckCircle, Target, RefreshCw, TrendingUp } from 'lucide-react';
import { apiUrl } from '@/lib/api';

interface RobustZone {
  cluster_id: number;
  center_grid: number;
  center_multiplier: number;
  atr_filter: number;
  optimization_score: number;
  avg_stability: number;
  cluster_size: number;
  grid_range: [number, number];
  multiplier_range: [number, number];
}

interface OverfittingPeak {
  grid_pips: number;
  multiplier: number;
  atr_filter: number;
  optimization_score: number;
  stability_pct: number;
  std_dev: number;
  warning: string;
}

interface RobustnessRecommendation {
  recommended_config: {
    grid_pips: number;
    multiplier: number;
    atr_filter: number;
  };
  expected_performance: {
    optimization_score: number;
    stability: number;
  };
  rationale: string;
  robust_zones: RobustZone[];
  overfitting_warnings: OverfittingPeak[];
}

interface RobustnessAnalysis {
  landscape_summary: {
    total_configs: number;
    robust_configs: number;
    best_score: number;
    avg_stability: number;
  };
  robust_zones: RobustZone[];
  overfitting_warnings: OverfittingPeak[];
  recommendation: RobustnessRecommendation;
}

interface SurfacePoint {
  grid_pips: number;
  multiplier: number;
  optimization_score: number;
  neighbor_stability_pct: number;
  is_robust: boolean;
}

export default function RobustnessMappingPanel() {
  const [analysis, setAnalysis] = useState<RobustnessAnalysis | null>(null);
  const [surfaceData, setSurfaceData] = useState<SurfacePoint[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchRobustnessAnalysis = async () => {
    setLoading(true);
    try {
      const res = await fetch(apiUrl('/api/robustness/analyze'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });

      if (res.ok) {
        const data: RobustnessAnalysis = await res.json();
        setAnalysis(data);
      }

      // Fetch surface data
      const surfaceRes = await fetch(apiUrl('/api/robustness/surface-data'));
      if (surfaceRes.ok) {
        const surfaceResult = await surfaceRes.json();
        setSurfaceData(surfaceResult.surface_data || []);
      }
    } catch (e) {
      console.error('Error fetching robustness analysis:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRobustnessAnalysis();
  }, []);

  const getStabilityColor = (stability: number) => {
    if (stability >= 80) return '#22c55e';
    if (stability >= 60) return '#eab308';
    return '#ef4444';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Robustness Mapping</h2>
          <p className="text-slate-400">FR-16: 3D Surface Analysis for parameter stability</p>
        </div>
        <Button 
          onClick={fetchRobustnessAnalysis} 
          disabled={loading}
          className="gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh Analysis
        </Button>
      </div>

      {/* Summary Cards */}
      {analysis?.landscape_summary && (
        <div className="grid grid-cols-4 gap-4">
          <Card className="bg-slate-900 border-slate-800">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-400">Total Configs</p>
                  <p className="text-2xl font-bold text-white">
                    {analysis.landscape_summary.total_configs}
                  </p>
                </div>
                <div className="p-3 bg-blue-500/10 rounded-lg">
                  <Target className="w-6 h-6 text-blue-500" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-400">Robust Configs</p>
                  <p className="text-2xl font-bold text-green-400">
                    {analysis.landscape_summary.robust_configs}
                  </p>
                  <p className="text-xs text-slate-500">
                    {((analysis.landscape_summary.robust_configs / analysis.landscape_summary.total_configs) * 100).toFixed(1)}%
                  </p>
                </div>
                <div className="p-3 bg-green-500/10 rounded-lg">
                  <CheckCircle className="w-6 h-6 text-green-500" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-400">Best Score</p>
                  <p className="text-2xl font-bold text-white">
                    {analysis.landscape_summary.best_score.toFixed(1)}
                  </p>
                </div>
                <div className="p-3 bg-purple-500/10 rounded-lg">
                  <TrendingUp className="w-6 h-6 text-purple-500" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-400">Avg Stability</p>
                  <p className="text-2xl font-bold text-white">
                    {analysis.landscape_summary.avg_stability.toFixed(1)}%
                  </p>
                </div>
                <div className="p-3 bg-orange-500/10 rounded-lg">
                  <Shield className="w-6 h-6 text-orange-500" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* 2D Scatter Plot */}
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Target className="w-5 h-5 text-blue-500" />
            Robustness Landscape (2D Projection)
          </CardTitle>
          <CardDescription>
            X: Grid Spacing (pips) | Y: Lot Multiplier | Color: Stability | Size: Score
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-96">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis 
                  type="number" 
                  dataKey="grid_pips" 
                  name="Grid Spacing"
                  stroke="#64748b"
                  label={{ value: 'Grid Spacing (pips)', position: 'insideBottom', offset: -10 }}
                />
                <YAxis 
                  type="number" 
                  dataKey="multiplier" 
                  name="Lot Multiplier"
                  domain={[1.2, 1.6]}
                  stroke="#64748b"
                  label={{ value: 'Lot Multiplier', angle: -90, position: 'insideLeft' }}
                />
                <ZAxis 
                  type="number" 
                  dataKey="optimization_score" 
                  range={[50, 400]}
                />
                <Tooltip 
                  cursor={{ strokeDasharray: '3 3' }}
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload;
                      return (
                        <div className="bg-slate-800 p-3 rounded-lg border border-slate-700">
                          <p className="font-medium text-white">Grid: {data.grid_pips} pips</p>
                          <p className="text-slate-300">Multiplier: {data.multiplier.toFixed(2)}</p>
                          <p className="text-slate-300">Score: {data.optimization_score.toFixed(1)}</p>
                          <p className={`${data.neighbor_stability_pct >= 80 ? 'text-green-400' : 'text-yellow-400'}`}>
                            Stability: {data.neighbor_stability_pct.toFixed(1)}%
                          </p>
                          <Badge 
                            variant={data.is_robust ? 'default' : 'secondary'}
                            className="mt-2"
                          >
                            {data.is_robust ? 'Robust' : 'Not Robust'}
                          </Badge>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Scatter data={surfaceData}>
                  {surfaceData.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={getStabilityColor(entry.neighbor_stability_pct)}
                      fillOpacity={entry.is_robust ? 0.9 : 0.4}
                    />
                  ))}
                </Scatter>
                <ReferenceLine y={1.4} stroke="#94a3b8" strokeDasharray="3 3" />
                <ReferenceLine x={350} stroke="#94a3b8" strokeDasharray="3 3" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Legend */}
      <Card className="bg-slate-900 border-slate-800">
        <CardContent className="p-4">
          <div className="flex items-center justify-center gap-8">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-green-500"></div>
              <span className="text-sm text-slate-300">High Stability (&gt;80%)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-yellow-500"></div>
              <span className="text-sm text-slate-300">Medium Stability (60-80%)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-red-500"></div>
              <span className="text-sm text-slate-300">Low Stability (&lt;60%)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-slate-500 opacity-40"></div>
              <span className="text-sm text-slate-300">Non-Robust</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Robust Zones */}
      {analysis?.robust_zones && analysis.robust_zones.length > 0 && (
        <Card className="bg-slate-900 border-slate-800 border-l-4 border-l-green-500">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-green-500" />
              Robust Zones (Blue Zones)
            </CardTitle>
            <CardDescription>Parameter configurations with high stability</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              {analysis.robust_zones.slice(0, 4).map((zone, idx) => (
                <div key={idx} className="p-4 bg-slate-800 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <Badge className="bg-green-500">Zone {zone.cluster_id + 1}</Badge>
                    <span className="text-sm text-slate-400">{zone.cluster_size} configs</span>
                  </div>
                  <div className="space-y-1">
                    <p className="text-lg font-bold text-white">
                      Grid: {zone.center_grid} pips
                    </p>
                    <p className="text-lg font-bold text-white">
                      Mult: {zone.center_multiplier.toFixed(2)}x
                    </p>
                    <div className="flex gap-4 pt-2">
                      <div>
                        <p className="text-xs text-slate-400">Score</p>
                        <p className="font-mono text-green-400">{zone.optimization_score.toFixed(1)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-400">Stability</p>
                        <p className="font-mono text-blue-400">{zone.avg_stability.toFixed(1)}%</p>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Overfitting Warnings */}
      {analysis?.overfitting_warnings && analysis.overfitting_warnings.length > 0 && (
        <Card className="bg-slate-900 border-slate-800 border-l-4 border-l-red-500">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-red-500" />
              Overfitting Peaks (Red Zones)
            </CardTitle>
            <CardDescription>High performance but low stability - AVOID</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {analysis.overfitting_warnings.slice(0, 3).map((peak, idx) => (
                <Alert key={idx} className="bg-slate-800 border-red-500/30">
                  <AlertDescription className="text-slate-300">
                    <div className="flex items-center justify-between">
                      <span>{peak.warning}</span>
                      <Badge variant="destructive">AVOID</Badge>
                    </div>
                  </AlertDescription>
                </Alert>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recommendation */}
      {analysis?.recommendation && (
        <Card className="bg-slate-900 border-slate-800 border-l-4 border-l-blue-500">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Shield className="w-5 h-5 text-blue-500" />
              Recommended Configuration
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                <div className="p-4 bg-slate-800 rounded-lg text-center">
                  <p className="text-sm text-slate-400">Grid Spacing</p>
                  <p className="text-3xl font-bold text-white">
                    {analysis.recommendation.recommended_config.grid_pips}
                  </p>
                  <p className="text-xs text-slate-500">pips</p>
                </div>
                <div className="p-4 bg-slate-800 rounded-lg text-center">
                  <p className="text-sm text-slate-400">Lot Multiplier</p>
                  <p className="text-3xl font-bold text-white">
                    {analysis.recommendation.recommended_config.multiplier.toFixed(2)}
                  </p>
                  <p className="text-xs text-slate-500">x</p>
                </div>
                <div className="p-4 bg-slate-800 rounded-lg text-center">
                  <p className="text-sm text-slate-400">ATR Filter</p>
                  <p className="text-3xl font-bold text-white">
                    {analysis.recommendation.recommended_config.atr_filter.toFixed(1)}
                  </p>
                  <p className="text-xs text-slate-500">x ATR</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-slate-800 rounded-lg">
                  <p className="text-sm text-slate-400">Expected Score</p>
                  <p className="text-2xl font-bold text-green-400">
                    {analysis.recommendation.expected_performance.optimization_score.toFixed(1)}
                  </p>
                </div>
                <div className="p-4 bg-slate-800 rounded-lg">
                  <p className="text-sm text-slate-400">Stability</p>
                  <p className="text-2xl font-bold text-blue-400">
                    {analysis.recommendation.expected_performance.stability.toFixed(1)}%
                  </p>
                </div>
              </div>

              <Alert className="bg-blue-500/10 border-blue-500/30">
                <AlertDescription className="text-slate-300">
                  {analysis.recommendation.rationale}
                </AlertDescription>
              </Alert>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
