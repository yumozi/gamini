# Player AI

Visual game player agent: captures screen video → sends to Gemini → executes returned keyboard/mouse actions in a loop. React/Next.js frontend for controls and live status.

## Architecture

- **Backend:** Python 3.13 + FastAPI + uvicorn (port 8000)
- **Frontend:** Next.js 15 + React 19 + TypeScript + Tailwind (port 3000)
- **Gemini SDK:** `google-genai` with structured output via `response_schema`
- **Screen capture:** ffmpeg subprocess (gdigrab on Windows, avfoundation on macOS)
- **Input (Windows):** `pydirectinput-rgx` (DirectInput scan codes)
- **Input (macOS):** `pyobjc-framework-Quartz` (CGEventPost)
- **Window management:** `pywinctl`
- **Communication:** REST (config, windows) + WebSocket (commands, live status)

## Core loop (~3-5s per iteration)

1. ffmpeg captures ~1.5s of screen video to temp file
2. Video bytes sent inline to Gemini with game context prompt
3. Gemini returns structured JSON (`GameActionResponse`: reasoning + actions)
4. Actions executed via platform-specific input backend
5. Status pushed to frontend over WebSocket

## Key files

### Backend (`backend/`)
- `main.py` — FastAPI app, REST routes, WebSocket handler, emergency stop hotkey (F12)
- `models.py` — Pydantic models: `GameAction`, `GameActionResponse`, `LoopStatus`, `AppConfig`
- `config.py` — Runtime config with `.env` loading, thread-safe live updates
- `capture.py` — ffmpeg screen recording via `subprocess.run` in thread executor
- `gemini_client.py` — Gemini API with `response_schema` for enforced structured output, exponential backoff on 429s
- `input_controller.py` — Abstract `InputBackend` ABC, key validation, bounds checking, platform factory
- `input_windows.py` / `input_macos.py` — Platform-specific input implementations
- `window_manager.py` — Window listing + focusing via pywinctl
- `game_loop.py` — Core async loop with per-iteration error handling

### Frontend (`frontend/src/`)
- `app/page.tsx` — Main dashboard, all state management, WebSocket connection
- `lib/websocket.ts` — WebSocket client with auto-reconnect
- `components/` — ControlPanel, GameContextInput, WindowSelector, StatusFeed, ActionLog, SettingsPanel

## Running

Terminal 1 (backend): `.\start.bat` (Windows) or `./start.sh` (macOS)
Terminal 2 (frontend): `cd frontend && npm run dev`

## Design decisions

- **Inline video, not File API** — 1.5s clips are ~50-150KB, well under 100MB inline limit
- **`subprocess.run` in executor** instead of `asyncio.create_subprocess_exec` — the latter fails on Windows with uvicorn's event loop
- **Config re-read per iteration** — frontend changes take effect without restarting the loop
- **Game loop stays in RUNNING state on per-iteration errors** — so the frontend Stop button remains visible
- **API key from `.env` shown as masked placeholder** in frontend; typing a new key overrides it, clearing the field does not wipe the `.env` key
