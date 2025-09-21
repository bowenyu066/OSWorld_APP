"""Enhanced floating overlay window for task controls when VM is fullscreen."""

import sys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QFrame, QApplication
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread
from PySide6.QtGui import QFont, QPalette, QColor
from typing import Optional

from .models import Task
from .logging_setup import get_logger

logger = get_logger(__name__)

# Windows-specific imports for enhanced always-on-top functionality
if sys.platform == "win32":
    try:
        import ctypes
        from ctypes import wintypes
        WINDOWS_AVAILABLE = True
    except ImportError:
        WINDOWS_AVAILABLE = False
else:
    WINDOWS_AVAILABLE = False


class FloatingOverlay(QWidget):
    """Small floating overlay window that stays on top of fullscreen VM."""
    
    # Signals
    validate_requested = Signal()
    close_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_task: Optional[Task] = None
        self.stay_on_top_timer = QTimer()
        self.stay_on_top_timer.timeout.connect(self._ensure_on_top)
        self.init_ui()
        self.setup_window_properties()
    
    def init_ui(self):
        """Initialize the overlay UI."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # Title bar with close button
        title_layout = QHBoxLayout()
        
        title_label = QLabel("Task Control")
        title_label.setFont(QFont("Arial", 10, QFont.Bold))
        title_label.setStyleSheet("color: white;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # Close button
        close_btn = QPushButton("×")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff5555;
                color: white;
                border: none;
                border-radius: 10px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #ff7777;
            }
        """)
        close_btn.clicked.connect(self.close_requested.emit)
        title_layout.addWidget(close_btn)
        
        layout.addLayout(title_layout)
        
        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("color: #666666;")
        layout.addWidget(line)
        
        # Task instruction (compact)
        self.instruction_label = QLabel("No task selected")
        self.instruction_label.setFont(QFont("Arial", 9))
        self.instruction_label.setWordWrap(True)
        self.instruction_label.setStyleSheet("""
            color: white;
            background-color: rgba(0, 0, 0, 0.3);
            padding: 8px;
            border-radius: 4px;
        """)
        self.instruction_label.setMaximumHeight(80)
        layout.addWidget(self.instruction_label)
        
        # Task ID label
        self.task_id_label = QLabel("")
        self.task_id_label.setFont(QFont("Arial", 8))
        self.task_id_label.setStyleSheet("color: #cccccc;")
        layout.addWidget(self.task_id_label)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        # Validate button
        self.validate_btn = QPushButton("Validate")
        self.validate_btn.setEnabled(False)
        self.validate_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #666666;
                color: #999999;
            }
        """)
        self.validate_btn.clicked.connect(self.validate_requested.emit)
        button_layout.addWidget(self.validate_btn)
        
        # Status indicator
        self.status_label = QLabel("Ready")
        self.status_label.setFont(QFont("Arial", 8))
        self.status_label.setStyleSheet("color: #cccccc;")
        button_layout.addWidget(self.status_label)
        
        layout.addLayout(button_layout)
        
        # Make the layout compact
        layout.addStretch()
    
    def setup_window_properties(self):
        """Setup window properties for enhanced floating overlay."""
        # Enhanced window flags for maximum always-on-top behavior
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint | 
            Qt.Tool |
            Qt.WindowDoesNotAcceptFocus  # Prevents stealing focus from VM
        )
        
        # Set window size (slightly larger for better visibility)
        self.setFixedSize(320, 220)
        
        # Set window position (top-right corner with more margin)
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - self.width() - 30, 30)
        
        # Enhanced window style with better visibility
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(35, 35, 35, 0.98);
                border: 3px solid #4CAF50;
                border-radius: 12px;
            }
        """)
        
        # Slightly more opaque for better visibility
        self.setWindowOpacity(0.95)
        
        # Enable mouse tracking for dragging
        self.setMouseTracking(True)
        self.drag_position = None
        
        # Apply Windows-specific always-on-top enhancements
        if WINDOWS_AVAILABLE:
            self._apply_windows_enhancements()
    
    def set_task(self, task: Task):
        """Set the current task and update display."""
        self.current_task = task
        
        if task:
            # Truncate long instructions
            instruction = task.instruction
            if len(instruction) > 150:
                instruction = instruction[:147] + "..."
            
            self.instruction_label.setText(instruction)
            self.task_id_label.setText(f"Task: {task.id}")
        else:
            self.instruction_label.setText("No task selected")
            self.task_id_label.setText("")
    
    def enable_validate(self, enabled: bool = True):
        """Enable or disable the validate button."""
        self.validate_btn.setEnabled(enabled)
    
    def set_status(self, status: str):
        """Set the status text."""
        self.status_label.setText(status)
        
        # Auto-hide status after 3 seconds if it's not "Ready"
        if status != "Ready":
            QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
    
    def mousePressEvent(self, event):
        """Handle mouse press for window dragging."""
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for window dragging."""
        if event.buttons() == Qt.LeftButton and self.drag_position is not None:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release for window dragging."""
        self.drag_position = None
    
    def _apply_windows_enhancements(self):
        """Apply Windows-specific enhancements for always-on-top behavior."""
        try:
            # Get window handle
            hwnd = int(self.winId())
            
            # Windows constants
            HWND_TOPMOST = -1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            
            # Set window to topmost
            ctypes.windll.user32.SetWindowPos(
                hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
            )
            
            logger.debug("Applied Windows-specific always-on-top enhancements")
        except Exception as e:
            logger.warning(f"Could not apply Windows enhancements: {e}")
    
    def _ensure_on_top(self):
        """Ensure the window stays on top (called periodically)."""
        if self.isVisible():
            self.raise_()
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.show()  # Re-show to apply flags
            
            # Apply Windows-specific topmost setting if available
            if WINDOWS_AVAILABLE:
                try:
                    hwnd = int(self.winId())
                    HWND_TOPMOST = -1
                    SWP_NOMOVE = 0x0002
                    SWP_NOSIZE = 0x0001
                    SWP_NOACTIVATE = 0x0010
                    
                    ctypes.windll.user32.SetWindowPos(
                        hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
                    )
                except Exception as e:
                    logger.debug(f"Windows topmost enforcement failed: {e}")
    
    def show_overlay(self):
        """Show the overlay window with enhanced always-on-top behavior."""
        self.show()
        self.raise_()
        
        # Don't activate window to avoid stealing focus from VM
        # self.activateWindow()
        
        # Apply Windows-specific enhancements
        if WINDOWS_AVAILABLE:
            self._apply_windows_enhancements()
        
        # Start periodic enforcement of always-on-top
        self.stay_on_top_timer.start(2000)  # Check every 2 seconds
        
        logger.info("Enhanced floating overlay window shown with always-on-top enforcement")
    
    def hide_overlay(self):
        """Hide the overlay window."""
        # Stop the always-on-top timer
        self.stay_on_top_timer.stop()
        
        self.hide()
        logger.info("Floating overlay window hidden")
    
    def closeEvent(self, event):
        """Handle window close event."""
        self.stay_on_top_timer.stop()
        self.close_requested.emit()
        event.accept()
