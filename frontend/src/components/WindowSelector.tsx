"use client";

import { useCallback, useState } from "react";

interface WindowInfo {
  title: string;
  geometry: { x: number; y: number; w: number; h: number } | null;
}

interface WindowSelectorProps {
  windows: WindowInfo[];
  selected: string | null;
  onSelect: (title: string | null) => void;
  onRefresh: () => void;
}

export function WindowSelector({
  windows,
  selected,
  onSelect,
  onRefresh,
}: WindowSelectorProps) {
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    onRefresh();
    setTimeout(() => setRefreshing(false), 500);
  }, [onRefresh]);

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/80 p-5 overflow-hidden">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400 mb-3">
        Capture Target
      </h2>
      <div className="flex gap-2">
        <div className="select-wrap flex-1 min-w-0">
          <select
            value={selected ?? "__fullscreen__"}
            onChange={(e) =>
              onSelect(e.target.value === "__fullscreen__" ? null : e.target.value)
            }
            className="w-full rounded-lg bg-zinc-800/60 border border-zinc-700/50 px-3 py-2 pr-8 text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-emerald-500/50 appearance-none cursor-pointer truncate"
          >
            <option value="__fullscreen__">Full Screen</option>
            {windows.map((w) => (
              <option key={w.title} value={w.title}>
                {w.title}
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="shrink-0 rounded-lg bg-zinc-800/60 border border-zinc-700/50 w-9 h-9 flex items-center justify-center text-sm text-zinc-400 hover:text-zinc-200 hover:border-zinc-600 transition-colors disabled:opacity-50"
          title="Refresh window list"
        >
          <svg
            className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M4 4v5h5M20 20v-5h-5M4.93 9a9 9 0 0115.36-1.36L20 9M19.07 15A9 9 0 013.71 16.36L4 15"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
