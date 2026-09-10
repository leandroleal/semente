"""Engine-neutral logging facade.

Stdlib ``logging`` adapters with the same signatures as the engine's log
functions, so domains and Semente-level code never import the engine. The agno
backend configures its own loggers; everything else logs through here.
"""

from __future__ import annotations

import logging

_logger = logging.getLogger("semente")


def log_debug(msg, center: bool = False, symbol: str = "*", log_level: int = 1, *args, **kwargs):
    _logger.debug(msg)


def log_info(msg, center: bool = False, symbol: str = "*", *args, **kwargs):
    _logger.info(msg)


def log_warning(msg, *args, **kwargs):
    _logger.warning(msg)


def log_error(msg, *args, **kwargs):
    _logger.error(msg)


__all__ = ["log_debug", "log_info", "log_warning", "log_error"]
