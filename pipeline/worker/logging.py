"""Worker logging re-exports the shared JSON logging from the faultiq library."""

from faultiq.log import JsonFormatter, configure_logging

__all__ = ["JsonFormatter", "configure_logging"]
