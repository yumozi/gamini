"use client";

import { useEffect, useRef } from "react";

interface ActionEntry {
  iteration: number;
  action: string;
  key?: string;
  x?: number;
  y?: number;
  button?: string;
  duration?: number;
  timestamp: number;
}

interface ActionLogProps {
  entries: ActionEntry[];
}

export function ActionLog({ entries }: ActionLogProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [entries]);

  function formatAction(entry: ActionEntry): string {
    const parts = [entry.action];
    if (entry.key) parts.push(`key="${entry.key}"`);
    if (entry.x !== undefined) parts.push(`x=${entry.x}`);
    if (entry.y !== undefined) parts.push(`y=${entry.y}`);
    if (entry.button) parts.push(`btn=${entry.button}`);
    if (entry.duration) parts.push(`${entry.duration}s`);
    return parts.join(" ");
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/80 p-5 flex flex-col overflow-hidden">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400 mb-3">
        Action Log
      </h2>
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto min-h-[200px] max-h-[400px] font-mono text-xs"
      >
        {entries.length === 0 ? (
          <p className="text-sm text-zinc-600 italic font-sans">
            No actions yet...
          </p>
        ) : (
          <table className="w-full">
            <thead className="sticky top-0 bg-zinc-900/95">
              <tr className="text-left text-zinc-500">
                <th className="pb-2 pr-3">#</th>
                <th className="pb-2 pr-3">Time</th>
                <th className="pb-2">Action</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry, i) => (
                <tr
                  key={i}
                  className="border-t border-zinc-800/50 text-zinc-400 hover:text-zinc-200 transition-colors"
                >
                  <td className="py-1.5 pr-3 text-zinc-600">{entry.iteration}</td>
                  <td className="py-1.5 pr-3 text-zinc-500 whitespace-nowrap">
                    {new Date(entry.timestamp).toLocaleTimeString()}
                  </td>
                  <td className="py-1.5 text-emerald-400/70">{formatAction(entry)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
