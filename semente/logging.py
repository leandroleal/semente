"""Engine-neutral logging facade.

Re-exports the engine's log functions so domains never import the engine.
Upgrade path: swap these for stdlib ``logging`` adapters if the engine changes.
"""

from agno.utils.log import log_debug, log_error, log_info, log_warning

__all__ = ["log_debug", "log_info", "log_warning", "log_error"]
