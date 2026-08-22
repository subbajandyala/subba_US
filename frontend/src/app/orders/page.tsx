"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Loader } from "@/components/ui/Loader";

const STATUS_COLOR: Record<string, string> = {
  FILLED_ALL: "text-up",
  SUBMITTED: "text-brand-400",
  FILLED_PART: "text-yellow-400",
  CANCELLED_ALL: "text-slate-500",
  FAILED: "text-down",
};

export default function OrdersPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["orders-active"],
    queryFn: () => api.get("/api/account/orders?status=active").then((r) => r.data),
    refetchInterval: 8_000,
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Orders</h1>
      {isLoading && <Loader />}
      {error && <p className="text-red-400">Failed to load orders.</p>}
      {data?.orders && (
        <div className="overflow-x-auto rounded-xl border border-surface-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-400 border-b border-surface-border">
                {["Order ID", "Symbol", "Side", "Type", "Qty", "Price", "Filled", "Avg Fill", "Status", "Created"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.orders.map((o: any) => (
                <tr key={o.order_id} className="border-b border-surface-border hover:bg-surface-hover transition-colors">
                  <td className="px-4 py-3 num-font text-xs text-slate-500">{o.order_id.slice(-8)}</td>
                  <td className="px-4 py-3 font-semibold text-brand-400">{o.code.replace("US.", "")}</td>
                  <td className={`px-4 py-3 font-medium ${o.trd_side.includes("BUY") ? "text-up" : "text-down"}`}>{o.trd_side}</td>
                  <td className="px-4 py-3 text-slate-400">{o.order_type}</td>
                  <td className="px-4 py-3 num-font">{o.qty}</td>
                  <td className="px-4 py-3 num-font">${o.price.toFixed(2)}</td>
                  <td className="px-4 py-3 num-font">{o.dealt_qty}</td>
                  <td className="px-4 py-3 num-font">{o.dealt_avg_price ? `$${o.dealt_avg_price.toFixed(2)}` : "—"}</td>
                  <td className={`px-4 py-3 text-xs font-medium ${STATUS_COLOR[o.order_status] ?? "text-slate-400"}`}>{o.order_status}</td>
                  <td className="px-4 py-3 text-xs text-slate-500">{o.create_time}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.orders.length === 0 && <p className="text-slate-500 text-center py-8">No active orders</p>}
        </div>
      )}
    </div>
  );
}
