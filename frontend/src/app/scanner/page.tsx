"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface ScanRow {
  ticker: string;
  spot: number;
  expiry: string;
  pcr: number;
  max_pain: number;
  mp_dist_pct: number;
  signal: string;
  score: number;
  max_call_wall: number;
  max_put_wall: number;
}

interface ScanResult {
  results: ScanRow[];
  scanned: number;
  returned: number;
}

const DEFAULT_TICKERS = "AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,AMD,SPY,QQQ,IWM,JPM,NFLX,AVGO,CRM";

function signalBadge(signal: string) {
  if (signal.includes("STRONG BUY CALL")) return "bg-green-700 text-green-200";
  if (signal.includes("BUY CALL")) return "bg-green-900 text-green-300";
  if (signal.includes("STRONG BUY PUT")) return "bg-red-700 text-red-200";
  if (signal.includes("BUY PUT")) return "bg-red-900 text-red-300";
  return "bg-slate-700 text-slate-300";
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.min(Math.abs(score) / 6 * 100, 100);
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${score >= 0 ? "bg-green-400" : "bg-red-400"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-xs font-mono ${score > 0 ? "text-green-400" : score < 0 ? "text-red-400" : "text-slate-400"}`}>
        {score > 0 ? "+" : ""}{score}
      </span>
    </div>
  );
}

export default function ScannerPage() {
  const [tickers, setTickers] = useState(DEFAULT_TICKERS);
  const [expiryOffset, setExpiryOffset] = useState(0);
  const [submitted, setSubmitted] = useState(false);

  const { data, isLoading, error, refetch } = useQuery<ScanResult>({
    queryKey: ["scanner", tickers, expiryOffset, submitted],
    queryFn: () => api.get("/api/scanner/scan", { params: { tickers, expiry_offset: expiryOffset } }).then(r => r.data),
    enabled: submitted,
    staleTime: 2 * 60_000,
  });

  function handleScan() {
    if (submitted) {
      refetch();
    } else {
      setSubmitted(true);
    }
  }

  return (
    <main className="p-6 space-y-6 max-w-6xl">
      <h1 className="text-2xl font-bold text-white">Options OI Scanner</h1>
      <p className="text-slate-400 text-sm">
        Scans multiple tickers for their OI signal (PCR + Max Pain + OI walls), ranked by signal strength.
      </p>

      {/* Controls */}
      <div className="space-y-3">
        <div>
          <label className="block text-xs text-slate-400 mb-1">Tickers (comma-separated)</label>
          <input
            className="bg-surface-card border border-surface-border text-white rounded-lg px-3 py-2 text-sm w-full max-w-xl focus:outline-none focus:border-brand-500"
            value={tickers}
            onChange={e => setTickers(e.target.value)}
          />
        </div>
        <div className="flex gap-3 items-center">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Expiry</label>
            <div className="flex gap-2">
              {["Nearest", "Next week", "Third"].map((label, i) => (
                <button key={i} onClick={() => setExpiryOffset(i)}
                  className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${expiryOffset === i ? "bg-brand-600 text-white" : "bg-surface-card border border-surface-border text-slate-400 hover:text-white"}`}>
                  {label}
                </button>
              ))}
            </div>
          </div>
          <button
            onClick={handleScan}
            disabled={isLoading}
            className="mt-4 px-5 py-2 bg-brand-600 hover:bg-brand-500 disabled:bg-slate-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {isLoading ? "Scanning…" : "Scan"}
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center gap-3 text-slate-400">
          <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          <span>Fetching OI data for {tickers.split(",").length} tickers… this may take 30-60 seconds.</span>
        </div>
      )}
      {error && (
        <p className="text-red-400 bg-red-950/20 border border-red-800 rounded-lg px-4 py-3 text-sm">
          {(error as Error).message}
        </p>
      )}

      {data && (
        <>
          <div className="flex items-center gap-4">
            <p className="text-slate-400 text-sm">
              Scanned <span className="text-white font-medium">{data.scanned}</span> tickers,
              returned <span className="text-white font-medium">{data.returned}</span> results.
              Sorted by signal strength.
            </p>
          </div>

          {data.results.length === 0 ? (
            <p className="text-slate-500 py-8 text-center">No results returned. Check FutuOpenD connection.</p>
          ) : (
            <div className="bg-surface-card border border-surface-border rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-slate-500 text-xs border-b border-surface-border">
                    <th className="px-4 py-3 text-left">Ticker</th>
                    <th className="px-4 py-3 text-left">Spot</th>
                    <th className="px-4 py-3 text-left">Expiry</th>
                    <th className="px-4 py-3 text-left">PCR</th>
                    <th className="px-4 py-3 text-left">Max Pain</th>
                    <th className="px-4 py-3 text-left">MP Dist%</th>
                    <th className="px-4 py-3 text-left">Score</th>
                    <th className="px-4 py-3 text-left">Signal</th>
                    <th className="px-4 py-3 text-left">CE Wall</th>
                    <th className="px-4 py-3 text-left">PE Wall</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border">
                  {data.results.map((r, i) => (
                    <tr key={r.ticker} className={`hover:bg-surface-hover ${i === 0 ? "bg-brand-900/10" : ""}`}>
                      <td className="px-4 py-3 font-semibold text-white">{r.ticker}</td>
                      <td className="px-4 py-3 text-slate-200">${r.spot.toFixed(2)}</td>
                      <td className="px-4 py-3 text-slate-400 text-xs font-mono">{r.expiry}</td>
                      <td className="px-4 py-3 text-slate-200">{r.pcr.toFixed(2)}</td>
                      <td className="px-4 py-3 text-yellow-400">${r.max_pain.toFixed(2)}</td>
                      <td className={`px-4 py-3 text-xs font-mono ${r.mp_dist_pct < 0 ? "text-green-400" : "text-red-400"}`}>
                        {r.mp_dist_pct > 0 ? "+" : ""}{r.mp_dist_pct.toFixed(1)}%
                      </td>
                      <td className="px-4 py-3"><ScoreBar score={r.score} /></td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${signalBadge(r.signal)}`}>
                          {r.signal.replace(/ 📈| 📉| ⚖️/g, "")}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-blue-400">${r.max_call_wall.toFixed(0)}</td>
                      <td className="px-4 py-3 text-red-400">${r.max_put_wall.toFixed(0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {!submitted && (
        <div className="text-center py-20 text-slate-500">
          <p className="text-lg">Configure tickers and click Scan to start.</p>
          <p className="text-sm mt-1">Note: each scan makes live API calls to FutuOpenD — allow 30-60 seconds for a full scan.</p>
        </div>
      )}
    </main>
  );
}
