"use client";
import { useState, useMemo } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { fmt } from "@/lib/format";
import { Loader } from "./ui/Loader";
import { ShoppingCart } from "lucide-react";
import { OrderModal } from "./OrderModal";

interface Option {
  code: string;
  strike: number;
  expiry: string;
  last: number;
  bid: number;
  ask: number;
  mid: number;
  volume: number;
  open_interest: number;
  iv: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
}

interface OrderTarget {
  code: string;
  ticker: string;
  strike: number;
  expiry: string;
  side: "BUY" | "SELL";
  price: number;
  optionType: "CALL" | "PUT";
}

function GreekCell({ v, color }: { v: number; color?: string }) {
  return (
    <td className={`px-3 py-2 num-font text-xs text-right ${color ?? "text-slate-400"}`}>
      {v ? v.toFixed(4) : "—"}
    </td>
  );
}

function OptionRow({
  opt,
  spot,
  type,
  onOrder,
}: {
  opt: Option;
  spot: number;
  type: "CALL" | "PUT";
  onOrder: (t: OrderTarget) => void;
}) {
  const itm =
    type === "CALL" ? opt.strike < spot : opt.strike > spot;
  const atm = Math.abs(opt.strike - spot) / spot < 0.005;
  const rowCls = atm
    ? "row-atm"
    : itm
    ? type === "CALL"
      ? "row-itm-call"
      : "row-itm-put"
    : "";

  return (
    <tr className={`${rowCls} border-b border-surface-border hover:bg-surface-hover transition-colors text-sm`}>
      <td className="px-3 py-2 num-font text-right text-slate-300">{fmt(opt.bid)}</td>
      <td className="px-3 py-2 num-font text-right text-slate-300">{fmt(opt.ask)}</td>
      <td className="px-3 py-2 num-font text-right text-white font-medium">{fmt(opt.last)}</td>
      <td className="px-3 py-2 num-font text-right text-slate-400 text-xs">{opt.volume.toLocaleString()}</td>
      <td className="px-3 py-2 num-font text-right text-slate-400 text-xs">{opt.open_interest.toLocaleString()}</td>
      <td className="px-3 py-2 num-font text-right text-purple-300 text-xs">{opt.iv ? `${(opt.iv * 100).toFixed(1)}%` : "—"}</td>
      <GreekCell v={opt.delta} color={type === "CALL" ? "text-up" : "text-down"} />
      <GreekCell v={opt.theta} color="text-red-400" />
      <GreekCell v={opt.gamma} />
      <GreekCell v={opt.vega} />
      {/* Strike (centre) */}
      <td className={`px-4 py-2 num-font text-center font-bold text-sm ${atm ? "text-brand-400" : "text-slate-200"}`}>
        {fmt(opt.strike, 0)}
      </td>
      {/* PUT side (mirror) */}
      <GreekCell v={opt.vega} />
      <GreekCell v={opt.gamma} />
      <GreekCell v={opt.theta} color="text-red-400" />
      <GreekCell v={opt.delta} color={type === "PUT" ? "text-down" : "text-up"} />
      <td className="px-3 py-2 num-font text-left text-purple-300 text-xs">{opt.iv ? `${(opt.iv * 100).toFixed(1)}%` : "—"}</td>
      <td className="px-3 py-2 num-font text-left text-slate-400 text-xs">{opt.open_interest.toLocaleString()}</td>
      <td className="px-3 py-2 num-font text-left text-slate-400 text-xs">{opt.volume.toLocaleString()}</td>
      <td className="px-3 py-2 num-font text-left text-white font-medium">{fmt(opt.last)}</td>
      <td className="px-3 py-2 num-font text-left text-slate-300">{fmt(opt.bid)}</td>
      <td className="px-3 py-2 num-font text-left text-slate-300">{fmt(opt.ask)}</td>

      {/* Buy/Sell buttons */}
      <td className="px-2 py-2">
        <div className="flex gap-1">
          <button
            onClick={() => onOrder({ code: opt.code, ticker: "", strike: opt.strike, expiry: opt.expiry, side: "BUY", price: opt.ask, optionType: type })}
            className="px-2 py-0.5 text-xs rounded bg-green-900/60 text-up hover:bg-green-800/60 transition-colors"
          >
            B
          </button>
          <button
            onClick={() => onOrder({ code: opt.code, ticker: "", strike: opt.strike, expiry: opt.expiry, side: "SELL", price: opt.bid, optionType: type })}
            className="px-2 py-0.5 text-xs rounded bg-red-900/60 text-down hover:bg-red-800/60 transition-colors"
          >
            S
          </button>
        </div>
      </td>
    </tr>
  );
}

