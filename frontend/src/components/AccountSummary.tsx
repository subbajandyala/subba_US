"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { fmt } from "@/lib/format";
import { TrendBadge } from "./ui/TrendBadge";
import { DollarSign, TrendingUp, Wallet, BarChart3 } from "lucide-react";

export function AccountSummary() {
  const { data } = useQuery({
    queryKey: ["funds"],
    queryFn: () => api.get("/api/account/funds").then((r) => r.data),
    refetchInterval: 15_000,
    retry: false,
  });

  const tiles = data
    ? [
        { icon: Wallet,      label: "Total Assets",    value: `$${fmt(data.total_assets)}`,          color: "text-brand-400" },
        { icon: DollarSign,  label: "Cash",            value: `$${fmt(data.cash)}`,                  color: "text-slate-300" },
        { icon: BarChart3,   label: "Market Value",    value: `$${fmt(data.market_val)}`,            color: "text-yellow-400" },
        { icon: TrendingUp,  label: "Unrealized P&L",  value: <TrendBadge value={data.unrealized_pl} prefix="$" />, color: "" },
      ]
    : [];

  if (!data) return null;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {tiles.map(({ icon: Icon, label, value, color }) => (
        <div key={label} className="bg-surface-card border border-surface-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Icon className={`w-4 h-4 ${color || "text-slate-400"}`} />
            <span className="text-xs text-slate-500">{label}</span>
          </div>
          <div className="text-lg font-bold num-font text-white">{value}</div>
          {label === "Total Assets" && (
            <p className="text-xs text-slate-600 mt-1">{data.env} account</p>
          )}
        </div>
      ))}
    </div>
  );
}
