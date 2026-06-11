"""Logger compatibility layer for legacy UniAutos.Log framework.

This module provides compatibility wrapper for UniAutos.Log.getLogger()
to allow legacy test cases to use standard Python logging.
"""

import logging
from typing import Optional


class Log:
    """Compatibility wrapper for UniAutos.Log module.

    Legacy pattern:
        from UniAutos import Log
        logger = Log.getLogger("TestName")
        logger.info("message")
        logger.tcStep("step message")

    Converted to:
        from libs.utils.logger_compat import Log
        logger = Log.getLogger("TestName")
        # Uses standard Python logging internally
    """

    # Legacy UniAutos.Log.LogFileDir compatibility
    # Default log directory path (can be overridden by environment)
    LogFileDir = "/var/log/ubs-test"

    @staticmethod
    def getLogger(name: Optional[str] = None) -> logging.Logger:
        """Get logger instance compatible with UniAutos.Log.
        
        Args:
            name: Logger name (optional, defaults to "root")
            
        Returns:
            Python logging.Logger instance with compatibility methods
        
        Example:
            logger = Log.getLogger("Test_Create_UB_Controller_001")
            logger.info("Starting test")
            logger.tcStep("S1: Execute SDK command")
        """
        if name is None:
            name = "root"
        
        logger = logging.getLogger(name)
        
        if not hasattr(logger, "tcStep"):
            logger.tcStep = lambda msg: logger.info(f"[TC_STEP] {msg}")
        
        if not hasattr(logger, "tcSubStep"):
            logger.tcSubStep = lambda msg: logger.info(f"[TC_SUBSTEP] {msg}")
        
        return logger
    
    @staticmethod
    def setLogLevel(level: str) -> None:
        """Set global log level.
        
        Args:
            level: Log level string ("DEBUG", "INFO", "WARNING", "ERROR")
        """
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        
        logging.basicConfig(level=level_map.get(level.upper(), logging.INFO))


class LegacyLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter providing legacy-compatible method names.
    
    Provides methods like tcStep(), tcSubStep() that legacy test cases use.
    """
    
    def tcStep(self, msg: str) -> None:
        """Log test case step (legacy compatibility method)."""
        self.info(f"[TC_STEP] {msg}")
    
    def tcSubStep(self, msg: str) -> None:
        """Log test case sub-step (legacy compatibility method)."""
        self.info(f"[TC_SUBSTEP] {msg}")
    
    def process(self, msg, kwargs):
        """Process logging message (standard LoggerAdapter method)."""
        return msg, kwargs


def get_legacy_logger(name: str) -> LegacyLoggerAdapter:
    """Get logger with legacy-compatible adapter.
    
    Args:
        name: Logger name
        
    Returns:
        LegacyLoggerAdapter instance
    """
    logger = logging.getLogger(name)
    return LegacyLoggerAdapter(logger, {})


# Module-level Log instance for easy import
Log = Log()