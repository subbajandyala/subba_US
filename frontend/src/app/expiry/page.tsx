"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from "recharts";
import { api } from "@/lib/api";

interface ExpiryData {
  ticker: string;
  expiry: string;
  spot: number;
  atm: number;
  max_pain: number;
  pcr: number;
  mp_dist_pct: number;
  rocket_up: boolean;
  rocket_down: boolean;
  signal: string;
  score: number;
  details: { indicator: string; value: string; verdict: string; explanation: string }[];
  max_call_wall: number;
  max_put_wall: number;
  total_ce_oi: number;
  total_pe_oi: number;
  oi_chart: { strike: number; CE: number; PE: number }[];
}

const TICKERS = ["SPY", "QQQ", "IWM", "DIA", "AAPL", "TSLA", "NVDA", "MSFT"];
const EXPIRY_LABELS = ["Nearest (0)", "Next (1)", "Third (2)"];

function MetricCard({ label, value, highlight = false }: { label: string; value: string | number; highlight?: boolean }) {
  return (
    <div className={`rounded-xl px-5 py-4 border ${highlight ? "bg-yellow-950/20 border-yellow-700" : "bg-surface-card border-surface-border"}`}>
      <p className="text-slate-500 text-xs uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-xl font-semibold ${highlight ? "text-yellow-300" : "text-white"}`}>{value}</p>
    </div>
  );
}

function signalColor(signal: string) {
  if (signal.includes("BUY CALL")) return "border-green-500 bg-green-950/20 text-green-400";
  if (signal.includes("BUY PUT")) return "border-red-500 bg-red-950/20 text-red-400";
  return "border-yellow-600 bg-yellow-950/10 text-yellow-400";
}