export function OptionsChain({ ticker }: { ticker: string }) {
  const [expiry, setExpiry] = useState<string>("");
  const [order, setOrder] = useState<OrderTarget | null>(null);
  const [strikeFocus, setStrikeFocus] = useState<"all" | "near">("near");

  const expiryQ = useQuery({
    queryKey: ["expirations", ticker],
    queryFn: () => api.get(`/api/options/${ticker}/expirations`).then((r) => r.data),
    enabled: !!ticker,
    onSuccess: (d: any) => { if (!expiry && d.expirations?.length) setExpiry(d.expirations[0]); },
  } as any);

  const spotQ = useQuery({
    queryKey: ["quote", ticker],
    queryFn: () => api.get(`/api/quotes/${ticker}`).then((r) => r.data),
    refetchInterval: 10_000,
  });

  const chainQ = useQuery({
    queryKey: ["chain", ticker, expiry],
    queryFn: () => api.get(`/api/options/${ticker}/chain?expiry=${expiry}`).then((r) => r.data),
    enabled: !!expiry && !!ticker,
    refetchInterval: 15_000,
  });

  const spot = spotQ.data?.last_price ?? 0;

  const { calls, puts } = useMemo(() => {
    const c: Option[] = chainQ.data?.calls ?? [];
    const p: Option[] = chainQ.data?.puts ?? [];
    if (strikeFocus === "near" && spot) {
      const lo = spot * 0.85;
      const hi = spot * 1.15;
      return { calls: c.filter((o) => o.strike >= lo && o.strike <= hi), puts: p.filter((o) => o.strike >= lo && o.strike <= hi) };
    }
    return { calls: c, puts: p };
  }, [chainQ.data, strikeFocus, spot]);

  const allStrikes = useMemo(() => {
    const set = new Set([...calls.map((c) => c.strike), ...puts.map((p) => p.strike)]);
    return Array.from(set).sort((a, b) => a - b);
  }, [calls, puts]);

  const callByStrike = useMemo(() => Object.fromEntries(calls.map((c) => [c.strike, c])), [calls]);
  const putByStrike  = useMemo(() => Object.fromEntries(puts.map((p) => [p.strike, p])), [puts]);

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3 bg-surface-card border border-surface-border rounded-xl p-4">
        <div>
          <label className="text-xs text-slate-500 block mb-1">Expiration</label>
          <select
            value={expiry}
            onChange={(e) => setExpiry(e.target.value)}
            className="bg-surface border border-surface-border rounded-lg px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-brand-500"
          >
            {expiryQ.data?.expirations?.map((e: string) => (
              <option key={e} value={e}>{e}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-xs text-slate-500 block mb-1">Strike Range</label>
          <div className="flex rounded-lg overflow-hidden border border-surface-border">
            {(["near", "all"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setStrikeFocus(s)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${strikeFocus === s ? "bg-brand-700 text-white" : "text-slate-400 hover:text-white"}`}
              >
                {s === "near" ? "±15% ATM" : "All strikes"}
              </button>
            ))}
          </div>
        </div>

        {spot > 0 && (
          <div className="ml-auto text-right">
            <p className="text-xs text-slate-500">Spot</p>
            <p className="num-font font-bold text-white text-lg">${fmt(spot)}</p>
          </div>
        )}
      </div>

      {(chainQ.isLoading || expiryQ.isLoading) && <Loader />}

      {chainQ.data && (
        <div className="overflow-x-auto rounded-xl border border-surface-border">
          <table className="w-full text-xs min-w-[900px]">
            <thead>
              <tr className="bg-surface-card border-b border-surface-border text-slate-500">
                {/* CALLS */}
                <th colSpan={10} className="px-4 py-2 text-center text-up font-semibold border-r border-surface-border">CALLS</th>
                {/* STRIKE */}
                <th className="px-4 py-2 text-center text-slate-300 font-bold border-r border-surface-border">STRIKE</th>
                {/* PUTS */}
                <th colSpan={10} className="px-4 py-2 text-center text-down font-semibold">PUTS</th>
                <th className="px-2 py-2" />
              </tr>
              <tr className="bg-surface text-slate-500 border-b border-surface-border">
                {/* call headers (right-aligned) */}
                {["Bid", "Ask", "Last", "Vol", "OI", "IV", "Δ Delta", "Θ Theta", "Γ Gamma", "ν Vega"].map((h) => (
                  <th key={`ch-${h}`} className="px-3 py-2 text-right font-medium">{h}</th>
                ))}
                <th className="px-4 py-2 text-center font-bold text-slate-300 border-x border-surface-border">Strike</th>
                {/* put headers (left-aligned, mirror) */}
                {["ν Vega", "Γ Gamma", "Θ Theta", "Δ Delta", "IV", "OI", "Vol", "Last", "Bid", "Ask"].map((h) => (
                  <th key={`ph-${h}`} className="px-3 py-2 text-left font-medium">{h}</th>
                ))}
                <th className="px-2 py-2 text-center">Order</th>
              </tr>
            </thead>
            <tbody>
              {allStrikes.map((strike) => {
                const call = callByStrike[strike];
                const put  = putByStrike[strike];
                const atm  = spot && Math.abs(strike - spot) / spot < 0.005;
                const rowCls = atm ? "row-atm" : "";

                return (
                  <tr key={strike} className={`${rowCls} border-b border-surface-border hover:bg-surface-hover transition-colors`}>
                    {/* CALL side */}
                    <td className="px-3 py-2 num-font text-right text-slate-300">{call ? fmt(call.bid) : "—"}</td>
                    <td className="px-3 py-2 num-font text-right text-slate-300">{call ? fmt(call.ask) : "—"}</td>
                    <td className="px-3 py-2 num-font text-right text-white font-medium">{call ? fmt(call.last) : "—"}</td>
                    <td className="px-3 py-2 num-font text-right text-slate-400">{call ? call.volume.toLocaleString() : "—"}</td>
                    <td className="px-3 py-2 num-font text-right text-slate-400">{call ? call.open_interest.toLocaleString() : "—"}</td>
                    <td className="px-3 py-2 num-font text-right text-purple-300">{call?.iv ? `${(call.iv * 100).toFixed(1)}%` : "—"}</td>
                    <td className="px-3 py-2 num-font text-right text-up">{call?.delta ? call.delta.toFixed(3) : "—"}</td>
                    <td className="px-3 py-2 num-font text-right text-red-400">{call?.theta ? call.theta.toFixed(4) : "—"}</td>
                    <td className="px-3 py-2 num-font text-right text-slate-400">{call?.gamma ? call.gamma.toFixed(4) : "—"}</td>
                    <td className="px-3 py-2 num-font text-right text-slate-400">{call?.vega ? call.vega.toFixed(4) : "—"}</td>

                    {/* STRIKE */}
                    <td className={`px-4 py-2 num-font text-center font-bold border-x border-surface-border ${atm ? "text-brand-400 bg-brand-900/20" : "text-slate-200"}`}>
                      {fmt(strike, 0)}
                      {atm && <span className="ml-1 text-[10px] text-brand-500">ATM</span>}
                    </td>

                    {/* PUT side */}
                    <td className="px-3 py-2 num-font text-left text-slate-400">{put?.vega ? put.vega.toFixed(4) : "—"}</td>
                    <td className="px-3 py-2 num-font text-left text-slate-400">{put?.gamma ? put.gamma.toFixed(4) : "—"}</td>
                    <td className="px-3 py-2 num-font text-left text-red-400">{put?.theta ? put.theta.toFixed(4) : "—"}</td>
                    <td className="px-3 py-2 num-font text-left text-down">{put?.delta ? put.delta.toFixed(3) : "—"}</td>
                    <td className="px-3 py-2 num-font text-left text-purple-300">{put?.iv ? `${(put.iv * 100).toFixed(1)}%` : "—"}</td>
                    <td className="px-3 py-2 num-font text-left text-slate-400">{put ? put.open_interest.toLocaleString() : "—"}</td>
                    <td className="px-3 py-2 num-font text-left text-slate-400">{put ? put.volume.toLocaleString() : "—"}</td>
                    <td className="px-3 py-2 num-font text-left text-white font-medium">{put ? fmt(put.last) : "—"}</td>
                    <td className="px-3 py-2 num-font text-left text-slate-300">{put ? fmt(put.bid) : "—"}</td>
                    <td className="px-3 py-2 num-font text-left text-slate-300">{put ? fmt(put.ask) : "—"}</td>

                    {/* Order buttons */}
                    <td className="px-2 py-2">
                      <div className="flex flex-col gap-1">
                        {call && (
                          <button
                            onClick={() => setOrder({ code: call.code, ticker, strike, expiry: call.expiry, side: "BUY", price: call.ask, optionType: "CALL" })}
                            className="px-1.5 py-0.5 text-[10px] rounded bg-green-900/60 text-up hover:bg-green-800 transition-colors whitespace-nowrap"
                          >
                            Buy C
                          </button>
                        )}
                        {put && (
                          <button
                            onClick={() => setOrder({ code: put.code, ticker, strike, expiry: put.expiry, side: "BUY", price: put.ask, optionType: "PUT" })}
                            className="px-1.5 py-0.5 text-[10px] rounded bg-red-900/60 text-down hover:bg-red-800 transition-colors whitespace-nowrap"
                          >
                            Buy P
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {allStrikes.length === 0 && (
            <p className="text-slate-500 text-center py-8">No options data — select an expiration date</p>
          )}
        </div>
      )}

      {order && <OrderModal order={order} onClose={() => setOrder(null)} />}
    </div>
  );
}
