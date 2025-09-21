"""Test script for floating overlay functionality."""

import sys
import time
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import QApplication
from app.floating_overlay import FloatingOverlay
from app.models import Task
from app.logging_setup import setup_logging, get_logger

def test_floating_overlay():
    """Test the floating overlay window."""
    # Setup logging
    setup_logging("INFO")
    logger = get_logger(__name__)
    
    logger.info("=== Testing Floating Overlay Window ===")
    
    # Create QApplication
    app = QApplication(sys.argv)
    
    # Create test task
    test_task = Task(
        id="test_overlay",
        instruction="This is a test task instruction to verify that the floating overlay window displays task information correctly and allows validation.",
        source="test://example.com",
        snapshot="test_snapshot",
        related_apps=["chrome"],
        config=[]
    )
    
    # Create floating overlay
    overlay = FloatingOverlay()
    
    # Test setting task
    logger.info("Setting test task...")
    overlay.set_task(test_task)
    
    # Test enabling validate button
    logger.info("Enabling validate button...")
    overlay.enable_validate(True)
    
    # Test status updates
    logger.info("Testing status updates...")
    overlay.set_status("Testing...")
    
    # Show overlay
    logger.info("Showing floating overlay...")
    overlay.show_overlay()
    
    # Connect signals for testing
    def on_validate():
        logger.info("Validate button clicked!")
        overlay.set_status("Validating...")
        # Simulate validation process
        app.processEvents()
        time.sleep(1)
        overlay.set_status("PASSED")
    
    def on_close():
        logger.info("Close button clicked!")
        overlay.hide_overlay()
        app.quit()
    
    overlay.validate_requested.connect(on_validate)
    overlay.close_requested.connect(on_close)
    
    logger.info("Floating overlay test window shown. Click validate to test, or close to exit.")
    logger.info("The overlay should be draggable and stay on top of other windows.")
    
    # Run the application
    return app.exec()

if __name__ == "__main__":
    test_floating_overlay()
