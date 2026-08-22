"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from "recharts";
import { api } from "@/lib/api";

interface SignalDetail {
  indicator: string;
  value: string;
  verdict: string;
  explanation: string;
}

interface TradeRec {
  neutral: boolean;
  strike?: number;
  type?: string;
  ltp?: number;
  sl?: number;
  target?: number;
  rr?: number;
  strong?: boolean;
  score: number;
  expiry: string;
  atm?: number;
}

interface SignalData {
  ticker: string;
  spot: number;
  atm: number;
  expiry: string;
  pcr: number;
  max_pain: number;
  total_ce_oi: number;
  total_pe_oi: number;
  signal: string;
  score: number;
  details: SignalDetail[];
  trade: TradeRec;
  calls: { strike: number; open_interest: number }[];
  puts: { strike: number; open_interest: number }[];
}

function signalColor(signal: string) {
  if (signal.includes("STRONG BUY CALL")) return "border-green-500 bg-green-950/40 text-green-300";
  if (signal.includes("BUY CALL")) return "border-green-600 bg-green-950/20 text-green-400";
  if (signal.includes("STRONG BUY PUT")) return "border-red-500 bg-red-950/40 text-red-300";
  if (signal.includes("BUY PUT")) return "border-red-600 bg-red-950/20 text-red-400";
  return "border-yellow-600 bg-yellow-950/20 text-yellow-400";
}

function verdictBadge(verdict: string) {
  if (verdict.includes("Bullish")) return "bg-green-900 text-green-300";
  if (verdict.includes("Bearish")) return "bg-red-900 text-red-300";
  return "bg-slate-700 text-slate-300";
}

function MetricCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-surface-card border border-surface-border rounded-xl px-5 py-4">
      <p className="text-slate-500 text-xs uppercase tracking-wider mb-1">{label}</p>
      <p className="text-white text-xl font-semibold">{value}</p>
    </div>
  );
}

