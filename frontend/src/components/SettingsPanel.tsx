"use client";

interface SettingsPanelProps {
  apiKey: string;
  model: string;
  captureDuration: number;
  captureFps: number;
  temperature: number;
  mediaResolution: string;
  thinkingLevel: string;
  onUpdate: (updates: Record<string, unknown>) => void;
}

const THINKING_LEVELS = [
  { value: "none", label: "Minimal" },
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];

export function SettingsPanel({
  apiKey,
  model,
  captureDuration,
  captureFps,
  temperature,
  mediaResolution,
  thinkingLevel,
  onUpdate,
}: SettingsPanelProps) {
  const isPro = model.includes("pro");
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/80 p-5 overflow-hidden">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400 mb-4">
        Settings
      </h2>
      <div className="space-y-4">
        {/* API Key */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs text-zinc-500">Gemini API Key</label>
            {apiKey && apiKey !== "" && (
              <span className="text-xs text-emerald-500/70">
                {apiKey.includes("...") ? "Set via .env" : "Set"}
              </span>
            )}
          </div>
          <input
            type="password"
            value={apiKey.includes("...") ? "" : apiKey}
            onChange={(e) => onUpdate({ gemini_api_key: e.target.value })}
            placeholder={apiKey.includes("...") ? apiKey : "Enter API key..."}
            className="w-full rounded-lg bg-zinc-800/60 border border-zinc-700/50 px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
          />
        </div>

        {/* Model */}
        <div>
          <label className="block text-xs text-zinc-500 mb-1.5">Model</label>
          <div className="select-wrap">
            <select
              value={model}
              onChange={(e) => onUpdate({ model: e.target.value })}
              className="w-full rounded-lg bg-zinc-800/60 border border-zinc-700/50 px-3 py-2 pr-8 text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-emerald-500/50 appearance-none cursor-pointer"
            >
              <option value="gemini-3-flash-preview">Gemini 3 Flash</option>
              <option value="gemini-3-pro-preview">Gemini 3 Pro</option>
            </select>
          </div>
        </div>

        {/* Thinking Level */}
        <div>
          <div className="flex justify-between text-xs mb-1.5">
            <span className="text-zinc-500">Thinking Level</span>
          </div>
          <div className="flex gap-1.5">
            {THINKING_LEVELS.map(({ value, label }) => {
              const disabled = isPro && (value === "none" || value === "medium");
              const selected = thinkingLevel === value;
              return (
                <button
                  key={value}
                  disabled={disabled}
                  onClick={() => onUpdate({ thinking_level: value })}
                  className={`flex-1 rounded-lg border px-2 py-1.5 text-xs font-medium transition-colors ${
                    disabled
                      ? "border-zinc-800/50 bg-zinc-900/40 text-zinc-700 cursor-not-allowed"
                      : selected
                        ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-400"
                        : "border-zinc-700/50 bg-zinc-800/60 text-zinc-500 hover:text-zinc-300"
                  }`}
                  title={disabled ? "Not available for Pro" : ""}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Capture Duration */}
        <div>
          <div className="flex justify-between text-xs mb-1.5">
            <span className="text-zinc-500">Capture Duration</span>
            <span className="text-zinc-400 font-mono">{captureDuration}s</span>
          </div>
          <input
            type="range"
            min="0.5"
            max="5"
            step="0.5"
            value={captureDuration}
            onChange={(e) =>
              onUpdate({ capture_duration: parseFloat(e.target.value) })
            }
            className="w-full accent-emerald-500"
          />
        </div>

        {/* Capture FPS */}
        <div>
          <div className="flex justify-between text-xs mb-1.5">
            <span className="text-zinc-500">Video FPS</span>
            <span className="text-zinc-400 font-mono">{captureFps} fps</span>
          </div>
          <input
            type="range"
            min="1"
            max="10"
            step="1"
            value={captureFps}
            onChange={(e) =>
              onUpdate({ capture_fps: parseInt(e.target.value) })
            }
            className="w-full accent-emerald-500"
          />
          <div className="flex justify-between text-[10px] text-zinc-600 mt-1">
            <span>1 fps</span>
            <span>10 fps</span>
          </div>
        </div>

        {/* Media Resolution */}
        <div>
          <div className="flex justify-between text-xs mb-1.5">
            <span className="text-zinc-500">Media Resolution</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => onUpdate({ media_resolution: "low" })}
              className={`flex-1 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                mediaResolution === "low"
                  ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-400"
                  : "border-zinc-700/50 bg-zinc-800/60 text-zinc-500 hover:text-zinc-300"
              }`}
            >
              Low
            </button>
            <button
              onClick={() => onUpdate({ media_resolution: "default" })}
              className={`flex-1 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                mediaResolution !== "low"
                  ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-400"
                  : "border-zinc-700/50 bg-zinc-800/60 text-zinc-500 hover:text-zinc-300"
              }`}
            >
              Default
            </button>
          </div>
        </div>

        {/* Video context token estimate */}
        <div className="rounded-lg bg-zinc-800/40 border border-zinc-700/30 px-3 py-2 text-center">
          <span className="text-[11px] text-zinc-500">Est. video context: </span>
          <span className="text-[11px] text-zinc-300 font-mono">
            ~{Math.ceil(captureDuration * captureFps) * (mediaResolution === "low" ? 66 : 258) + Math.round(32 * captureDuration)} tokens/call
          </span>
          <span className="text-[11px] text-zinc-600"> ({Math.ceil(captureDuration * captureFps)} frames)</span>
        </div>

        {/* Temperature */}
        <div>
          <div className="flex justify-between text-xs mb-1.5">
            <span className="text-zinc-500">Temperature</span>
            <span className="text-zinc-400 font-mono">{temperature}</span>
          </div>
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={temperature}
            onChange={(e) =>
              onUpdate({ temperature: parseFloat(e.target.value) })
            }
            className="w-full accent-emerald-500"
          />
        </div>
      </div>
    </div>
  );
}
