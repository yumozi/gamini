"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { GameWebSocket } from "@/lib/websocket";
import { ControlPanel } from "@/components/ControlPanel";
import { GameContextInput } from "@/components/GameContextInput";
import { WindowSelector } from "@/components/WindowSelector";
import { StatusFeed } from "@/components/StatusFeed";
import { ActionLog } from "@/components/ActionLog";
import { SettingsPanel } from "@/components/SettingsPanel";

interface WindowInfo {
  title: string;
  geometry: { x: number; y: number; w: number; h: number } | null;
}

interface StatusEntry {
  iteration: number;
  reasoning: string;
  timestamp: number;
  videoUrl?: string;
}

interface ActionEntry {
  iteration: number;
  action: string;
  key?: string;
  x?: number;
  y?: number;
  bbox?: number[];
  button?: string;
  duration?: number;
  timestamp: number;
}

interface LoopStatus {
  state: string;
  iteration: number;
  reasoning: string;
  actions: Array<{
    action: string;
    key?: string;
    x?: number;
    y?: number;
    bbox?: number[];
    button?: string;
    duration?: number;
  }>;
  fps: number;
  error?: string;
  video_url?: string;
}

const MAX_LOG_ENTRIES = 500;

export default function Home() {
  const wsRef = useRef<GameWebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [loopState, setLoopState] = useState("idle");
  const [iteration, setIteration] = useState(0);
  const [fps, setFps] = useState(0);
  const [statusEntries, setStatusEntries] = useState<StatusEntry[]>([]);
  const [actionEntries, setActionEntries] = useState<ActionEntry[]>([]);
  const [windows, setWindows] = useState<WindowInfo[]>([]);
  const [selectedWindow, setSelectedWindow] = useState<string | null>(null);
  const [gameContext, setGameContext] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("gemini-3-flash-preview");
  const [captureDuration, setCaptureDuration] = useState(1.5);
  const [captureFps, setCaptureFps] = useState(5);
  const [temperature, setTemperature] = useState(1.0);
  const [mediaResolution, setMediaResolution] = useState("low");
  const [thinkingLevel, setThinkingLevel] = useState("low");
  const [error, setError] = useState<string | null>(null);

  const fetchWindows = useCallback(async () => {
    try {
      const res = await fetch("/api/windows");
      const data = await res.json();
      setWindows(data.windows || []);
    } catch {
      // backend not available yet
    }
  }, []);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch("/api/config");
      const data = await res.json();
      if (data.gemini_api_key) setApiKey(data.gemini_api_key);
      if (data.model) setModel(data.model);
      if (data.capture_duration) setCaptureDuration(data.capture_duration);
      if (data.capture_fps) setCaptureFps(data.capture_fps);
      if (data.temperature !== undefined) setTemperature(data.temperature);
      if (data.media_resolution) setMediaResolution(data.media_resolution);
      if (data.thinking_level) setThinkingLevel(data.thinking_level);
      setGameContext(data.game_context || "");
      setSelectedWindow(data.target_window || null);
    } catch {
      // backend not available yet
    }
  }, []);

  // WebSocket setup
  useEffect(() => {
    const ws = new GameWebSocket();
    wsRef.current = ws;

    ws.on("connected", () => {
      setConnected(true);
      // Re-sync config from backend on every reconnect (backend may have restarted)
      fetchConfig();
      fetchWindows();
    });
    ws.on("disconnected", () => setConnected(false));

    ws.on("status", (data) => {
      const status = data as LoopStatus;
      setLoopState(status.state);
      setIteration(status.iteration);
      setFps(status.fps);

      if (status.error) {
        setError(status.error);
      } else {
        setError(null);
      }

      if (status.reasoning) {
        setStatusEntries((prev) => {
          const next = [
            ...prev,
            {
              iteration: status.iteration,
              reasoning: status.reasoning,
              timestamp: Date.now(),
              videoUrl: status.video_url
                ? `http://localhost:8000${status.video_url}?t=${Date.now()}`
                : undefined,
            },
          ];
          return next.length > MAX_LOG_ENTRIES
            ? next.slice(-MAX_LOG_ENTRIES)
            : next;
        });
      }

      if (status.actions?.length) {
        setActionEntries((prev) => {
          const now = Date.now();
          const newEntries = status.actions.map((a) => ({
            iteration: status.iteration,
            action: a.action,
            key: a.key ?? undefined,
            x: a.x ?? undefined,
            y: a.y ?? undefined,
            bbox: a.bbox ?? undefined,
            button: a.button ?? undefined,
            duration: a.duration ?? undefined,
            timestamp: now,
          }));
          const next = [...prev, ...newEntries];
          return next.length > MAX_LOG_ENTRIES
            ? next.slice(-MAX_LOG_ENTRIES)
            : next;
        });
      }
    });

    ws.on("ack", (data) => {
      if (data === "started") setLoopState("running");
      if (data === "stopped") setLoopState("idle");
    });

    ws.on("error", (data) => {
      setError(data as string);
    });

    ws.connect();
    return () => ws.disconnect();
  }, []);

  // Fetch initial data
  useEffect(() => {
    fetchWindows();
    fetchConfig();
  }, [fetchWindows, fetchConfig]);

  const handleStart = useCallback(() => {
    wsRef.current?.send("start");
  }, []);

  const handleStop = useCallback(() => {
    wsRef.current?.send("stop");
  }, []);

  const handleConfigUpdate = useCallback(
    (updates: Record<string, unknown>) => {
      if ("gemini_api_key" in updates) setApiKey(updates.gemini_api_key as string);
      if ("model" in updates) setModel(updates.model as string);
      if ("capture_duration" in updates) setCaptureDuration(updates.capture_duration as number);
      if ("capture_fps" in updates) setCaptureFps(updates.capture_fps as number);
      if ("temperature" in updates) setTemperature(updates.temperature as number);
      if ("media_resolution" in updates) setMediaResolution(updates.media_resolution as string);
      if ("thinking_level" in updates) setThinkingLevel(updates.thinking_level as string);

      // Auto-switch thinking level if switching to Pro with unsupported level
      if ("model" in updates) {
        const newModel = updates.model as string;
        if (newModel.includes("pro")) {
          setThinkingLevel((prev) => {
            if (prev === "none" || prev === "medium") {
              updates.thinking_level = "low";
              return "low";
            }
            return prev;
          });
        }
      }

      // Don't send empty API key to backend (would overwrite .env value)
      const toSend = { ...updates };
      if ("gemini_api_key" in toSend && !toSend.gemini_api_key) {
        delete toSend.gemini_api_key;
      }
      if (Object.keys(toSend).length > 0) {
        wsRef.current?.send("config", toSend);
      }
    },
    []
  );

  const contextTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleGameContextChange = useCallback(
    (value: string) => {
      setGameContext(value);
      if (contextTimerRef.current) clearTimeout(contextTimerRef.current);
      contextTimerRef.current = setTimeout(() => {
        wsRef.current?.send("config", { game_context: value });
      }, 500);
    },
    []
  );

  const handleWindowSelect = useCallback(
    (title: string | null) => {
      setSelectedWindow(title);
      wsRef.current?.send("config", { target_window: title });
    },
    []
  );

  const isRunning = loopState === "running" || loopState === "stopping" || loopState === "error";

  return (
    <div className="scanlines grain min-h-screen">
      {/* Ambient emerald glow — drifts behind header */}
      <div className="fixed top-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-emerald-500/[0.03] rounded-full blur-[120px] pointer-events-none" />

      <div className="relative z-10 max-w-7xl mx-auto px-6 py-8">
        {/* ── Header ── */}
        <header className="mb-8 animate-fade-in-up">
          <div className="flex items-end justify-between border-b border-zinc-800/60 pb-6">
            <div>
              <div className="flex items-center gap-3 mb-1">
                <div className="h-8 w-1 bg-emerald-500 rounded-full" />
                <h1 className="text-2xl font-bold tracking-tight text-zinc-50">
                  Player AI
                </h1>
              </div>
              <p className="text-sm text-zinc-500 ml-[19px]">
                Visual game agent &middot; Gemini-powered
              </p>
            </div>
            <div className="flex items-center gap-4 text-xs text-zinc-600 font-mono">
              {error && (
                <span className="text-red-400/80 max-w-xs truncate">
                  {error}
                </span>
              )}
              <span>F12 emergency stop</span>
            </div>
          </div>
        </header>

        {/* ── Two-column layout ── */}
        <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-6">
          {/* Left — config & controls */}
          <div className="space-y-4 stagger">
            <div className="animate-fade-in-up">
              <ControlPanel
                isRunning={isRunning}
                connected={connected}
                iteration={iteration}
                fps={fps}
                state={loopState}
                onStart={handleStart}
                onStop={handleStop}
              />
            </div>
            <div className="animate-fade-in-up">
              <WindowSelector
                windows={windows}
                selected={selectedWindow}
                onSelect={handleWindowSelect}
                onRefresh={fetchWindows}
              />
            </div>
            <div className="animate-fade-in-up">
              <GameContextInput
                value={gameContext}
                onChange={handleGameContextChange}
              />
            </div>
            <div className="animate-fade-in-up">
              <SettingsPanel
                apiKey={apiKey}
                model={model}
                captureDuration={captureDuration}
                captureFps={captureFps}
                temperature={temperature}
                mediaResolution={mediaResolution}
                thinkingLevel={thinkingLevel}
                onUpdate={handleConfigUpdate}
              />
            </div>
          </div>

          {/* Right — live feed */}
          <div className="space-y-4 stagger">
            <div className="animate-fade-in-up">
              <StatusFeed entries={statusEntries} />
            </div>
            <div className="animate-fade-in-up">
              <ActionLog entries={actionEntries} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