export default function OiSignalPage() {
  const [ticker, setTicker] = useState("SPY");
  const [expiry, setExpiry] = useState("");
  const [inputTicker, setInputTicker] = useState("SPY");
  const [inputExpiry, setInputExpiry] = useState("");

  // Fetch available expirations for the ticker
  const { data: expirations } = useQuery<string[]>({
    queryKey: ["expirations", ticker],
    queryFn: () => api.get(`/api/options/${ticker}/expirations`).then(r => r.data),
    enabled: !!ticker,
    staleTime: 5 * 60_000,
  });

  const { data, isLoading, error, refetch } = useQuery<SignalData>({
    queryKey: ["oi-signal", ticker, expiry],
    queryFn: () => api.get(`/api/options/${ticker}/oi-signal`, { params: { expiry, strikes_atm: 15 } }).then(r => r.data),
    enabled: !!ticker && !!expiry,
    refetchInterval: 60_000,
  });

  function handleAnalyze() {
    setTicker(inputTicker.toUpperCase().trim());
    setExpiry(inputExpiry);
  }

  // Build OI chart data
  const chartData = (() => {
    if (!data) return [];
    const strikes = new Map<number, { CE: number; PE: number }>();
    data.calls.forEach(r => {
      const s = strikes.get(r.strike) ?? { CE: 0, PE: 0 };
      s.CE = r.open_interest;
      strikes.set(r.strike, s);
    });
    data.puts.forEach(r => {
      const s = strikes.get(r.strike) ?? { CE: 0, PE: 0 };
      s.PE = r.open_interest;
      strikes.set(r.strike, s);
    });
    return Array.from(strikes.entries())
      .sort(([a], [b]) => a - b)
      .map(([strike, v]) => ({ strike, ...v }));
  })();

  return (
    <main className="p-6 space-y-6 max-w-7xl">
      <h1 className="text-2xl font-bold text-white">OI Signal Analysis</h1>

      {/* Controls */}
      <div className="flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs text-slate-400 mb-1">Ticker</label>
          <input
            className="bg-surface-card border border-surface-border text-white rounded-lg px-3 py-2 w-28 text-sm focus:outline-none focus:border-brand-500"
            value={inputTicker}
            onChange={e => setInputTicker(e.target.value)}
            onBlur={() => setTicker(inputTicker.toUpperCase().trim())}
            placeholder="SPY"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Expiry</label>
          {expirations && expirations.length > 0 ? (
            <select
              className="bg-surface-card border border-surface-border text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-brand-500"
              value={inputExpiry}
              onChange={e => setInputExpiry(e.target.value)}
            >
              <option value="">Select expiry…</option>
              {expirations.map(e => (
                <option key={e} value={e}>{e}</option>
              ))}
            </select>
          ) : (
            <input
              className="bg-surface-card border border-surface-border text-white rounded-lg px-3 py-2 w-36 text-sm focus:outline-none focus:border-brand-500"
              value={inputExpiry}
              onChange={e => setInputExpiry(e.target.value)}
              placeholder="YYYY-MM-DD"
            />
          )}
        </div>
        <button
          onClick={handleAnalyze}
          disabled={!inputExpiry}
          className="px-5 py-2 bg-brand-600 hover:bg-brand-500 disabled:bg-slate-700 text-white rounded-lg text-sm font-medium transition-colors"
        >
          Analyze
        </button>
        {data && (
          <button onClick={() => refetch()} className="px-4 py-2 border border-surface-border text-slate-400 rounded-lg text-sm hover:text-white transition-colors">
            Refresh
          </button>
        )}
      </div>

      {isLoading && (
        <div className="flex items-center gap-3 text-slate-400">
          <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          <span>Fetching OI data…</span>
        </div>
      )}
      {error && (
        <p className="text-red-400 bg-red-950/20 border border-red-800 rounded-lg px-4 py-3 text-sm">
          {(error as Error).message}
        </p>
      )}

      {data && (
        <>
          {/* Metrics row */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <MetricCard label="Spot" value={`$${data.spot.toFixed(2)}`} />
            <MetricCard label="ATM" value={`$${data.atm.toFixed(2)}`} />
            <MetricCard label="PCR" value={data.pcr.toFixed(2)} />
            <MetricCard label="Max Pain" value={`$${data.max_pain.toFixed(2)}`} />
            <MetricCard label="Total CE OI" value={(data.total_ce_oi / 1000).toFixed(1) + "K"} />
            <MetricCard label="Total PE OI" value={(data.total_pe_oi / 1000).toFixed(1) + "K"} />
          </div>

          {/* Signal box */}
          <div className={`border-2 rounded-2xl px-6 py-5 ${signalColor(data.signal)}`}>
            <p className="text-3xl font-bold">{data.signal}</p>
            <p className="mt-1 text-sm opacity-75">
              Score: {data.score > 0 ? "+" : ""}{data.score} &nbsp;|&nbsp; {data.ticker} {data.expiry}
            </p>
            {/* Score bar */}
            <div className="mt-3 h-2 bg-black/30 rounded-full overflow-hidden w-64">
              <div
                className={`h-full rounded-full transition-all ${data.score >= 0 ? "bg-green-400" : "bg-red-400"}`}
                style={{ width: `${Math.min(Math.abs(data.score) / 6 * 100, 100)}%`, marginLeft: data.score < 0 ? "auto" : "0" }}
              />
            </div>
            <p className="text-xs mt-1 opacity-50">−6 ←→ +6 scale</p>
          </div>

          {/* Indicator details */}
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
                    <td className="px-5 py-3 text-slate-300 font-mono">{d.value}</td>
                    <td className="px-5 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${verdictBadge(d.verdict)}`}>{d.verdict}</span>
                    </td>
                    <td className="px-5 py-3 text-slate-400 text-xs">{d.explanation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Trade recommendation */}
          {!data.trade.neutral ? (
            <div className="bg-surface-card border border-surface-border rounded-xl p-5">
              <h2 className="text-sm font-semibold text-white mb-4">Recommended Trade</h2>
              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-4">
                {[
                  { label: "Type", value: data.trade.type },
                  { label: "Strike", value: `$${data.trade.strike?.toFixed(2)}` },
                  { label: "Entry (LTP)", value: `$${data.trade.ltp?.toFixed(2)}` },
                  { label: "Stop Loss", value: `$${data.trade.sl?.toFixed(2)}` },
                  { label: "Target", value: `$${data.trade.target?.toFixed(2)}` },
                  { label: "Risk : Reward", value: `1 : ${data.trade.rr}` },
                ].map(({ label, value }) => (
                  <div key={label}>
                    <p className="text-xs text-slate-500 mb-0.5">{label}</p>
                    <p className={`font-semibold ${label === "Type" ? (data.trade.type === "CALL" ? "text-green-400" : "text-red-400") : "text-white"}`}>{value}</p>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-xs text-slate-500">
                SL = 65% of entry | Target = 165% of entry | Expiry: {data.trade.expiry}
              </p>
            </div>
          ) : (
            <div className="bg-yellow-950/20 border border-yellow-800 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-yellow-400 mb-1">Neutral — Wait for Clarity</h2>
              <p className="text-xs text-slate-400">
                ATM: ${data.trade.atm?.toFixed(2)} &nbsp;|&nbsp;
                Call LTP: ${data.trade.call_ltp?.toFixed(2)} &nbsp;|&nbsp;
                Put LTP: ${data.trade.put_ltp?.toFixed(2)}
              </p>
            </div>
          )}

          {/* OI Bar Chart */}
          <div className="bg-surface-card border border-surface-border rounded-xl p-5">
            <h2 className="text-sm font-semibold text-white mb-4">
              OI by Strike — {data.ticker} {data.expiry}
            </h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData} margin={{ top: 4, right: 10, left: 10, bottom: 4 }}>
                <XAxis
                  dataKey="strike"
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                  tickFormatter={v => `$${v}`}
                />
                <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} tickFormatter={v => `${(v / 1000).toFixed(0)}K`} />
                <Tooltip
                  contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
                  formatter={(v: number, name: string) => [`${v.toLocaleString()}`, name]}
                  labelFormatter={v => `Strike $${v}`}
                />
                <Legend />
                <ReferenceLine x={data.atm} stroke="#f59e0b" strokeDasharray="4 2" label={{ value: "ATM", fill: "#f59e0b", fontSize: 11 }} />
                <Bar dataKey="CE" name="Call OI" fill="#3b82f6" radius={[2, 2, 0, 0]} />
                <Bar dataKey="PE" name="Put OI" fill="#ef4444" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {!data && !isLoading && (
        <div className="text-center py-20 text-slate-500">
          <p className="text-lg">Select a ticker and expiry, then click Analyze.</p>
        </div>
      )}
    </main>
  );
}
