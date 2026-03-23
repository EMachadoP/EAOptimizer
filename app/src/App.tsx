import { useState, useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { 
  Activity, 
  TrendingUp, 
  Shield, 
  BarChart3, 
  Settings, 
  Database,
  AlertTriangle,
  CheckCircle
} from 'lucide-react';

import DashboardSummary from './sections/DashboardSummary';
import RegimeAnalysisPanel from './sections/RegimeAnalysisPanel';
import SurvivalAnalysisPanel from './sections/SurvivalAnalysisPanel';
import RobustnessMappingPanel from './sections/RobustnessMappingPanel';
import OptimizationPanel from './sections/OptimizationPanel';
import DataImportPanel from './sections/DataImportPanel';

import './App.css';

interface SystemStatus {
  backend: boolean;
  database: boolean;
  marketData: boolean;
  trades: boolean;
}

function App() {
  const [status, setStatus] = useState<SystemStatus>({
    backend: false,
    database: false,
    marketData: false,
    trades: false
  });
  const [activeTab, setActiveTab] = useState('dashboard');

  useEffect(() => {
    // Check system status
    checkSystemStatus();
  }, []);

  const checkSystemStatus = async () => {
    try {
      const response = await fetch('http://localhost:5000/api/health');
      if (response.ok) {
        setStatus(prev => ({ ...prev, backend: true }));
      }
    } catch (e) {
      console.log('Backend not available');
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-600 rounded-lg">
                <Activity className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-white">
                  EA Configuration Optimizer
                </h1>
                <p className="text-xs text-slate-400">
                  v1.2 FINAL • Sistema Quantitativo de Otimização
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Badge variant={status.backend ? 'default' : 'destructive'} className="gap-1">
                  {status.backend ? <CheckCircle className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
                  Backend
                </Badge>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-6">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid grid-cols-6 gap-4 bg-slate-900/50 p-1">
            <TabsTrigger value="dashboard" className="gap-2">
              <BarChart3 className="w-4 h-4" />
              Dashboard
            </TabsTrigger>
            <TabsTrigger value="regime" className="gap-2">
              <TrendingUp className="w-4 h-4" />
              Regime Detection
            </TabsTrigger>
            <TabsTrigger value="survival" className="gap-2">
              <Activity className="w-4 h-4" />
              Survival Analysis
            </TabsTrigger>
            <TabsTrigger value="robustness" className="gap-2">
              <Shield className="w-4 h-4" />
              Robustness
            </TabsTrigger>
            <TabsTrigger value="optimization" className="gap-2">
              <Settings className="w-4 h-4" />
              Optimization
            </TabsTrigger>
            <TabsTrigger value="data" className="gap-2">
              <Database className="w-4 h-4" />
              Data Import
            </TabsTrigger>
          </TabsList>

          <TabsContent value="dashboard" className="space-y-4">
            <DashboardSummary />
          </TabsContent>

          <TabsContent value="regime" className="space-y-4">
            <RegimeAnalysisPanel />
          </TabsContent>

          <TabsContent value="survival" className="space-y-4">
            <SurvivalAnalysisPanel />
          </TabsContent>

          <TabsContent value="robustness" className="space-y-4">
            <RobustnessMappingPanel />
          </TabsContent>

          <TabsContent value="optimization" className="space-y-4">
            <OptimizationPanel />
          </TabsContent>

          <TabsContent value="data" className="space-y-4">
            <DataImportPanel />
          </TabsContent>
        </Tabs>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 bg-slate-900/50 mt-12">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between text-sm text-slate-500">
            <p>EA Configuration Optimizer v1.2 • PRD FINAL</p>
            <div className="flex gap-4">
              <span>FR-14: Regime Detection</span>
              <span>FR-15: Survival Analysis</span>
              <span>FR-16: Robustness Mapping</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
