"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { fmt, fmtPct, fmtK } from "@/lib/format";
import Link from "next/link";

interface Props { ticker: string; large?: boolean }

export function QuoteCard({ ticker, large }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ["quote", ticker],
    queryFn: () => api.get(`/api/quotes/${ticker}`).then((r) => r.data),
    refetchInterval: 10_000,
    retry: false,
  });

  const isUp = (data?.change ?? 0) >= 0;

  if (isLoading)
    return (
      <div className="bg-surface-card border border-surface-border rounded-xl p-4 animate-pulse h-28" />
    );

  if (!data)
    return (
      <div className="bg-surface-card border border-surface-border rounded-xl p-4">
        <p className="text-slate-500 text-sm">No data for {ticker}</p>
      </div>
    );

  return (
    <Link href={`/quotes?sym=${ticker}`}>
      <div className={`bg-surface-card border border-surface-border rounded-xl p-4 hover:border-brand-600 transition-colors cursor-pointer ${large ? "h-full" : ""}`}>
        <div className="flex items-start justify-between">
          <div>
            <p className="font-bold text-white text-base">{ticker}</p>
            <p className="text-slate-500 text-xs truncate max-w-[120px]">{data.name}</p>
          </div>
          <span className={`text-xs px-2 py-0.5 rounded font-medium ${isUp ? "bg-green-900/40 text-up" : "bg-red-900/40 text-down"}`}>
            {isUp ? "▲" : "▼"} {fmtPct(data.change_pct)}
          </span>
        </div>

        <p className={`text-2xl font-bold num-font mt-2 ${isUp ? "text-up" : "text-down"}`}>
          ${fmt(data.last_price)}
        </p>
        <p className={`text-xs num-font ${isUp ? "text-up" : "text-down"}`}>
          {isUp ? "+" : ""}{fmt(data.change)} today
        </p>

        {large && (
          <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-slate-400">
            <div><span className="text-slate-600">Open</span><br/><span className="num-font text-slate-300">${fmt(data.open)}</span></div>
            <div><span className="text-slate-600">Prev</span><br/><span className="num-font text-slate-300">${fmt(data.prev_close)}</span></div>
            <div><span className="text-slate-600">High</span><br/><span className="num-font text-up">${fmt(data.high)}</span></div>
            <div><span className="text-slate-600">Low</span><br/><span className="num-font text-down">${fmt(data.low)}</span></div>
            <div><span className="text-slate-600">Volume</span><br/><span className="num-font text-slate-300">{fmtK(data.volume)}</span></div>
            <div><span className="text-slate-600">Mkt Cap</span><br/><span className="num-font text-slate-300">{fmtK(data.market_cap)}</span></div>
            <div><span className="text-slate-600">52W High</span><br/><span className="num-font text-slate-300">${fmt(data.week52_high)}</span></div>
            <div><span className="text-slate-600">52W Low</span><br/><span className="num-font text-slate-300">${fmt(data.week52_low)}</span></div>
          </div>
        )}
      </div>
    </Link>
  );
}
