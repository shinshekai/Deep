const { app, BrowserWindow, Tray, Menu, shell, nativeImage } = require("electron");
const { spawn, exec } = require("child_process");
const path = require("path");
const http = require("http");

const DEEP_URL = "http://localhost:3782";
const BACKEND_URL = "http://localhost:8001/api/v1/health";
const POLL_INTERVAL = 3000;

let tray = null;
let mainWindow = null;
let deepProcess = null;
let isRunning = false;

const icon = nativeImage.createFromDataURL(
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAAXNSR0IArs4cQAAAARnQU1BAACxjwv8YQUAAAAkSURBVHgB7cExAQAAAMKg9U9tDQ+gAAAAAAAAAAAAAAAAAICcA+0AAXsJBw0AAAAASUVORK5CYII="
);

function checkBackend() {
  return new Promise((resolve) => {
    const req = http.get(BACKEND_URL, (res) => {
      resolve(res.statusCode === 200);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(3000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function updateTrayStatus() {
  if (!tray) return;
  const healthy = await checkBackend();
  if (healthy) {
    tray.setToolTip("DEEP — Running (localhost:3782)");
    tray.setImage(icon);
    isRunning = true;
  } else {
    tray.setToolTip("DEEP — Not running");
    isRunning = false;
  }
  updateContextMenu();
}

function updateContextMenu() {
  if (!tray) return;
  const contextMenu = Menu.buildFromTemplate([
    {
      label: isRunning ? "Open DEEP" : "Start DEEP",
      click: () => {
        if (isRunning) {
          shell.openExternal(DEEP_URL);
        } else {
          startDeep();
        }
      },
    },
    { type: "separator" },
    {
      label: "Check Status",
      click: updateTrayStatus,
    },
    {
      label: "Open in Browser",
      click: () => shell.openExternal(DEEP_URL),
    },
    { type: "separator" },
    {
      label: "Quit",
      role: "quit",
    },
  ]);
  tray.setContextMenu(contextMenu);
}

function startDeep() {
  const deepDir = path.resolve(__dirname, "..");

  const platform = process.platform;
  if (platform === "win32") {
    deepProcess = spawn("powershell", ["-ExecutionPolicy", "Bypass", "-File", path.join(deepDir, "install.ps1")], {
      cwd: deepDir,
      detached: false,
      stdio: "ignore",
    });
  } else {
    deepProcess = spawn("bash", [path.join(deepDir, "install.sh")], {
      cwd: deepDir,
      detached: false,
      stdio: "ignore",
    });
  }

  deepProcess.on("error", (err) => {
    tray.setToolTip(`DEEP — Error: ${err.message}`);
  });

  tray.setToolTip("DEEP — Starting...");

  const pollTimer = setInterval(async () => {
    const healthy = await checkBackend();
    if (healthy) {
      clearInterval(pollTimer);
      isRunning = true;
      tray.setToolTip("DEEP — Running");
      updateContextMenu();
      shell.openExternal(DEEP_URL);
    }
  }, POLL_INTERVAL);

  setTimeout(() => clearInterval(pollTimer), 60000);
}

app.whenReady().then(() => {
  tray = new Tray(icon);
  tray.setToolTip("DEEP — Not running");

  tray.on("click", () => {
    if (isRunning) {
      shell.openExternal(DEEP_URL);
    } else {
      startDeep();
    }
  });

  tray.on("double-click", () => {
    if (isRunning) {
      shell.openExternal(DEEP_URL);
    } else {
      startDeep();
    }
  });

  updateContextMenu();
  updateTrayStatus();

  setInterval(updateTrayStatus, 30000);
});

app.on("window-all-closed", (e) => {
  e.preventDefault();
});

app.on("before-quit", () => {
  if (deepProcess) {
    try {
      deepProcess.kill();
    } catch {}
  }
});
