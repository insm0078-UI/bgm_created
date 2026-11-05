# AI BGM STUDIO

A Windows desktop app that generates **instrumental background music** (no vocals) for video
and anime scenes with the local [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5) model.
It's free and runs locally, with no paid APIs.

## Features
- Scene presets, mood, instruments, length (up to the GPU tier limit), and a free-form Korean description
- AI recommendations (scene analysis), dialogue background mode, multiple versions at once, cancel
- Playback, trimming, smooth fade in/out, volume, WAV/MP3 export
- Similar versions, seamless loops (extendable to 1/3/5 minutes), generation history and delete

## Structure
```
app/      Tauri 2 + React/TypeScript UI (starts and stops the AI engine)
engine/   Python engine (bgm_engine) — wraps ACE-Step 1.5 behind a local HTTP API
```
The engine listens only on `127.0.0.1` and is protected by a random per-launch token.

## Development setup (Windows)
Requirements: NVIDIA GPU, Node.js, Rust (MSVC), Visual Studio C++ Build Tools, uv

1. Prepare ACE-Step 1.5 next to this folder (`../ACE-Step-1.5`).
   ```
   uv sync --python 3.11
   uvx --from "huggingface_hub[cli]" hf download ACE-Step/Ace-Step1.5 --local-dir checkpoints
   ```
2. Run the app
   ```
   cd app
   npm install
   powershell -ExecutionPolicy Bypass -File dev.ps1
   ```

## Tests
```
cd engine
set PYTHONPATH=.
..\..\ACE-Step-1.5\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

## License notes
- ACE-Step 1.5 code and model weights: MIT (commercial use allowed per the model card)
- We can't guarantee that generated music is free of similarity to existing works.
