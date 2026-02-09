"use client";

import { useEffect, useRef, useState } from "react";

interface StatusEntry {
  iteration: number;
  reasoning: string;
  timestamp: number;
  videoUrl?: string;
}

interface StatusFeedProps {
  entries: StatusEntry[];
}

function VideoPreview({ url }: { url: string }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="mt-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="text-xs text-emerald-400/70 hover:text-emerald-400 transition-colors"
      >
        {expanded ? "Hide video" : "Show video"}
      </button>
      {expanded && (
        <video
          src={url}
          controls
          muted
          className="mt-1.5 rounded-md border border-zinc-700/50 w-full max-w-md"
        />
      )}
    </div>
  );
}

export function StatusFeed({ entries }: StatusFeedProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [entries]);

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/80 p-5 flex flex-col overflow-hidden">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400 mb-3">
        AI Reasoning
      </h2>
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto space-y-2 min-h-[200px] max-h-[400px]"
      >
        {entries.length === 0 ? (
          <p className="text-sm text-zinc-600 italic">
            Waiting for first iteration...
          </p>
        ) : (
          entries.map((entry, idx) => (
            <div
              key={`${entry.iteration}-${idx}`}
              className="rounded-lg bg-zinc-800/40 border border-zinc-800 p-3"
            >
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-xs font-mono text-emerald-400/80">
                  #{entry.iteration}
                </span>
                <span className="text-xs text-zinc-600">
                  {new Date(entry.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <p className="text-sm text-zinc-300 leading-relaxed">
                {entry.reasoning}
              </p>
              {entry.videoUrl && <VideoPreview url={entry.videoUrl} />}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
