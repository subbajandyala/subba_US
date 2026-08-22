"use client";
import { useState, useRef } from "react";
import { Search } from "lucide-react";

interface Props {
  placeholder?: string;
  defaultValue?: string;
  onSearch: (v: string) => void;
}

export function SearchBar({ placeholder = "Search symbol…", defaultValue = "", onSearch }: Props) {
  const [val, setVal] = useState(defaultValue);
  const inputRef = useRef<HTMLInputElement>(null);

  const commit = () => {
    const v = val.trim().toUpperCase();
    if (v) onSearch(v);
  };

  return (
    <div className="flex items-center gap-2 bg-surface-card border border-surface-border rounded-lg px-3 py-2 focus-within:border-brand-500 transition-colors">
      <Search className="w-4 h-4 text-slate-500" />
      <input
        ref={inputRef}
        value={val}
        onChange={(e) => setVal(e.target.value.toUpperCase())}
        onKeyDown={(e) => e.key === "Enter" && commit()}
        placeholder={placeholder}
        className="bg-transparent outline-none text-sm text-slate-200 placeholder-slate-600 w-36"
      />
      <button
        onClick={commit}
        className="text-xs text-brand-400 hover:text-brand-300 font-medium px-1"
      >
        Go
      </button>
    </div>
  );
}
