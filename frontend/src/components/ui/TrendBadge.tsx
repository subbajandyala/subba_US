import { TrendingUp, TrendingDown } from "lucide-react";

interface Props {
  value: number;
  prefix?: string;
  suffix?: string;
  digits?: number;
}

export function TrendBadge({ value, prefix = "", suffix = "", digits = 2 }: Props) {
  const isUp = value >= 0;
  const cls = isUp ? "text-up" : "text-down";
  const sign = isUp ? "+" : "";
  return (
    <span className={`inline-flex items-center gap-1 ${cls}`}>
      {isUp ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
      {prefix}{sign}{value.toFixed(digits)}{suffix}
    </span>
  );
}