export default function ExpiryPage() {
  const [ticker, setTicker] = useState("SPY");
  const [expiryOffset, setExpiryOffset] = useState(0);

  const { data, isLoading, error, refetch } = useQuery<ExpiryData>({
    queryKey: ["expiry", ticker, expiryOffset],
    queryFn: () => api.get("/api/expiry/analyze", { params: { ticker, expiry_offset: expiryOffset } }).then(r => r.data),
    refetchInterval: 60_000,
  });

  return (
    <main className="p-6 space-y-6 max-w-6xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Expiry Analyzer</h1>
        {data && (
          <button onClick={() => refetch()} className="px-4 py-2 border border-surface-border text-slate-400 rounded-lg text-sm hover:text-white transition-colors">
            Refresh
          </button>
        )}
      </div>
      <p className="text-slate-400 text-sm">
        Analyzes Max Pain & PCR for the nearest expiry. Flags "Rocket" conditions when spot deviates sharply from Max Pain.
      </p>

      {/* Controls */}
      <div className="flex flex-wrap gap-3">
        <div>
          <label className="block text-xs text-slate-400 mb-1">Ticker</label>
          <div className="flex gap-2 flex-wrap">
            {TICKERS.map(t => (
              <button key={t} onClick={() => setTicker(t)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${ticker === t ? "bg-brand-600 text-white" : "bg-surface-card border border-surface-border text-slate-400 hover:text-white"}`}>
                {t}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Expiry</label>
          <div className="flex gap-2">
            {EXPIRY_LABELS.map((label, i) => (
              <button key={i} onClick={() => setExpiryOffset(i)}
                className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${expiryOffset === i ? "bg-brand-600 text-white" : "bg-surface-card border border-surface-border text-slate-400 hover:text-white"}`}>
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center gap-3 text-slate-400">
          <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          <span>Fetching expiry data for {ticker}…</span>
        </div>
      )}
      {error && (
        <p className="text-red-400 bg-red-950/20 border border-red-800 rounded-lg px-4 py-3 text-sm">
          {(error as Error).message}
        </p>
      )}

      {data && (
        <>
          {/* Rocket alert */}
          {(data.rocket_up || data.rocket_down) && (
            <div className={`rounded-2xl border-2 px-6 py-4 ${data.rocket_up ? "border-green-500 bg-green-950/30" : "border-red-500 bg-red-950/30"}`}>
              <p className={`text-xl font-bold ${data.rocket_up ? "text-green-300" : "text-red-300"}`}>
                {data.rocket_up ? "🚀 EXPIRY ROCKET UP — Spot far below Max Pain" : "🔻 EXPIRY DROP — Spot far above Max Pain"}
              </p>
              <p className="text-sm text-slate-400 mt-1">
                Spot is {Math.abs(data.mp_dist_pct).toFixed(1)}% {data.mp_dist_pct < 0 ? "below" : "above"} Max Pain. Option writers will likely push spot toward ${data.max_pain.toFixed(2)}.
              </p>
            </div>
          )}

          {/* Metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <MetricCard label="Spot" value={`$${data.spot.toFixed(2)}`} />
            <MetricCard label="ATM" value={`$${data.atm.toFixed(2)}`} />
            <MetricCard label="Max Pain" value={`$${data.max_pain.toFixed(2)}`} highlight />
            <MetricCard label="MP Dist%" value={`${data.mp_dist_pct > 0 ? "+" : ""}${data.mp_dist_pct.toFixed(2)}%`} />
            <MetricCard label="PCR" value={data.pcr.toFixed(2)} />
            <MetricCard label="Expiry" value={data.expiry} />
          </div>

          {/* OI totals */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-blue-950/20 border border-blue-800 rounded-xl px-5 py-4">
              <p className="text-xs text-blue-400 uppercase tracking-wider mb-1">Total Call OI</p>
              <p className="text-2xl font-bold text-white">{(data.total_ce_oi / 1000).toFixed(1)}K</p>
            </div>
            <div className="bg-red-950/20 border border-red-800 rounded-xl px-5 py-4">
              <p className="text-xs text-red-400 uppercase tracking-wider mb-1">Total Put OI</p>
              <p className="text-2xl font-bold text-white">{(data.total_pe_oi / 1000).toFixed(1)}K</p>
            </div>
          </div>

          {/* Signal */}
          <div className={`border-2 rounded-2xl px-6 py-4 ${signalColor(data.signal)}`}>
            <p className="text-2xl font-bold">{data.signal}</p>
            <p className="text-sm opacity-70 mt-1">Score: {data.score > 0 ? "+" : ""}{data.score}</p>
          </div>

          {/* OI Chart */}
          {data.oi_chart.length > 0 && (
            <div className="bg-surface-card border border-surface-border rounded-xl p-5">
              <h2 className="text-sm font-semibold text-white mb-4">OI Distribution — {data.ticker} {data.expiry}</h2>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={data.oi_chart} margin={{ top: 4, right: 10, left: 10, bottom: 4 }}>
                  <XAxis dataKey="strike" tick={{ fill: "#94a3b8", fontSize: 11 }} tickFormatter={v => `$${v}`} />
                  <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} tickFormatter={v => `${(v / 1000).toFixed(0)}K`} />
                  <Tooltip
                    contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
                    formatter={(v: number, name: string) => [v.toLocaleString(), name]}
                    labelFormatter={v => `Strike $${v}`}
                  />
                  <Legend />
                  <ReferenceLine x={data.max_pain} stroke="#f59e0b" strokeDasharray="4 2" label={{ value: "MaxPain", fill: "#f59e0b", fontSize: 10 }} />
                  <Bar dataKey="CE" name="Call OI" fill="#3b82f6" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="PE" name="Put OI" fill="#ef4444" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Details table */}
          <div className="bg-surface-card border border-surface-border rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-surface-border">
              <h2 className="text-sm font-semibold text-white">Signal Breakdown</h2>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-500 text-xs">
                  <th className="px-5 py-2 text-left">Indicator</th>
                  <th className="px-5 py-2 text-left">Value</th>
                  <th className="px-5 py-2 text-left">Verdict</th>
                  <th className="px-5 py-2 text-left">Explanation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border">
                {data.details.map((d, i) => (
                  <tr key={i} className="hover:bg-surface-hover">
                    <td className="px-5 py-3 font-medium text-white">{d.indicator}</td>
                    <td className="px-5 py-3 text-slate-300 font-mono text-xs">{d.value}</td>
                    <td className="px-5 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${d.verdict.includes("Bullish") ? "bg-green-900 text-green-300" : d.verdict.includes("Bearish") ? "bg-red-900 text-red-300" : "bg-slate-700 text-slate-300"}`}>{d.verdict}</span>
                    </td>
                    <td className="px-5 py-3 text-slate-400 text-xs">{d.explanation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Key levels */}
          <div className="bg-surface-card border border-surface-border rounded-xl px-5 py-4">
            <h2 className="text-sm font-semibold text-white mb-3">Key OI Levels</h2>
            <div className="flex gap-8">
              <div>
                <p className="text-xs text-slate-500 mb-0.5">Resistance (Call Wall)</p>
                <p className="text-lg font-semibold text-blue-400">${data.max_call_wall.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500 mb-0.5">Support (Put Wall)</p>
                <p className="text-lg font-semibold text-red-400">${data.max_put_wall.toFixed(2)}</p>
              </div>
            </div>
          </div>
        </>
      )}
    </main>
  );
}
