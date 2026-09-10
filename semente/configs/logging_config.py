import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional

LOG_DIR = Path.cwd() / "logs"

_ERROR_FORMATTER = logging.Formatter(
    fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def _build_error_file_handler() -> Optional[RotatingFileHandler]:
    """Build the rotating error file handler, or None if the log dir is not writable."""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            filename=LOG_DIR / "errors.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
    except OSError as exc:
        # Log dir not writable (e.g. host-mounted logs/ owned by root from a
        # prior Docker run). Don't crash the app; emit a warning to stderr.
        print(
            f"[logging_config] WARNING: cannot write error log to {LOG_DIR}/errors.log "
            f"({exc}); error file logging disabled.",
            file=sys.stderr,
        )
        return None
    handler.setLevel(logging.ERROR)
    handler.setFormatter(_ERROR_FORMATTER)
    return handler


def setup_logging(config: Any) -> None:
    """Configure the Semente logger (and agno's, when installed).

    - Errors -> /app/logs/errors.log (rotating 5MB x 3) in every environment.
    - Info -> terminal in every environment.
    - Debug -> terminal only when config.DEBUG_MODE is True (dev/staging).
    """
    debug_mode = bool(getattr(config, "DEBUG_MODE", False))
    console_level = logging.DEBUG if debug_mode else logging.INFO

    error_handler = _build_error_file_handler()
    error_path = getattr(error_handler, "baseFilename", None)

    # Semente-level logger (stdlib).
    semente_logger = logging.getLogger("semente")
    semente_logger.setLevel(console_level)
    if not any(isinstance(h, logging.StreamHandler) for h in semente_logger.handlers):
        console = logging.StreamHandler()
        console.setLevel(console_level)
        semente_logger.addHandler(console)
    if error_handler is not None and not any(
        getattr(h, "baseFilename", None) == error_path for h in semente_logger.handlers
    ):
        semente_logger.addHandler(error_handler)

    # Agno's loggers — only when the agno backend is installed (bare must not
    # require agno).
    try:
        from agno.utils.log import agent_logger, team_logger, workflow_logger
    except ImportError:
        return

    for logger in (agent_logger, team_logger, workflow_logger):
        if error_handler is not None and not any(
            getattr(h, "baseFilename", None) == error_path for h in logger.handlers
        ):
            logger.addHandler(error_handler)
        for handler in logger.handlers:
            if isinstance(handler, RotatingFileHandler):
                continue
            handler.setLevel(console_level)
