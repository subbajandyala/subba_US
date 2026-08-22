"use client";
import { useState } from "react";
import { useQuery, useQueries } from "@tanstack/react-query";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { api } from "@/lib/api";

interface ExpirySignal {
  expiry: string;
  pcr: number;
  max_pain: number;
  signal: string;
  score: number;
  max_call_wall: number;
  max_put_wall: number;
  mp_dist_pct: number;
  total_ce_oi: number;
  total_pe_oi: number;
}

function scoreColor(s: number) {
  if (s >= 4) return "#22c55e";
  if (s >= 2) return "#86efac";
  if (s <= -4) return "#ef4444";
  if (s <= -2) return "#fca5a5";
  return "#94a3b8";
}

function signalBadge(signal: string) {
  if (signal.includes("STRONG BUY CALL")) return "bg-green-700 text-green-100";
  if (signal.includes("BUY CALL")) return "bg-green-900 text-green-300";
  if (signal.includes("STRONG BUY PUT")) return "bg-red-700 text-red-100";
  if (signal.includes("BUY PUT")) return "bg-red-900 text-red-300";
  return "bg-slate-700 text-slate-300";
}

export default function SmartSignalPage() {
  const [inputTicker, setInputTicker] = useState("AAPL");
  const [ticker, setTicker] = useState("AAPL");

  const { data: expirations } = useQuery<string[]>({
    queryKey: ["expirations", ticker],
    queryFn: () => api.get(`/api/options/${ticker}/expirations`).then(r => r.data),
    staleTime: 5 * 60_000,
  });

  const expiriesToScan = (expirations || []).slice(0, 6);

  const signalQueries = useQueries({
    queries: expiriesToScan.map(expiry => ({
      queryKey: ["oi-signal-smart", ticker, expiry],
      queryFn: () =>
        api.get(`/api/options/${ticker}/oi-signal`, { params: { expiry, strikes_atm: 20 } })
          .then(r => ({
            expiry: r.data.expiry as string,
            pcr: r.data.pcr as number,
            max_pain: r.data.max_pain as number,
            signal: r.data.signal as string,
            score: r.data.score as number,
            max_call_wall: r.data.max_call_wall as number,
            max_put_wall: r.data.max_put_wall as number,
            mp_dist_pct: ((r.data.spot - r.data.max_pain) / r.data.max_pain) * 100,
            total_ce_oi: r.data.total_ce_oi as number,
            total_pe_oi: r.data.total_pe_oi as number,
          })),
      enabled: !!expiry,
      staleTime: 2 * 60_000,
    })),
  });

  const results: ExpirySignal[] = signalQueries
    .filter(q => q.data)
    .map(q => q.data as ExpirySignal);

  const isLoading = signalQueries.some(q => q.isLoading);
  const loadedCount = signalQueries.filter(q => q.data).length;

  const best = results.reduce<ExpirySignal | null>((acc, r) => {
    if (!acc || Math.abs(r.score) > Math.abs(acc.score)) return r;
    return acc;
  }, null);

  function handleSearch() {
    setTicker(inputTicker.toUpperCase().trim());
  }

  return (
    <main className="p-6 space-y-6 max-w-6xl">
      <h1 className="text-2xl font-bold text-white">Smart Signal</h1>
      <p className="text-slate-400 text-sm">
        Compares OI signals across all available expiries for a single ticker. Identifies which expiry has the strongest directional bias.
      </p>

      <div className="flex gap-3 items-end">
        <div>
          <label className="block text-xs text-slate-400 mb-1">Ticker</label>
          <input
            className="bg-surface-card border border-surface-border text-white rounded-lg px-3 py-2 w-28 text-sm focus:outline-none focus:border-brand-500"
            value={inputTicker}
            onChange={e => setInputTicker(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleSearch()}
          />
        </div>
        <button
          onClick={handleSearch}
          className="px-5 py-2 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-sm font-medium transition-colors"
        >
          Analyze All Expiries
        </button>
      </div>

      {expirations && expiriesToScan.length > 0 && (
        <p className="text-slate-500 text-xs">
          Scanning {expiriesToScan.length} expiries for {ticker}… loaded {loadedCount}/{expiriesToScan.length}
        </p>
      )}

      {isLoading && loadedCount === 0 && (
        <div className="flex items-center gap-3 text-slate-400">
          <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          <span>Fetching OI data…</span>
        </div>
      )}

      {best && (
        <div className="bg-brand-900/20 border border-brand-600 rounded-2xl px-6 py-4">
          <p className="text-xs text-brand-400 uppercase tracking-wider mb-1">Strongest Signal</p>
          <p className={`text-2xl font-bold ${best.score >= 0 ? "text-green-300" : "text-red-300"}`}>{best.signal}</p>
          <p className="text-slate-400 text-sm mt-1">
            Expiry: <span className="text-white">{best.expiry}</span> &nbsp;·&nbsp;
            Score: <span className={best.score >= 0 ? "text-green-400" : "text-red-400"}>{best.score > 0 ? "+" : ""}{best.score}</span> &nbsp;·&nbsp;
            PCR: {best.pcr.toFixed(2)} &nbsp;·&nbsp; Max Pain: ${best.max_pain.toFixed(2)}
          </p>
        </div>
      )}

      {results.length > 0 && (
        <>
          <div className="bg-surface-card border border-surface-border rounded-xl p-5">
            <h2 className="text-sm font-semibold text-white mb-4">OI Score by Expiry</h2>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={results} margin={{ top: 4, right: 10, left: 0, bottom: 4 }}>
                <XAxis dataKey="expiry" tick={{ fill: "#94a3b8", fontSize: 10 }} />
                <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} domain={[-6, 6]} />
                <Tooltip
                  contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
                  formatter={(v: number) => [`${v > 0 ? "+" : ""}${v}`, "Score"]}
                />
                <Bar dataKey="score" radius={[3, 3, 0, 0]}>
                  {results.map((r, i) => (
                    <Cell key={i} fill={scoreColor(r.score)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-surface-card border border-surface-border rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-surface-border">
              <h2 className="text-sm font-semibold text-white">All Expiries — {ticker}</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-slate-500 text-xs border-b border-surface-border">
                    <th className="px-4 py-2 text-left">Expiry</th>
                    <th className="px-4 py-2 text-left">Score</th>
                    <th className="px-4 py-2 text-left">Signal</th>
                    <th className="px-4 py-2 text-left">PCR</th>
                    <th className="px-4 py-2 text-left">Max Pain</th>
                    <th className="px-4 py-2 text-left">MP Dist%</th>
                    <th className="px-4 py-2 text-left">CE OI</th>
                    <th className="px-4 py-2 text-left">PE OI</th>
                    <th className="px-4 py-2 text-left">CE Wall</th>
                    <th className="px-4 py-2 text-left">PE Wall</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border">
                  {results.map(r => (
                    <tr key={r.expiry} className={`hover:bg-surface-hover ${r.expiry === best?.expiry ? "bg-brand-900/10" : ""}`}>
                      <td className="px-4 py-3 font-mono text-xs text-white">{r.expiry}</td>
                      <td className="px-4 py-3">
                        <span className={`font-semibold ${r.score > 0 ? "text-green-400" : r.score < 0 ? "text-red-400" : "text-slate-400"}`}>
                          {r.score > 0 ? "+" : ""}{r.score}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${signalBadge(r.signal)}`}>
                          {r.signal.replace(/ 📈| 📉| ⚖️/g, "")}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-200">{r.pcr.toFixed(2)}</td>
                      <td className="px-4 py-3 text-yellow-400">${r.max_pain.toFixed(2)}</td>
                      <td className={`px-4 py-3 text-xs font-mono ${r.mp_dist_pct < 0 ? "text-green-400" : "text-red-400"}`}>
                        {r.mp_dist_pct > 0 ? "+" : ""}{r.mp_dist_pct.toFixed(1)}%
                      </td>
                      <td className="px-4 py-3 text-blue-400">{(r.total_ce_oi / 1000).toFixed(1)}K</td>
                      <td className="px-4 py-3 text-red-400">{(r.total_pe_oi / 1000).toFixed(1)}K</td>
                      <td className="px-4 py-3 text-blue-300">${r.max_call_wall.toFixed(0)}</td>
                      <td className="px-4 py-3 text-red-300">${r.max_put_wall.toFixed(0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {!expirations && (
        <div className="text-center py-20 text-slate-500">
          <p className="text-lg">Enter a ticker and click Analyze to compare OI signals across all expiries.</p>
        </div>
      )}
    </main>
  );
}
