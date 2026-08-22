"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { AreaChart, Area, ResponsiveContainer, Tooltip } from "recharts";

interface Props { ticker: string }

export function MiniChart({ ticker }: Props) {
  const { data } = useQuery({
    queryKey: ["kline-mini", ticker],
    queryFn: () => api.get(`/api/quotes/${ticker}/kline?period=day&count=30`).then((r) => r.data),
    retry: false,
  });

  if (!data?.length) return null;

  const isUp = data[data.length - 1].close >= data[0].close;
  const color = isUp ? "#22c55e" : "#ef4444";

  return (
    <ResponsiveContainer width="100%" height={60}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id={`grad-${ticker}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={color} stopOpacity={0.3} />
            <stop offset="95%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="close"
          stroke={color}
          strokeWidth={1.5}
          fill={`url(#grad-${ticker})`}
          dot={false}
        />
        <Tooltip
          contentStyle={{ background: "#161b27", border: "1px solid #1e2a3b", borderRadius: 6, fontSize: 11 }}
          formatter={(v: number) => [`$${v.toFixed(2)}`, ""]}
          labelFormatter={() => ""}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
