"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Activity, TrendingUp, Briefcase, List, ShoppingCart,
  BarChart2, Search, Calendar, ScanLine, Zap,
} from "lucide-react";

const NAV_GROUPS = [
  {
    label: "Trading",
    items: [
      { href: "/",          icon: LayoutDashboard, label: "Dashboard" },
      { href: "/options",   icon: Activity,        label: "Options Chain" },
      { href: "/quotes",    icon: TrendingUp,      label: "Quotes" },
      { href: "/positions", icon: Briefcase,       label: "Positions" },
      { href: "/orders",    icon: List,            label: "Orders" },
      { href: "/trade",     icon: ShoppingCart,    label: "Trade" },
    ],
  },
  {
    label: "Analytics",
    items: [
      { href: "/oi-signal",    icon: BarChart2, label: "OI Signal" },
      { href: "/expiry",       icon: Calendar,  label: "Expiry Analyzer" },
      { href: "/smart-signal", icon: Zap,       label: "Smart Signal" },
      { href: "/scanner",      icon: ScanLine,  label: "OI Scanner" },
    ],
  },
  {
    label: "Screeners",
    items: [
      { href: "/screeners", icon: Search, label: "Screeners" },
    ],
  },
];

export function Sidebar() {
  const path = usePathname();

  return (
    <aside className="w-56 flex-shrink-0 bg-surface-card border-r border-surface-border flex flex-col">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-surface-border">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center text-white font-bold text-sm">S</div>
          <div>
            <p className="text-white font-semibold text-sm leading-none">Subba US</p>
            <p className="text-slate-500 text-xs mt-0.5">Options Analyzer</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-4 overflow-y-auto">
        {NAV_GROUPS.map(group => (
          <div key={group.label}>
            <p className="px-3 mb-1 text-[10px] uppercase tracking-wider text-slate-600 font-semibold">{group.label}</p>
            <div className="space-y-0.5">
              {group.items.map(({ href, icon: Icon, label }) => {
                const active = path === href || (href !== "/" && path.startsWith(href));
                return (
                  <Link
                    key={href}
                    href={href}
                    className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                      active
                        ? "bg-brand-900/50 text-brand-400 font-medium"
                        : "text-slate-400 hover:text-slate-200 hover:bg-surface-hover"
                    }`}
                  >
                    <Icon className={`w-4 h-4 flex-shrink-0 ${active ? "text-brand-400" : ""}`} />
                    {label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-surface-border">
        <p className="text-xs text-slate-600">MooMoo API Connected</p>
        <p className="text-xs text-slate-700">US Market</p>
      </div>
    </aside>
  );
}
