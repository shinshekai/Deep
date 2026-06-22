"""System routes — split into 7 routers. This module re-exports for backward compatibility."""

from app.routers.health import router, settings
from app.routers.config_routes import router as _cr
from app.routers.model_routes import router as _mr
from app.routers.vram import router as _vr
from app.routers.benchmarks import router as _br
from app.routers.data_routes import router as _dr
from app.routers.backup import router as _bk
from app.routers.system_shared import (
    _cache_state,
    _mask_value,
    _metrics_history,
    _rotation_history,
    _ROTATION_HISTORY_MAX,
    CONFIG_ALLOWED_FIELDS,
    URL_FIELDS,
    METRICS_DIR,
    logger,
)
from app.services.secrets import get_secret as secrets_get, set_secret as secrets_set
from app.services.secrets import is_keyring_available as secrets_available
from app.services.secrets import warn_fallback_once as secrets_warn_fallback
