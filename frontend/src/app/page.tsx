"use client";
import { useState } from "react";
import { QuoteCard } from "@/components/QuoteCard";
import { MiniChart } from "@/components/MiniChart";
import { AccountSummary } from "@/components/AccountSummary";
import { SearchBar } from "@/components/SearchBar";
import { TrendingUp, Activity, DollarSign, Zap } from "lucide-react";

const WATCHLIST = ["AAPL", "TSLA", "NVDA", "SPY", "QQQ", "AMZN", "META", "MSFT"];

export default function Dashboard() {
  const [search, setSearch] = useState("");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-slate-400 text-sm mt-1">US Options &amp; Stock Analyzer — MooMoo Trading</p>
        </div>
        <SearchBar placeholder="Quick lookup symbol…" onSearch={setSearch} />
      </div>

      {/* Account Summary */}
      <AccountSummary />

      {/* Quick Links */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { icon: Activity, label: "Options Chain", href: "/options", color: "text-brand-400" },
          { icon: TrendingUp, label: "Stock Quotes",  href: "/quotes",  color: "text-up" },
          { icon: DollarSign, label: "My Positions",  href: "/positions", color: "text-yellow-400" },
          { icon: Zap,        label: "Place Order",   href: "/trade",  color: "text-purple-400" },
        ].map(({ icon: Icon, label, href, color }) => (
          <a
            key={href}
            href={href}
            className="flex flex-col items-center gap-2 p-4 rounded-xl bg-surface-card border border-surface-border hover:border-brand-600 transition-colors"
          >
            <Icon className={`w-7 h-7 ${color}`} />
            <span className="text-sm font-medium text-slate-300">{label}</span>
          </a>
        ))}
      </div>

      {/* Watchlist */}
      <div>
        <h2 className="text-lg font-semibold text-slate-200 mb-3">Watchlist</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          {WATCHLIST.map((t) => (
            <QuoteCard key={t} ticker={t} />
          ))}
        </div>
      </div>
    </div>
  );
}
