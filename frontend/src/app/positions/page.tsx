"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { TrendBadge } from "@/components/ui/TrendBadge";
import { Loader } from "@/components/ui/Loader";
import { fmt, fmtPct } from "@/lib/format";

export default function PositionsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["positions"],
    queryFn: () => api.get("/api/account/positions").then((r) => r.data),
    refetchInterval: 15_000,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">My Positions</h1>
        <p className="text-slate-400 text-sm">Live portfolio — MooMoo {data?.env ?? ""}</p>
      </div>

      {isLoading && <Loader />}
      {error && <p className="text-red-400">Failed to load positions. Is the backend running?</p>}

      {data?.positions && (
        <div className="overflow-x-auto rounded-xl border border-surface-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-400 border-b border-surface-border">
                {["Symbol", "Name", "Qty", "Cost", "Price", "Mkt Val", "Unrealized P&L", "P&L %", "Realized"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.positions.map((p: any, i: number) => (
                <tr key={i} className="border-b border-surface-border hover:bg-surface-hover transition-colors">
                  <td className="px-4 py-3 font-semibold text-brand-400 num-font">{p.code.replace("US.", "")}</td>
                  <td className="px-4 py-3 text-slate-300">{p.name}</td>
                  <td className="px-4 py-3 num-font">{p.qty}</td>
                  <td className="px-4 py-3 num-font">{fmt(p.cost_price)}</td>
                  <td className="px-4 py-3 num-font">{fmt(p.nominal_price)}</td>
                  <td className="px-4 py-3 num-font">{fmt(p.market_val)}</td>
                  <td className="px-4 py-3 num-font">
                    <TrendBadge value={p.unrealized_pl} prefix="$" />
                  </td>
                  <td className="px-4 py-3 num-font">
                    <TrendBadge value={p.unrealized_pl_ratio} suffix="%" />
                  </td>
                  <td className="px-4 py-3 num-font">
                    <TrendBadge value={p.realized_pl} prefix="$" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.positions.length === 0 && (
            <p className="text-slate-500 text-center py-8">No open positions</p>
          )}
        </div>
      )}
    </div>
  );
}
