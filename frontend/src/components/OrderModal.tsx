"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { X, CheckCircle2, XCircle } from "lucide-react";
import { fmt } from "@/lib/format";

interface OrderTarget {
  code: string;
  ticker: string;
  strike: number;
  expiry: string;
  side: "BUY" | "SELL";
  price: number;
  optionType: "CALL" | "PUT";
}

export function OrderModal({ order, onClose }: { order: OrderTarget; onClose: () => void }) {
  const [qty, setQty] = useState("1");
  const [price, setPrice] = useState(order.price.toFixed(2));
  const [orderType, setOrderType] = useState<"NORMAL" | "MARKET">("NORMAL");
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);

  const mut = useMutation({
    mutationFn: (body: object) => api.post("/api/trading/order", body),
    onSuccess: (res) => setResult({ ok: true, msg: `Order placed! ID: ${res.data.order_id}` }),
    onError: (err: any) =>
      setResult({ ok: false, msg: err?.response?.data?.detail ?? "Order failed" }),
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setResult(null);
    mut.mutate({
      ticker: order.code,
      qty: parseInt(qty),
      price: parseFloat(price),
      side: order.side,
      order_type: orderType,
      remark: `${order.optionType} ${order.strike} ${order.expiry}`,
    });
  };

  const premium = parseFloat(price) * parseInt(qty || "1") * 100;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-surface-card border border-surface-border rounded-2xl p-6 w-[420px] shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div>
            <p className={`font-bold text-lg ${order.optionType === "CALL" ? "text-up" : "text-down"}`}>
              {order.side} {order.optionType}
            </p>
            <p className="text-slate-400 text-sm">
              {order.ticker} · Strike ${fmt(order.strike, 0)} · {order.expiry}
            </p>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={submit} className="space-y-4">
          {/* Order type */}
          <div className="flex rounded-lg overflow-hidden border border-surface-border">
            {(["NORMAL", "MARKET"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setOrderType(t)}
                className={`flex-1 py-2 text-sm font-medium transition-colors ${orderType === t ? "bg-brand-700 text-white" : "text-slate-400"}`}
              >
                {t === "NORMAL" ? "Limit" : "Market"}
              </button>
            ))}
          </div>

          {/* Price */}
          <div>
            <label className="text-xs text-slate-400 mb-1 block">Premium per contract (USD)</label>
            <input
              type="number"
              step="0.01"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              className="w-full bg-surface border border-surface-border rounded-lg px-3 py-2 num-font text-sm focus:outline-none focus:border-brand-500"
            />
          </div>

          {/* Qty */}
          <div>
            <label className="text-xs text-slate-400 mb-1 block">Contracts (1 contract = 100 shares)</label>
            <input
              type="number"
              min="1"
              step="1"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              className="w-full bg-surface border border-surface-border rounded-lg px-3 py-2 num-font text-sm focus:outline-none focus:border-brand-500"
            />
          </div>

          {/* Cost estimate */}
          <div className="bg-surface rounded-lg px-4 py-3 text-sm">
            <div className="flex justify-between text-slate-400">
              <span>Total premium</span>
              <span className="num-font text-white font-bold">${fmt(premium)}</span>
            </div>
            <div className="flex justify-between text-slate-600 text-xs mt-1">
              <span>{qty} contract × ${price} × 100</span>
              <span>Max profit unlimited (call)</span>
            </div>
          </div>

          <button
            type="submit"
            disabled={mut.isPending}
            className={`w-full py-3 rounded-xl font-bold text-white text-sm transition-colors ${
              order.side === "BUY"
                ? "bg-up hover:bg-green-600 disabled:bg-green-900"
                : "bg-down hover:bg-red-600 disabled:bg-red-900"
            }`}
          >
            {mut.isPending ? "Placing…" : `Confirm ${order.side} ${qty} ${order.optionType}`}
          </button>

          {result && (
            <div className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg ${result.ok ? "bg-green-900/30 text-up" : "bg-red-900/30 text-down"}`}>
              {result.ok ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
              {result.msg}
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
