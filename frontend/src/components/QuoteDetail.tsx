"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { fmt, fmtK, fmtPct } from "@/lib/format";
import { TrendBadge } from "./ui/TrendBadge";
import { Loader } from "./ui/Loader";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

const PERIODS = ["1min", "5min", "15min", "30min", "60min", "day", "week"] as const;
const COUNTS: Record<string, number> = {
  "1min": 120, "5min": 100, "15min": 80, "30min": 60, "60min": 60, day: 90, week: 52,
};

export function QuoteDetail({ ticker }: { ticker: string }) {
  const [period, setPeriod] = useState<string>("day");

  const quoteQ = useQuery({
    queryKey: ["quote", ticker],
    queryFn: () => api.get(`/api/quotes/${ticker}`).then((r) => r.data),
    refetchInterval: 10_000,
  });

  const klineQ = useQuery({
    queryKey: ["kline", ticker, period],
    queryFn: () =>
      api.get(`/api/quotes/${ticker}/kline?period=${period}&count=${COUNTS[period]}`).then((r) => r.data),
    refetchInterval: 15_000,
  });

  const q = quoteQ.data;
  const isUp = (q?.change ?? 0) >= 0;
  const kData = klineQ.data ?? [];
  const chartColor = isUp ? "#22c55e" : "#ef4444";

  return (
    <div className="space-y-4">
      {quoteQ.isLoading && <Loader />}

      {q && (
        <div className="bg-surface-card border border-surface-border rounded-xl p-5">
          <div className="flex flex-wrap items-start gap-6">
            <div>
              <p className="text-slate-400 text-sm">{q.name}</p>
              <p className={`text-4xl font-bold num-font ${isUp ? "text-up" : "text-down"}`}>${fmt(q.last_price)}</p>
              <TrendBadge value={q.change} prefix="$" /> &nbsp;
              <TrendBadge value={q.change_pct} suffix="%" />
            </div>

            <div className="ml-auto grid grid-cols-3 md:grid-cols-5 gap-x-6 gap-y-2 text-sm text-slate-400">
              {[
                ["Open",     `$${fmt(q.open)}`],
                ["High",     `$${fmt(q.high)}`],
                ["Low",      `$${fmt(q.low)}`],
                ["Prev Close",`$${fmt(q.prev_close)}`],
                ["Volume",   fmtK(q.volume)],
                ["Mkt Cap",  fmtK(q.market_cap)],
                ["P/E",      q.pe_ratio ? fmt(q.pe_ratio) : "—"],
                ["52W High", `$${fmt(q.week52_high)}`],
                ["52W Low",  `$${fmt(q.week52_low)}`],
              ].map(([label, val]) => (
                <div key={label}>
                  <p className="text-xs text-slate-600">{label}</p>
                  <p className="num-font text-slate-200">{val}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Chart */}
      <div className="bg-surface-card border border-surface-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <p className="text-sm font-medium text-slate-300">Price Chart</p>
          <div className="flex gap-1">
            {PERIODS.map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                  period === p ? "bg-brand-600 text-white" : "text-slate-500 hover:text-slate-300"
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>
        {klineQ.isLoading ? (
          <Loader />
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={kData}>
              <defs>
                <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={chartColor} stopOpacity={0.25} />
                  <stop offset="95%" stopColor={chartColor} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#1e2a3b" strokeDasharray="3 3" />
              <XAxis
                dataKey="time"
                tickFormatter={(t) => t.slice(5)}
                tick={{ fill: "#64748b", fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                domain={["auto", "auto"]}
                tick={{ fill: "#64748b", fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => `$${v}`}
                width={60}
              />
              <Tooltip
                contentStyle={{ background: "#161b27", border: "1px solid #1e2a3b", borderRadius: 8, fontSize: 12 }}
                formatter={(v: number) => [`$${fmt(v)}`, "Close"]}
                labelStyle={{ color: "#94a3b8" }}
              />
              <Area
                type="monotone"
                dataKey="close"
                stroke={chartColor}
                strokeWidth={2}
                fill="url(#chartGrad)"
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
