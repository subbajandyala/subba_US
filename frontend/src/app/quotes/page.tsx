"use client";
import { useState } from "react";
import { QuoteDetail } from "@/components/QuoteDetail";
import { SearchBar } from "@/components/SearchBar";

export default function QuotesPage() {
  const [ticker, setTicker] = useState("AAPL");

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Stock Quotes</h1>
          <p className="text-slate-400 text-sm">US equities — live price, chart &amp; order book</p>
        </div>
        <div className="ml-auto">
          <SearchBar placeholder="Symbol" onSearch={setTicker} defaultValue={ticker} />
        </div>
      </div>
      <QuoteDetail ticker={ticker} />
    </div>
  );
}
