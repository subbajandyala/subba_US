"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

type Tab = "ema" | "ma20" | "ma50" | "volume" | "fundamentals";

interface EMARow {
  ticker: string;
  close: number;
  ema_fast: number;
  ema_slow: number;
  cross: string;
  chg_pct: number;
  volume: number;
}

interface MARow {
  ticker: string;
  close: number;
  sma: number;
  dist_pct: number;
  chg_pct: number;
  vol_ratio: number;
}

interface VolRow {
  ticker: string;
  close: number;
  chg_pct: number;
  vol_ratio: number;
  today_vol: number;
  avg_vol_20d: number;
  direction: string;
}

interface FundRow {
  ticker: string;
  name: string;
  close: number;
  pe: number;
  mktcap_b: number;
  div_yield_pct: number;
  sector: string;
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-4 py-2 text-left text-xs text-slate-500 uppercase tracking-wide font-normal">{children}</th>;
}

function Td({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-4 py-3 text-sm text-slate-200 ${className}`}>{children}</td>;
}

function Chg({ v }: { v: number }) {
  return <span className={v >= 0 ? "text-green-400" : "text-red-400"}>{v >= 0 ? "+" : ""}{v.toFixed(2)}%</span>;
}

function EmptyState() {
  return <p className="text-center py-12 text-slate-500">No matches found for current filters.</p>;
}

function EMATab() {
  const [direction, setDirection] = useState<"bullish" | "bearish" | "both">("bullish");
  const { data, isLoading, error } = useQuery<{ results: EMARow[] }>({
    queryKey: ["screener-ema", direction],
    queryFn: () => api.get("/api/screener/ema-crossover", { params: { direction } }).then(r => r.data),
    staleTime: 5 * 60_000,
  });

  return (
    <div>
      <div className="flex gap-2 mb-4">
        {(["bullish", "bearish", "both"] as const).map(d => (
          <button key={d} onClick={() => setDirection(d)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors capitalize ${direction === d ? "bg-brand-600 text-white" : "bg-surface-hover text-slate-400 hover:text-white"}`}>
            {d}
          </button>
        ))}
      </div>
      {isLoading && <p className="text-slate-500 text-sm">Scanning {direction} EMA crossovers…</p>}
      {error && <p className="text-red-400 text-sm">{(error as Error).message}</p>}
      {data?.results.length === 0 && <EmptyState />}
      {data && data.results.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead><tr><Th>Ticker</Th><Th>Close</Th><Th>EMA20</Th><Th>EMA50</Th><Th>Cross</Th><Th>Chg%</Th><Th>Volume</Th></tr></thead>
            <tbody className="divide-y divide-surface-border">
              {data.results.map(r => (
                <tr key={r.ticker} className="hover:bg-surface-hover">
                  <Td><span className="font-semibold text-white">{r.ticker}</span></Td>
                  <Td>${r.close}</Td>
                  <Td>${r.ema_fast}</Td>
                  <Td>${r.ema_slow}</Td>
                  <Td><span className={r.cross === "BULLISH" ? "text-green-400" : "text-red-400"}>{r.cross}</span></Td>
                  <Td><Chg v={r.chg_pct} /></Td>
                  <Td>{r.volume.toLocaleString()}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function MARetracementTab({ ma }: { ma: 20 | 50 }) {
  const { data, isLoading, error } = useQuery<{ results: MARow[] }>({
    queryKey: ["screener-ma", ma],
    queryFn: () => api.get("/api/screener/ma-retracement", { params: { ma } }).then(r => r.data),
    staleTime: 5 * 60_000,
  });

  return (
    <div>
      {isLoading && <p className="text-slate-500 text-sm">Finding stocks near {ma}-day MA…</p>}
      {error && <p className="text-red-400 text-sm">{(error as Error).message}</p>}
      {data?.results.length === 0 && <EmptyState />}
      {data && data.results.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead><tr><Th>Ticker</Th><Th>Close</Th><Th>SMA{ma}</Th><Th>Dist%</Th><Th>Chg%</Th><Th>Vol Ratio</Th></tr></thead>
            <tbody className="divide-y divide-surface-border">
              {data.results.map(r => (
                <tr key={r.ticker} className="hover:bg-surface-hover">
                  <Td><span className="font-semibold text-white">{r.ticker}</span></Td>
                  <Td>${r.close}</Td>
                  <Td>${r.sma}</Td>
                  <Td><span className="text-yellow-400">{r.dist_pct.toFixed(2)}%</span></Td>
                  <Td><Chg v={r.chg_pct} /></Td>
                  <Td className={r.vol_ratio >= 1.5 ? "text-blue-400" : ""}>{r.vol_ratio}x</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function VolumeSurgeTab() {
  const { data, isLoading, error } = useQuery<{ results: VolRow[] }>({
    queryKey: ["screener-vol"],
    queryFn: () => api.get("/api/screener/volume-surge").then(r => r.data),
    staleTime: 2 * 60_000,
  });

  return (
    <div>
      {isLoading && <p className="text-slate-500 text-sm">Scanning for volume surges…</p>}
      {error && <p className="text-red-400 text-sm">{(error as Error).message}</p>}
      {data?.results.length === 0 && <EmptyState />}
      {data && data.results.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead><tr><Th>Ticker</Th><Th>Close</Th><Th>Chg%</Th><Th>Vol Ratio</Th><Th>Today Vol</Th><Th>Avg Vol</Th><Th>Dir</Th></tr></thead>
            <tbody className="divide-y divide-surface-border">
              {data.results.map(r => (
                <tr key={r.ticker} className="hover:bg-surface-hover">
                  <Td><span className="font-semibold text-white">{r.ticker}</span></Td>
                  <Td>${r.close}</Td>
                  <Td><Chg v={r.chg_pct} /></Td>
                  <Td><span className="text-blue-400 font-medium">{r.vol_ratio}x</span></Td>
                  <Td>{(r.today_vol / 1e6).toFixed(2)}M</Td>
                  <Td>{(r.avg_vol_20d / 1e6).toFixed(2)}M</Td>
                  <Td><span className={r.direction === "BULL" ? "text-green-400" : "text-red-400"}>{r.direction}</span></Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function FundamentalsTab() {
  const { data, isLoading, error } = useQuery<{ results: FundRow[] }>({
    queryKey: ["screener-fund"],
    queryFn: () => api.get("/api/screener/fundamentals").then(r => r.data),
    staleTime: 30 * 60_000,
  });

  return (
    <div>
      <p className="text-xs text-slate-500 mb-3">S&P universe · P/E ≤ 30 · Market cap ≥ $10B</p>
      {isLoading && <p className="text-slate-500 text-sm">Fetching fundamentals (may take 20-30s)…</p>}
      {error && <p className="text-red-400 text-sm">{(error as Error).message}</p>}
      {data?.results.length === 0 && <EmptyState />}
      {data && data.results.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead><tr><Th>Ticker</Th><Th>Name</Th><Th>Close</Th><Th>P/E</Th><Th>Mkt Cap</Th><Th>Div Yield</Th><Th>Sector</Th></tr></thead>
            <tbody className="divide-y divide-surface-border">
              {data.results.map(r => (
                <tr key={r.ticker} className="hover:bg-surface-hover">
                  <Td><span className="font-semibold text-white">{r.ticker}</span></Td>
                  <Td>{r.name}</Td>
                  <Td>${r.close}</Td>
                  <Td>{r.pe}</Td>
                  <Td>${r.mktcap_b}B</Td>
                  <Td>{r.div_yield_pct > 0 ? `${r.div_yield_pct}%` : "—"}</Td>
                  <Td className="text-slate-400">{r.sector}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const TABS: { id: Tab; label: string }[] = [
  { id: "ema", label: "EMA Crossover" },
  { id: "ma20", label: "20MA Bounce" },
  { id: "ma50", label: "50MA Support" },
  { id: "volume", label: "Volume Surge" },
  { id: "fundamentals", label: "Fundamentals" },
];

export default function ScreersPage() {
  const [tab, setTab] = useState<Tab>("ema");

  return (
    <main className="p-6 space-y-6 max-w-6xl">
      <h1 className="text-2xl font-bold text-white">Stock Screeners</h1>
      <p className="text-slate-400 text-sm">Universe: top 50 liquid US stocks + ETFs. Data via yfinance.</p>

      {/* Tab bar */}
      <div className="flex gap-1 bg-surface-card border border-surface-border rounded-xl p-1 w-fit">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${tab === t.id ? "bg-brand-600 text-white" : "text-slate-400 hover:text-white"}`}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="bg-surface-card border border-surface-border rounded-xl p-5">
        {tab === "ema" && <EMATab />}
        {tab === "ma20" && <MARetracementTab ma={20} />}
        {tab === "ma50" && <MARetracementTab ma={50} />}
        {tab === "volume" && <VolumeSurgeTab />}
        {tab === "fundamentals" && <FundamentalsTab />}
      </div>
    </main>
  );
}
