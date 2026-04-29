"""VRAM Monitor tests."""

import pytest
from app.services.vram_monitor import VRAMMonitor

def test_pressure_level_calculation():
    monitor = VRAMMonitor()
    
    # Green: < 70%
    assert monitor._compute_level(0.65) == "green"
    
    # Yellow: 70% - 85%
    assert monitor._compute_level(0.78) == "yellow"
    
    # Orange: 85% - 93%
    assert monitor._compute_level(0.88) == "orange"
    
    # Red: > 93%
    assert monitor._compute_level(0.95) == "red"

@pytest.mark.asyncio
async def test_callbacks_fired():
    monitor = VRAMMonitor()
    monitor._pynvml_available = True
    monitor._handle = "fake_handle"
    
    # Mock pynvml inside sys.modules for this test
    import sys
    class FakeInfo:
        total = 16000 * (1024**2)
        used = 10000 * (1024**2)
        
    class FakePynvml:
        def nvmlDeviceGetMemoryInfo(self, handle):
            return FakeInfo()
            
    sys.modules['pynvml'] = FakePynvml()
    
    called_data = None
    def mock_callback(data):
        nonlocal called_data
        called_data = data
        
    monitor.on_update(mock_callback)
    
    try:
        await monitor.poll_once()
    finally:
        del sys.modules['pynvml']
    
    assert called_data is not None
    assert called_data["vram_used_mb"] == 10000
    assert called_data["pressure_level"] == "green"

@pytest.mark.asyncio
async def test_initialize_without_pynvml():
    monitor = VRAMMonitor()
    
    # Since pynvml is not installed in the standard test env or we want to test failure:
    import sys
    if 'pynvml' in sys.modules:
        del sys.modules['pynvml']
        
    class FakeModule:
        def __getattr__(self, name):
            raise ImportError("fake error")
            
    sys.modules['pynvml'] = FakeModule()
    
    try:
        result = await monitor.initialize()
        assert result is False
    finally:
        del sys.modules['pynvml']
