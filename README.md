# Player AI

A visual game player agent that captures screen video, sends it to Gemini for analysis, and executes the returned keyboard/mouse actions in a loop. React/Next.js frontend provides controls, context input, and live status.

## Prerequisites

### Both platforms

- **Python 3.11+** — https://www.python.org/downloads/
- **Node.js 18+** — https://nodejs.org/
- **ffmpeg** — must be installed and on your PATH
- **Gemini API key** — https://aistudio.google.com/apikey

### Windows

Install ffmpeg via Chocolatey:

```
choco install ffmpeg
```

Or download from https://ffmpeg.org/download.html, extract, and add the `bin` folder to your system PATH.

Verify:

```
ffmpeg -version
```

### macOS

```bash
brew install ffmpeg
```

On the first run, macOS will prompt you to grant permissions to your terminal app or IDE (e.g. Terminal, VS Code, etc). Go to **System Settings > Privacy & Security** and enable the following for your terminal:

- **Accessibility** — required for the input controller to send keyboard/mouse events to games
- **Screen Recording** — required for ffmpeg to capture screen content

You may also see a **Camera** access prompt. This is a macOS quirk: ffmpeg uses the AVFoundation framework to capture the screen (device `1:none` in `capture.py` line 54), and macOS triggers the camera permission dialog for any AVFoundation video access, even though only screen capture is used. It is safe to grant — no camera data is accessed.

## Setup

### 1. Clone and set up the backend

```bash
cd player-ai
python -m venv .venv
```

Activate the virtual environment:

- **Windows (PowerShell):** `.venv\Scripts\activate`
- **Windows (cmd):** `.venv\Scripts\activate.bat`
- **macOS/Linux:** `source .venv/bin/activate`

Install dependencies:

```bash
pip install -r requirements.txt
```

### 2. Configure API key

Copy the example env file and add your Gemini API key:

```bash
cp .env.example .env
```

Edit `.env`:

```
GEMINI_API_KEY=your-actual-key-here
```

You can also set the key from the frontend Settings panel at runtime.

### 3. Set up the frontend

```bash
cd frontend
npm install
```

## Running

You need **two terminals** — one for the backend, one for the frontend.

### Terminal 1 — Backend

**Windows:**

```
.\start.bat
```

**macOS:**

```bash
chmod +x start.sh   # first time only
./start.sh
```

Or manually:

```bash
# Activate venv first (see Setup step 1)
python -m backend.main
```

The backend starts at **http://localhost:8000**.

### Terminal 2 — Frontend

```bash
cd frontend
npm run dev
```

The frontend starts at **http://localhost:3000**.

Open http://localhost:3000 in your browser.

## Usage

1. Start both backend and frontend
2. Open http://localhost:3000
3. The connection indicator in the Control panel should show green "Connected"
4. Select a capture target window (or leave as Full Screen)
5. Write game context in the textarea — describe the game, its controls, and objectives
6. Click **Start**
7. The agent will capture screen video, analyze it with Gemini, and execute actions in a loop
8. Click **Stop** to stop the loop

### Emergency Stop

Press **F12** to immediately stop the game loop regardless of the frontend state. This is a global hotkey registered at the system level.

- **Windows:** Works globally via RegisterHotKey
- **macOS:** Works globally via NSEvent monitor (requires Accessibility permission)

Note: F12 in the browser opens DevTools — the emergency stop is registered by the backend process, not the browser.

## Configuration

All settings can be changed from the frontend Settings panel while the agent is running. Changes take effect on the next loop iteration.

| Setting | Default | Description |
|---------|---------|-------------|
| Gemini API Key | from `.env` | Can also be set in the frontend |
| Model | Gemini 3 Flash | Also supports Gemini 3 Pro |
| Capture Duration | 1.5s | How long each screen recording is |
| Capture FPS | 5 | Frames per second (1-10, sent to Gemini via video_metadata) |
| Temperature | 1.0 | Gemini sampling temperature (0-1) |
| Media Resolution | Low | Low (66 tok/frame) or Default (258 tok/frame) |

## Project Structure

```
player-ai/
├── backend/
│   ├── main.py              # FastAPI server, REST + WebSocket
│   ├── models.py            # Pydantic models (actions, config, status)
│   ├── config.py            # Runtime config with .env loading
│   ├── capture.py           # ffmpeg screen recording
│   ├── gemini_client.py     # Gemini API with structured output
│   ├── input_controller.py  # Abstract input + platform factory
│   ├── input_windows.py     # Windows input (pydirectinput)
│   ├── input_macos.py       # macOS input (Quartz CGEventPost)
│   ├── window_manager.py    # Window listing/focusing (pywinctl)
│   └── game_loop.py         # Core capture → infer → act loop
├── frontend/                # Next.js + React + TypeScript + Tailwind
│   └── src/
│       ├── app/page.tsx     # Main dashboard
│       ├── components/      # UI components
│       └── lib/websocket.ts # WebSocket client
├── start.bat                # Windows launcher
├── start.sh                 # macOS/Linux launcher
├── requirements.txt
├── .env.example
└── .gitignore
```

## Troubleshooting

### `ffmpeg: command not found` / `The system cannot find the file specified`

ffmpeg is not installed or not on PATH. See Prerequisites above.

### `NotImplementedError` from asyncio subprocess

Fixed in current version. If you see this, make sure you have the latest `capture.py` which uses `subprocess.run` instead of `asyncio.create_subprocess_exec`.

### Frontend shows "Disconnected"

The backend isn't running. Start it first in a separate terminal.

### `No Gemini API key configured`

Set `GEMINI_API_KEY` in your `.env` file, or enter it in the frontend Settings panel.

### macOS: Input events not working in games

Grant Accessibility permission to your terminal/Python in System Settings > Privacy & Security > Accessibility.
