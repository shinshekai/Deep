"""GPU VRAM monitor polling every 2s via pynvml with 4 pressure levels."""

import asyncio
import logging
from enum import Enum

logger = logging.getLogger(__name__)

PressureLevel = Enum("PressureLevel", ["GREEN", "YELLOW", "ORANGE", "RED"])


class VRAMMonitor:
    """Continuously monitor GPU VRAM and report pressure levels."""

    GREEN_THRESHOLD = 0.70
    YELLOW_THRESHOLD = 0.85
    ORANGE_THRESHOLD = 0.93

    def __init__(self):
        self._pynvml_available = False
        self._total_mb = 0
        self._used_mb = 0
        self._pct = 0.0
        self._level = "green"
        self._callbacks: list = []

    async def initialize(self) -> bool:
        """Probe pynvml availability. Returns True if GPU monitor active."""
        try:
            import pynvml

            pynvml.nvmlInit()
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._pynvml_available = True
            info = pynvml.nvmlDeviceGetMemoryInfo(self._handle)
            self._total_mb = info.total / (1024**2)
            logger.info(f"VRAM monitor active: {self._total_mb:.0f} MB total")
            return True
        except Exception as e:
            logger.warning(f"VRAM monitor unavailable (no pynvml/GPU): {e}")
            self._total_mb = 0
            return False

    @property
    def is_active(self) -> bool:
        return self._pynvml_available

    def on_update(self, callback):
        """Register callback for pressure level changes."""
        self._callbacks.append(callback)

    async def poll_once(self) -> dict:
        """Read current VRAM state and compute pressure level."""
        if not self._pynvml_available:
            return {
                "vram_total_mb": 0,
                "vram_used_mb": 0,
                "vram_used_pct": 0,
                "pressure_level": "green",
                "gpu_available": False,
            }
        try:
            import pynvml

            info = pynvml.nvmlDeviceGetMemoryInfo(self._handle)
            self._total_mb = info.total / (1024**2)
            self._used_mb = info.used / (1024**2)
            self._pct = self._used_mb / self._total_mb if self._total_mb > 0 else 0
            self._level = self._compute_level(self._pct)

            result = {
                "vram_total_mb": round(self._total_mb, 1),
                "vram_used_mb": round(self._used_mb, 1),
                "vram_used_pct": round(self._pct * 100, 1),
                "pressure_level": self._level,
                "gpu_available": True,
            }
            for cb in self._callbacks:
                cb(result)
            return result
        except Exception as e:
            logger.error(f"VRAM poll error: {e}")
            return {
                "vram_total_mb": self._total_mb,
                "vram_used_mb": 0,
                "vram_used_pct": 0,
                "pressure_level": "green",
                "gpu_available": False,
            }

    def _compute_level(self, pct: float) -> str:
        if pct < self.GREEN_THRESHOLD:
            return "green"
        elif pct < self.YELLOW_THRESHOLD:
            return "yellow"
        elif pct < self.ORANGE_THRESHOLD:
            return "orange"
        else:
            return "red"

    async def start_polling(self, interval: float = 2.0):
        """Poll VRAM until cancelled."""
        while True:
            await self.poll_once()
            await asyncio.sleep(interval)
