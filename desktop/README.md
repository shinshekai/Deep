# DEEP Desktop Launcher

System tray application that starts DEEP and provides quick access.

## Features
- System tray icon showing DEEP status (running/not running)
- Click tray icon to open DEEP in browser
- Right-click for context menu: Start, Open, Check Status, Quit
- Auto-polls backend health every 30 seconds
- Cross-platform: Windows, macOS, Linux

## Development
```bash
cd desktop
npm install
npm start
```

## Build
```bash
npm run build:win    # Windows NSIS installer
npm run build:mac    # macOS DMG
npm run build:linux  # Linux AppImage
```

## How it works
1. On launch, creates a system tray icon
2. Checks if DEEP backend is already running at localhost:8001
3. If not running, executes `install.sh` or `install.ps1` from repo root
4. Polls backend health until ready, then opens browser to localhost:3782
5. Monitors status every 30 seconds, updates tray tooltip
6. On quit, kills the DEEP process
