"use client";

import { useEffect, useRef } from "react";

interface GameContextInputProps {
  value: string;
  onChange: (value: string) => void;
}

export function GameContextInput({ value, onChange }: GameContextInputProps) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const handleChange = (text: string) => {
    // Update local display immediately via parent
    onChange(text);
  };

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/80 p-5 overflow-hidden">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400 mb-3">
        Game Context
      </h2>
      <textarea
        value={value}
        onChange={(e) => handleChange(e.target.value)}
        placeholder={"Describe the game, its controls, and your objectives...\n\nExample: This is Tetris. Use left/right arrows to move, up to rotate, down to soft drop, space to hard drop. Clear as many lines as possible."}
        className="w-full h-36 rounded-lg bg-zinc-800/60 border border-zinc-700/50 p-3 text-sm text-zinc-200 placeholder:text-zinc-600 resize-none focus:outline-none focus:ring-1 focus:ring-emerald-500/50 focus:border-emerald-500/50 transition-colors"
      />
    </div>
  );
}
