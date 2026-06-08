"""Security / compliance audit trail.

Logs structured events to a dedicated ``audit`` logger so an operator
can grep for ``audit.audit`` and see a chronological list of
security-relevant actions: auth failures, config changes, KB
operations, LLM model load/unload, API key access.

Events are written at WARNING level on the ``app.audit`` logger; configure
your log handler to route this logger to a separate file (or send it
to your SIEM) in production. WARNING level ensures security events
are never filtered out by handlers that gate on ``WARNING+``.
The default text/json formatter from ``logging_config`` applies the
same format as the rest of the app.
"""

import logging
import time
from typing import Any

logger = logging.getLogger("app.audit")


def audit(event: str, **fields: Any) -> None:
    """Emit a structured audit log entry.

    ``event`` is a short snake_case tag (e.g. ``"auth.ws_failure"``,
    ``"config.field_changed"``). Extra keyword arguments become
    structured fields in the log message — when the JSON formatter is
    active they appear as top-level keys.

    Example::

        audit("auth.ws_failure", endpoint="/api/v1/solve",
              remote="10.0.0.7", reason="bad_token")
    """
    parts = [f"event={event}", f"ts={time.time():.3f}"]
    for k, v in sorted(fields.items()):
        # Keep the on-disk format readable in text mode by quoting strings
        if isinstance(v, str):
            parts.append(f"{k}={v!r}")
        else:
            parts.append(f"{k}={v}")
    logger.warning(" ".join(parts))
