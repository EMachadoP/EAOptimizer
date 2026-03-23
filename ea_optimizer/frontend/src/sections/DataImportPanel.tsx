import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import { 
  Upload, 
  Database, 
  FileText, 
  CheckCircle, 
  AlertTriangle,
  TrendingUp,
  Activity,
  FolderOpen
} from 'lucide-react';

interface ImportStatus {
  type: 'market' | 'trades' | null;
  status: 'idle' | 'uploading' | 'processing' | 'success' | 'error';
  message: string;
  records?: number;
  error?: string;
}

export default function DataImportPanel() {
  const [marketFile, setMarketFile] = useState<File | null>(null);
  const [tradesFile, setTradesFile] = useState<File | null>(null);
  const [marketPath, setMarketPath] = useState('');
  const [tradesPath, setTradesPath] = useState('');
  const [importStatus, setImportStatus] = useState<ImportStatus>({
    type: null,
    status: 'idle',
    message: ''
  });

  const handleMarketImport = async () => {
    if (!marketPath) {
      setImportStatus({
        type: 'market',
        status: 'error',
        message: 'Please provide a file path'
      });
      return;
    }

    setImportStatus({
      type: 'market',
      status: 'processing',
      message: 'Importing market data...'
    });

    try {
      const res = await fetch('http://localhost:5000/api/import/market-data', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          csv_path: marketPath,
          symbol: 'XAUUSD'
        })
      });

      if (res.ok) {
        const data = await res.json();
        setImportStatus({
          type: 'market',
          status: 'success',
          message: `Successfully imported ${data.records_imported} market data records`,
          records: data.records_imported
        });
      } else {
        const error = await res.json();
        setImportStatus({
          type: 'market',
          status: 'error',
          message: error.error || 'Failed to import market data'
        });
      }
    } catch (e) {
      setImportStatus({
        type: 'market',
        status: 'error',
        message: 'Network error. Is the backend running?'
      });
    }
  };

  const handleTradesImport = async () => {
    if (!tradesPath) {
      setImportStatus({
        type: 'trades',
        status: 'error',
        message: 'Please provide a file path'
      });
      return;
    }

    setImportStatus({
      type: 'trades',
      status: 'processing',
      message: 'Importing trades...'
    });

    try {
      const res = await fetch('http://localhost:5000/api/import/trades', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          csv_path: tradesPath,
          symbol: 'XAUUSD'
        })
      });

      if (res.ok) {
        const data = await res.json();
        setImportStatus({
          type: 'trades',
          status: 'success',
          message: `Successfully imported ${data.records_imported} trades`,
          records: data.records_imported
        });
      } else {
        const error = await res.json();
        setImportStatus({
          type: 'trades',
          status: 'error',
          message: error.error || 'Failed to import trades'
        });
      }
    } catch (e) {
      setImportStatus({
        type: 'trades',
        status: 'error',
        message: 'Network error. Is the backend running?'
      });
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white">Data Import</h2>
        <p className="text-slate-400">FR-01/02: Import MT5 market data and trade history</p>
      </div>

      {/* Status Alert */}
      {importStatus.status !== 'idle' && (
        <Alert 
          className={`${
            importStatus.status === 'success' ? 'bg-green-500/10 border-green-500/30' :
            importStatus.status === 'error' ? 'bg-red-500/10 border-red-500/30' :
            'bg-blue-500/10 border-blue-500/30'
          }`}
        >
          {importStatus.status === 'success' ? (
            <CheckCircle className="w-5 h-5 text-green-500" />
          ) : importStatus.status === 'error' ? (
            <AlertTriangle className="w-5 h-5 text-red-500" />
          ) : (
            <Activity className="w-5 h-5 text-blue-500 animate-pulse" />
          )}
          <AlertDescription className="text-slate-300 ml-2">
            {importStatus.message}
          </AlertDescription>
        </Alert>
      )}

      {/* Market Data Import */}
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-blue-500" />
            Market Data Import
          </CardTitle>
          <CardDescription>
            Import OHLCV data from MT5 (CSV format)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="p-4 bg-slate-800 rounded-lg">
              <p className="text-sm text-slate-400 mb-2">Expected CSV format:</p>
              <code className="text-xs text-slate-300 block bg-slate-950 p-2 rounded">
                time,open,high,low,close,volume<br/>
                2024-01-01 00:00,2050.50,2051.20,2049.80,2050.90,1000
              </code>
            </div>

            <div className="flex gap-2">
              <div className="flex-1">
                <Input
                  placeholder="/path/to/XAUUSD_H1.csv"
                  value={marketPath}
                  onChange={(e) => setMarketPath(e.target.value)}
                  className="bg-slate-800 border-slate-700"
                />
              </div>
              <Button 
                onClick={handleMarketImport}
                disabled={importStatus.status === 'processing'}
                className="gap-2"
              >
                <Upload className="w-4 h-4" />
                Import
              </Button>
            </div>

            <div className="flex items-center gap-2 text-sm text-slate-500">
              <FolderOpen className="w-4 h-4" />
              <span>Or place CSV files in the /data directory</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Trades Import */}
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Activity className="w-5 h-5 text-green-500" />
            Trade History Import
          </CardTitle>
          <CardDescription>
            Import EA trade history from MT5 (CSV or HTML report)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="p-4 bg-slate-800 rounded-lg">
              <p className="text-sm text-slate-400 mb-2">Expected CSV format:</p>
              <code className="text-xs text-slate-300 block bg-slate-950 p-2 rounded">
                ticket,time_open,time_close,type,volume,price_open,price_close,commission,swap,profit<br/>
                12345678,2024-01-01 10:00,2024-01-01 12:00,0,0.01,2050.50,2051.00,-0.07,0.00,5.00
              </code>
            </div>

            <div className="flex gap-2">
              <div className="flex-1">
                <Input
                  placeholder="/path/to/trades.csv"
                  value={tradesPath}
                  onChange={(e) => setTradesPath(e.target.value)}
                  className="bg-slate-800 border-slate-700"
                />
              </div>
              <Button 
                onClick={handleTradesImport}
                disabled={importStatus.status === 'processing'}
                className="gap-2"
              >
                <Upload className="w-4 h-4" />
                Import
              </Button>
            </div>

            <div className="flex items-center gap-2 text-sm text-slate-500">
              <FileText className="w-4 h-4" />
              <span>Also supports MT5 Strategy Tester HTML reports</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Database Status */}
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Database className="w-5 h-5 text-purple-500" />
            Database Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-4 gap-4">
            <div className="p-4 bg-slate-800 rounded-lg text-center">
              <p className="text-sm text-slate-400">Market Data</p>
              <p className="text-2xl font-bold text-white">-</p>
              <p className="text-xs text-slate-500">bars</p>
            </div>
            <div className="p-4 bg-slate-800 rounded-lg text-center">
              <p className="text-sm text-slate-400">Trades</p>
              <p className="text-2xl font-bold text-white">-</p>
              <p className="text-xs text-slate-500">records</p>
            </div>
            <div className="p-4 bg-slate-800 rounded-lg text-center">
              <p className="text-sm text-slate-400">Baskets</p>
              <p className="text-2xl font-bold text-white">-</p>
              <p className="text-xs text-slate-500">reconstructed</p>
            </div>
            <div className="p-4 bg-slate-800 rounded-lg text-center">
              <p className="text-sm text-slate-400">Configs</p>
              <p className="text-2xl font-bold text-white">-</p>
              <p className="text-xs text-slate-500">tested</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Instructions */}
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="text-lg">Import Instructions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4 text-sm text-slate-400">
            <div className="flex gap-3">
              <Badge variant="outline" className="shrink-0">1</Badge>
              <p>
                <strong className="text-white">Export from MT5:</strong> Use the Strategy Tester 
                to export your EA results or use the MT5 History Center to export tick data.
              </p>
            </div>
            <div className="flex gap-3">
              <Badge variant="outline" className="shrink-0">2</Badge>
              <p>
                <strong className="text-white">Format:</strong> Ensure CSV files have the correct 
                column headers. The system expects standard MT5 export format.
              </p>
            </div>
            <div className="flex gap-3">
              <Badge variant="outline" className="shrink-0">3</Badge>
              <p>
                <strong className="text-white">Import:</strong> Provide the full file path and click 
                Import. Data will be validated and stored in the SQLite database.
              </p>
            </div>
            <div className="flex gap-3">
              <Badge variant="outline" className="shrink-0">4</Badge>
              <p>
                <strong className="text-white">Analyze:</strong> Once imported, use the Dashboard 
                and other tabs to analyze your EA performance.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
