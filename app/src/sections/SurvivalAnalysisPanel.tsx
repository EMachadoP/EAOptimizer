import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Area,
  ComposedChart,
  ReferenceLine
} from 'recharts';
import { Activity, Clock, AlertTriangle, TrendingDown, CheckCircle, RefreshCw } from 'lucide-react';

interface SurvivalPoint {
  time_hours: number;
  survival_probability: number;
  hazard_rate: number;
  confidence_lower: number;
  confidence_upper: number;
}

interface TimeStopSuggestion {
  suggested_time_stop: number;
  survival_at_suggestion: number;
  rationale: string;
  hazard_rate_at_suggestion: number;
  confidence: number;
  median_survival_time: number;
  critical_points: Array<{
    time_hours: number;
    survival_prob?: number;
    hazard_rate?: number;
    type: string;
  }>;
}

interface SurvivalAnalysis {
  survival_curve: {
    time_hours: number[];
    survival_probability: number[];
    hazard_rate: number[];
    confidence_lower: number[];
    confidence_upper: number[];
  };
  statistics: {
    sample_size: number;
    median_survival_time: number;
    regime_filter: string;
  };
  time_stop_suggestion: TimeStopSuggestion;
}

export default function SurvivalAnalysisPanel() {
  const [analysis, setAnalysis] = useState<SurvivalAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedRegime, setSelectedRegime] = useState<string | null>(null);

  const fetchSurvivalAnalysis = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:5000/api/survival/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          symbol: 'XAUUSD',
          regime_filter: selectedRegime 
        })
      });

      if (res.ok) {
        const data: SurvivalAnalysis = await res.json();
        setAnalysis(data);
      }
    } catch (e) {
      console.error('Error fetching survival analysis:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSurvivalAnalysis();
  }, [selectedRegime]);

  // Transform data for charts
  const survivalData = analysis?.survival_curve?.time_hours.map((t, i) => ({
    time_hours: t,
    survival_probability: analysis.survival_curve.survival_probability[i] * 100,
    hazard_rate: analysis.survival_curve.hazard_rate[i] * 100,
    confidence_lower: analysis.survival_curve.confidence_lower[i] * 100,
    confidence_upper: analysis.survival_curve.confidence_upper[i] * 100,
  })) || [];

  const getSuggestionColor = (confidence: number) => {
    if (confidence >= 0.8) return 'bg-green-500';
    if (confidence >= 0.5) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Survival Analysis</h2>
          <p className="text-slate-400">FR-15: Kaplan-Meier estimator for basket time decay modeling</p>
        </div>
        <div className="flex gap-2">
          <select 
            className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-white"
            value={selectedRegime || ''}
            onChange={(e) => setSelectedRegime(e.target.value || null)}
          >
            <option value="">All Regimes</option>
            <option value="Range_MeanRev">Range_MeanRev</option>
            <option value="Range_Neutral">Range_Neutral</option>
            <option value="Trend_Weak">Trend_Weak</option>
            <option value="Trend_Strong">Trend_Strong</option>
          </select>
          <Button 
            onClick={fetchSurvivalAnalysis} 
            disabled={loading}
            className="gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Statistics Cards */}
      {analysis?.statistics && (
        <div className="grid grid-cols-4 gap-4">
          <Card className="bg-slate-900 border-slate-800">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-400">Sample Size</p>
                  <p className="text-2xl font-bold text-white">
                    {analysis.statistics.sample_size}
                  </p>
                  <p className="text-xs text-slate-500">baskets analyzed</p>
                </div>
                <div className="p-3 bg-blue-500/10 rounded-lg">
                  <Activity className="w-6 h-6 text-blue-500" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-400">Median Survival</p>
                  <p className="text-2xl font-bold text-white">
                    {analysis.statistics.median_survival_time.toFixed(1)}h
                  </p>
                  <p className="text-xs text-slate-500">50% survival point</p>
                </div>
                <div className="p-3 bg-purple-500/10 rounded-lg">
                  <Clock className="w-6 h-6 text-purple-500" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-400">S(4h)</p>
                  <p className="text-2xl font-bold text-white">
                    {analysis.survival_curve?.survival_probability[3] 
                      ? (analysis.survival_curve.survival_probability[3] * 100).toFixed(0) 
                      : 'N/A'}%
                  </p>
                  <p className="text-xs text-slate-500">survival at 4h</p>
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
                  <p className="text-sm text-slate-400">S(12h)</p>
                  <p className="text-2xl font-bold text-white">
                    {analysis.survival_curve?.survival_probability[11] 
                      ? (analysis.survival_curve.survival_probability[11] * 100).toFixed(0) 
                      : 'N/A'}%
                  </p>
                  <p className="text-xs text-slate-500">survival at 12h</p>
                </div>
                <div className="p-3 bg-red-500/10 rounded-lg">
                  <TrendingDown className="w-6 h-6 text-red-500" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Survival Curve */}
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Activity className="w-5 h-5 text-blue-500" />
            Survival Function S(t)
          </CardTitle>
          <CardDescription>Probability of basket not hitting stop over time</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={survivalData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis 
                  dataKey="time_hours" 
                  stroke="#64748b"
                  label={{ value: 'Time (hours)', position: 'insideBottom', offset: -5 }}
                />
                <YAxis 
                  domain={[0, 100]} 
                  stroke="#64748b"
                  label={{ value: 'Survival Probability (%)', angle: -90, position: 'insideLeft' }}
                />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1e293b', border: 'none' }}
                  formatter={(value: number) => `${value.toFixed(1)}%`}
                />
                <ReferenceLine y={50} stroke="#94a3b8" strokeDasharray="3 3" label="50%" />
                
                {/* Confidence interval */}
                <Area 
                  type="monotone" 
                  dataKey="confidence_upper" 
                  stroke="none" 
                  fill="#3b82f6" 
                  fillOpacity={0.1}
                />
                <Area 
                  type="monotone" 
                  dataKey="confidence_lower" 
                  stroke="none" 
                  fill="#1e293b" 
                  fillOpacity={1}
                />
                
                {/* Survival curve */}
                <Line 
                  type="stepAfter" 
                  dataKey="survival_probability" 
                  stroke="#3b82f6" 
                  strokeWidth={2}
                  dot={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Hazard Rate */}
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <TrendingDown className="w-5 h-5 text-red-500" />
            Hazard Rate h(t)
          </CardTitle>
          <CardDescription>Instantaneous failure rate (hitting stop)</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={survivalData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis 
                  dataKey="time_hours" 
                  stroke="#64748b"
                  label={{ value: 'Time (hours)', position: 'insideBottom', offset: -5 }}
                />
                <YAxis 
                  stroke="#64748b"
                  label={{ value: 'Hazard Rate (%/h)', angle: -90, position: 'insideLeft' }}
                />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1e293b', border: 'none' }}
                  formatter={(value: number) => `${value.toFixed(2)}%/h`}
                />
                <ReferenceLine y={15} stroke="#ef4444" strokeDasharray="3 3" label="Critical (15%)" />
                <Area 
                  type="monotone" 
                  dataKey="hazard_rate" 
                  stroke="#ef4444" 
                  fill="#ef4444" 
                  fillOpacity={0.3}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Time Stop Suggestion */}
      {analysis?.time_stop_suggestion && (
        <Card className="bg-slate-900 border-slate-800 border-l-4 border-l-green-500">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Clock className="w-5 h-5 text-green-500" />
              Time Stop Intelligence
            </CardTitle>
            <CardDescription>AI-powered recommendation based on survival analysis</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                <div className="p-4 bg-slate-800 rounded-lg">
                  <p className="text-sm text-slate-400">Suggested Time Stop</p>
                  <p className="text-3xl font-bold text-green-400">
                    {analysis.time_stop_suggestion.suggested_time_stop.toFixed(1)}h
                  </p>
                </div>
                <div className="p-4 bg-slate-800 rounded-lg">
                  <p className="text-sm text-slate-400">Survival at Cutoff</p>
                  <p className="text-3xl font-bold text-blue-400">
                    {(analysis.time_stop_suggestion.survival_at_suggestion * 100).toFixed(0)}%
                  </p>
                </div>
                <div className="p-4 bg-slate-800 rounded-lg">
                  <p className="text-sm text-slate-400">Hazard Rate</p>
                  <p className="text-3xl font-bold text-red-400">
                    {(analysis.time_stop_suggestion.hazard_rate_at_suggestion * 100).toFixed(1)}%/h
                  </p>
                </div>
              </div>

              <Alert className="bg-slate-800 border-slate-700">
                <AlertDescription className="text-slate-300 text-base">
                  {analysis.time_stop_suggestion.rationale}
                </AlertDescription>
              </Alert>

              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-400">Confidence:</span>
                <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
                  <div 
                    className={`h-full ${getSuggestionColor(analysis.time_stop_suggestion.confidence)}`}
                    style={{ width: `${analysis.time_stop_suggestion.confidence * 100}%` }}
                  ></div>
                </div>
                <span className="text-sm font-mono">
                  {(analysis.time_stop_suggestion.confidence * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Critical Points */}
      {analysis?.time_stop_suggestion?.critical_points && analysis.time_stop_suggestion.critical_points.length > 0 && (
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-yellow-500" />
              Critical Points
            </CardTitle>
            <CardDescription>Key inflection points in the survival curve</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4">
              {analysis.time_stop_suggestion.critical_points.map((point, idx) => (
                <div key={idx} className="p-4 bg-slate-800 rounded-lg">
                  <p className="text-sm text-slate-400">{point.type}</p>
                  <p className="text-xl font-bold text-white">
                    {point.time_hours.toFixed(1)}h
                  </p>
                  {point.survival_prob && (
                    <p className="text-sm text-slate-500">
                      S(t) = {(point.survival_prob * 100).toFixed(0)}%
                    </p>
                  )}
                  {point.hazard_rate && (
                    <p className="text-sm text-slate-500">
                      h(t) = {(point.hazard_rate * 100).toFixed(1)}%/h
                    </p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
