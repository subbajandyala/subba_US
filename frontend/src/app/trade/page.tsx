"use client";
import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { SearchBar } from "@/components/SearchBar";
import { QuoteCard } from "@/components/QuoteCard";
import { Loader } from "@/components/ui/Loader";
import { CheckCircle2, XCircle } from "lucide-react";

type Side = "BUY" | "SELL";
type OType = "NORMAL" | "MARKET" | "STOP" | "STOP_LIMIT";

export default function TradePage() {
  const [ticker, setTicker] = useState("AAPL");
  const [side, setSide] = useState<Side>("BUY");
  const [orderType, setOrderType] = useState<OType>("NORMAL");
  const [qty, setQty] = useState("1");
  const [price, setPrice] = useState("");
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);

  const maxQtyQ = useQuery({
    queryKey: ["max-qty", ticker, price, side],
    queryFn: () =>
      price
        ? api
            .get(`/api/trading/max-qty/${ticker}?price=${price}&side=${side}`)
            .then((r) => r.data)
        : null,
    enabled: !!price && !!ticker,
  });

  const placeMut = useMutation({
    mutationFn: (body: object) => api.post("/api/trading/order", body),
    onSuccess: (res) => setResult({ ok: true, msg: `Order placed! ID: ${res.data.order_id}` }),
    onError: (err: any) =>
      setResult({ ok: false, msg: err?.response?.data?.detail ?? "Order failed" }),
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setResult(null);
    placeMut.mutate({ ticker, qty: parseFloat(qty), price: parseFloat(price), side, order_type: orderType });
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Place Order</h1>
          <p className="text-slate-400 text-sm">US market — MooMoo paper/live</p>
        </div>
        <div className="ml-auto">
          <SearchBar placeholder="Symbol" onSearch={setTicker} defaultValue={ticker} />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <QuoteCard ticker={ticker} large />

        <form onSubmit={submit} className="bg-surface-card border border-surface-border rounded-xl p-5 space-y-4">
          {/* Side */}
          <div className="flex rounded-lg overflow-hidden border border-surface-border">
            {(["BUY", "SELL"] as Side[]).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setSide(s)}
                className={`flex-1 py-2 text-sm font-semibold transition-colors ${
                  side === s
                    ? s === "BUY" ? "bg-up text-white" : "bg-down text-white"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {s}
              </button>
            ))}
          </div>

          {/* Order type */}
          <div>
            <label className="text-xs text-slate-400 mb-1 block">Order Type</label>
            <select
              value={orderType}
              onChange={(e) => setOrderType(e.target.value as OType)}
              className="w-full bg-surface border border-surface-border rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-brand-500"
            >
              <option value="NORMAL">Limit</option>
              <option value="MARKET">Market</option>
              <option value="STOP">Stop</option>
              <option value="STOP_LIMIT">Stop Limit</option>
            </select>
          </div>

          {/* Price */}
          <div>
            <label className="text-xs text-slate-400 mb-1 block">Price (USD)</label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="0.00"
              className="w-full bg-surface border border-surface-border rounded-lg px-3 py-2 text-sm num-font focus:outline-none focus:border-brand-500"
            />
          </div>

          {/* Qty */}
          <div>
            <label className="text-xs text-slate-400 mb-1 block">
              Quantity
              {maxQtyQ.data && (
                <span className="ml-2 text-brand-400">
                  (max {side === "SELL" ? maxQtyQ.data.max_position_sell : maxQtyQ.data.max_cash_buy})
                </span>
              )}
            </label>
            <input
              type="number"
              step="1"
              min="1"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              className="w-full bg-surface border border-surface-border rounded-lg px-3 py-2 text-sm num-font focus:outline-none focus:border-brand-500"
            />
          </div>

          {/* Total estimate */}
          {price && qty && (
            <div className="text-xs text-slate-400 bg-surface rounded-lg px-3 py-2">
              Estimated total:{" "}
              <span className="text-white num-font font-medium">
                ${(parseFloat(price) * parseFloat(qty)).toFixed(2)}
              </span>
            </div>
          )}

          <button
            type="submit"
            disabled={placeMut.isPending}
            className={`w-full py-3 rounded-lg font-semibold text-white transition-colors ${
              side === "BUY"
                ? "bg-up hover:bg-green-600 disabled:bg-green-900"
                : "bg-down hover:bg-red-600 disabled:bg-red-900"
            }`}
          >
            {placeMut.isPending ? "Placing…" : `${side} ${ticker}`}
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
