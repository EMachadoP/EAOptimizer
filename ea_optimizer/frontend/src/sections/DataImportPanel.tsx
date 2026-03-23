import { useMemo, useState } from 'react';
import type { ChangeEvent } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { apiUrl } from '@/lib/api';
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

const IMPORT_TIMEOUT_MS = 90000;

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

  const marketSourceLabel = useMemo(
    () => marketFile?.name || marketPath || 'No market file selected',
    [marketFile, marketPath]
  );
  const tradesSourceLabel = useMemo(
    () => tradesFile?.name || tradesPath || 'No trade file selected',
    [tradesFile, tradesPath]
  );

  const updateSelectedFile = (
    event: ChangeEvent<HTMLInputElement>,
    type: 'market' | 'trades'
  ) => {
    const file = event.target.files?.[0] || null;
    setImportStatus({ type: null, status: 'idle', message: '' });
    if (type === 'market') {
      setMarketFile(file);
      if (file) setMarketPath('');
    } else {
      setTradesFile(file);
      if (file) setTradesPath('');
    }
  };

  const fetchWithTimeout = async (input: RequestInfo | URL, init?: RequestInit) => {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), IMPORT_TIMEOUT_MS);

    try {
      return await fetch(input, {
        ...init,
        signal: controller.signal,
      });
    } finally {
      window.clearTimeout(timeoutId);
    }
  };

  const handleMarketImport = async () => {
    if (!marketFile && !marketPath) {
      setImportStatus({
        type: 'market',
        status: 'error',
        message: 'Choose a CSV file or provide a server file path'
      });
      return;
    }

    setImportStatus({
      type: 'market',
      status: 'processing',
      message: 'Importing market data...'
    });

    try {
      const res = marketFile
        ? await (() => {
            const formData = new FormData();
            formData.append('file', marketFile);
            formData.append('symbol', 'XAUUSD');
            return fetchWithTimeout(apiUrl('/api/import/market-data'), {
              method: 'POST',
              body: formData
            });
          })()
        : await fetchWithTimeout(apiUrl('/api/import/market-data'), {
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
        setMarketFile(null);
        setMarketPath('');
      } else {
        const error = await res.json();
        setImportStatus({
          type: 'market',
          status: 'error',
          message: error.error || 'Failed to import market data'
        });
      }
    } catch (e) {
      const message =
        e instanceof DOMException && e.name === 'AbortError'
          ? 'Import timed out. Please try a smaller file or retry in a moment.'
          : 'Network error. Is the backend running?';
      setImportStatus({
        type: 'market',
        status: 'error',
        message
      });
    }
  };

  const handleTradesImport = async () => {
    if (!tradesFile && !tradesPath) {
      setImportStatus({
        type: 'trades',
        status: 'error',
        message: 'Choose a CSV/HTML file or provide a server file path'
      });
      return;
    }

    setImportStatus({
      type: 'trades',
      status: 'processing',
      message: 'Importing trades...'
    });

    try {
      const res = tradesFile
        ? await (() => {
            const formData = new FormData();
            formData.append('file', tradesFile);
            formData.append('symbol', 'XAUUSD');
            return fetchWithTimeout(apiUrl('/api/import/trades'), {
              method: 'POST',
              body: formData
            });
          })()
        : await fetchWithTimeout(apiUrl('/api/import/trades'), {
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
        setTradesFile(null);
        setTradesPath('');
      } else {
        const error = await res.json();
        setImportStatus({
          type: 'trades',
          status: 'error',
          message: error.error || 'Failed to import trades'
        });
      }
    } catch (e) {
      const message =
        e instanceof DOMException && e.name === 'AbortError'
          ? 'Import timed out. Please try a smaller file or retry in a moment.'
          : 'Network error. Is the backend running?';
      setImportStatus({
        type: 'trades',
        status: 'error',
        message
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
          <CardTitle className="text-lg text-white flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-blue-500" />
            Market Data Import
          </CardTitle>
          <CardDescription className="text-slate-300">
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

            <div className="rounded-xl border border-slate-700 bg-slate-800/70 p-4">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-sm font-medium text-white">Choose market CSV</p>
                  <p className="text-xs text-slate-400">Upload directly from your computer to the backend</p>
                </div>
                <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-blue-500/40 bg-blue-500/10 px-4 py-2 text-sm font-medium text-blue-100 hover:bg-blue-500/20">
                  <FolderOpen className="w-4 h-4" />
                  Browse File
                  <Input
                    type="file"
                    accept=".csv,text/csv"
                    className="hidden"
                    onChange={(event) => updateSelectedFile(event, 'market')}
                  />
                </label>
              </div>
              <p className="mt-3 rounded-lg bg-slate-950/70 px-3 py-2 text-sm text-slate-300">
                {marketSourceLabel}
              </p>
            </div>

            <div className="flex gap-2">
              <div className="flex-1 space-y-2">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Optional server path</p>
                <Input
                  placeholder="/var/data/XAUUSD_H1.csv"
                  value={marketPath}
                  onChange={(e) => {
                    setMarketPath(e.target.value);
                    if (e.target.value) setMarketFile(null);
                  }}
                  className="bg-slate-800 border-slate-700 text-slate-100 placeholder:text-slate-500"
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

            <div className="flex items-center gap-2 text-sm text-slate-400">
              <FolderOpen className="w-4 h-4" />
              <span>You can upload a local file or use a path that already exists on the server.</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Trades Import */}
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="text-lg text-white flex items-center gap-2">
            <Activity className="w-5 h-5 text-green-500" />
            Trade History Import
          </CardTitle>
          <CardDescription className="text-slate-300">
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

            <div className="rounded-xl border border-slate-700 bg-slate-800/70 p-4">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-sm font-medium text-white">Choose trade file</p>
                  <p className="text-xs text-slate-400">Supports MT5 CSV exports and Strategy Tester HTML reports</p>
                </div>
                <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-green-500/40 bg-green-500/10 px-4 py-2 text-sm font-medium text-green-100 hover:bg-green-500/20">
                  <FileText className="w-4 h-4" />
                  Browse File
                  <Input
                    type="file"
                    accept=".csv,.html,.htm,text/csv,text/html"
                    className="hidden"
                    onChange={(event) => updateSelectedFile(event, 'trades')}
                  />
                </label>
              </div>
              <p className="mt-3 rounded-lg bg-slate-950/70 px-3 py-2 text-sm text-slate-300">
                {tradesSourceLabel}
              </p>
            </div>

            <div className="flex gap-2">
              <div className="flex-1 space-y-2">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Optional server path</p>
                <Input
                  placeholder="/var/data/trades.csv"
                  value={tradesPath}
                  onChange={(e) => {
                    setTradesPath(e.target.value);
                    if (e.target.value) setTradesFile(null);
                  }}
                  className="bg-slate-800 border-slate-700 text-slate-100 placeholder:text-slate-500"
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

            <div className="flex items-center gap-2 text-sm text-slate-400">
              <FileText className="w-4 h-4" />
              <span>Also supports MT5 Strategy Tester HTML reports</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Database Status */}
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="text-lg text-white flex items-center gap-2">
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
          <CardTitle className="text-lg text-white">Import Instructions</CardTitle>
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
                Import, or use the Browse button to upload the file directly from your computer.
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

      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="text-lg text-white">Direct MT5 Sync</CardTitle>
          <CardDescription className="text-slate-300">
            Use the desktop bridge on the same Windows machine where MetaTrader 5 is open.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3 text-sm text-slate-300">
            <p>
              This cloud app cannot access your local MT5 terminal directly. To avoid CSV exports,
              run the local sync script from the project folder on your Windows desktop.
            </p>
            <code className="block rounded-lg bg-slate-950 px-3 py-3 text-xs text-slate-200">
              python sync_mt5_to_cloud.py --api-url https://eaoptimizer.onrender.com --symbol XAUUSD --days 30
            </code>
            <p className="text-slate-400">
              Keep MT5 open and logged in while the command runs. The script will fetch market data
              and trades locally, then upload them to the hosted backend.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
