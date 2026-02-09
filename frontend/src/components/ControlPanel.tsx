"use client";

interface ControlPanelProps {
  isRunning: boolean;
  connected: boolean;
  iteration: number;
  fps: number;
  state: string;
  onStart: () => void;
  onStop: () => void;
}

export function ControlPanel({
  isRunning,
  connected,
  iteration,
  fps,
  state,
  onStart,
  onStop,
}: ControlPanelProps) {
  const stateColors: Record<string, string> = {
    idle: "bg-zinc-700",
    running: "bg-emerald-500",
    error: "bg-red-500",
    stopping: "bg-amber-500",
  };

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/80 p-5 overflow-hidden">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400">
          Control
        </h2>
        <div className="flex items-center gap-2">
          <span
            className={`h-2.5 w-2.5 rounded-full ${
              connected ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]" : "bg-zinc-600"
            }`}
          />
          <span className="text-xs text-zinc-500">
            {connected ? "Connected" : "Disconnected"}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <button
          onClick={isRunning ? onStop : onStart}
          disabled={!connected}
          className={`flex-1 rounded-lg px-4 py-2.5 text-sm font-medium transition-all ${
            isRunning
              ? "bg-red-500/20 text-red-300 hover:bg-red-500/30 border border-red-500/30"
              : "bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30 border border-emerald-500/30"
          } disabled:opacity-40 disabled:cursor-not-allowed`}
        >
          {isRunning ? "Stop" : "Start"}
        </button>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg bg-zinc-800/60 p-3 text-center">
          <div className="text-xs text-zinc-500 mb-1">Status</div>
          <div className="flex items-center justify-center gap-1.5">
            <span className={`h-2 w-2 rounded-full ${stateColors[state] || "bg-zinc-700"}`} />
            <span className="text-sm font-medium capitalize">{state}</span>
          </div>
        </div>
        <div className="rounded-lg bg-zinc-800/60 p-3 text-center">
          <div className="text-xs text-zinc-500 mb-1">Iteration</div>
          <div className="text-sm font-mono font-medium">{iteration}</div>
        </div>
        <div className="rounded-lg bg-zinc-800/60 p-3 text-center">
          <div className="text-xs text-zinc-500 mb-1">Loop/s</div>
          <div className="text-sm font-mono font-medium">{fps.toFixed(2)}</div>
        </div>
      </div>
    </div>
  );
}
