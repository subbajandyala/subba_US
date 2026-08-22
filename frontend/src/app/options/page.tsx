"use client";
import { useState } from "react";
import { OptionsChain } from "@/components/OptionsChain";
import { SearchBar } from "@/components/SearchBar";
import { QuoteCard } from "@/components/QuoteCard";

export default function OptionsPage() {
  const [ticker, setTicker] = useState("AAPL");

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Options Chain</h1>
          <p className="text-slate-400 text-sm">Real-time US equity options via MooMoo</p>
        </div>
        <div className="ml-auto">
          <SearchBar
            placeholder="Symbol (e.g. AAPL)"
            onSearch={setTicker}
            defaultValue={ticker}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
        <div className="xl:col-span-1">
          <QuoteCard ticker={ticker} large />
        </div>
        <div className="xl:col-span-3">
          <OptionsChain ticker={ticker} />
        </div>
      </div>
    </div>
  );
}
