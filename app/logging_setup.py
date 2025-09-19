"""Logging configuration for the Annotator Kit."""

import logging
import sys
from pathlib import Path
from rich.logging import RichHandler
from rich.console import Console


def setup_logging(level: str = "INFO", log_file: str = None) -> None:
    """Setup logging configuration with Rich handler."""
    
    # Create console for Rich handler
    console = Console()
    
    # Create Rich handler with custom formatting
    handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        markup=True,
        show_time=True,
        show_path=False
    )
    
    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,  # Changed from INFO to DEBUG for troubleshooting
        format="%(message)s",
        handlers=[handler]
    )
    
    # Add file handler if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setFormatter(
            logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        )
        logging.getLogger().addHandler(file_handler)
    
    # Set specific logger levels
    logging.getLogger("PySide6").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)
