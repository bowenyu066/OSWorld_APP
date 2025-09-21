"""Main GUI application for OSWorld Annotator Kit."""

import time
import sys
import json
import random
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QPushButton, QTextEdit,
    QSplitter, QMessageBox, QProgressBar, QStatusBar, QComboBox,
    QLineEdit, QGroupBox, QCheckBox, QSpinBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QDesktopServices, QPalette, QColor
from PySide6.QtCore import QUrl

from .models import Task
from .config import config_manager
from .vm_control import VMController
from .task_adapter import TaskRunner
from .evaluator_runner import EvaluatorRunner
from .snapshot import prepare_for_task
from .floating_overlay import FloatingOverlay
from .logging_setup import setup_logging, get_logger

logger = get_logger(__name__)


class TaskExecutionThread(QThread):
    """Thread for executing tasks to avoid blocking the GUI."""
    
    finished = Signal(bool, str)  # success, message
    progress = Signal(str)  # status message
    error_occurred = Signal(str, str)  # operation_name, error_message
    
    def __init__(self, task: Task, run_id: str):
        super().__init__()
        self.task = task
        self.run_id = run_id
        self.vm = VMController()
        self.task_runner = TaskRunner()
        self.should_retry = False
        self.should_skip = False
    
    def set_retry_flag(self):
        """Set flag to retry current operation."""
        self.should_retry = True
    
    def set_skip_flag(self):
        """Set flag to skip current operation."""
        self.should_skip = True
    
    def run(self):
        """Execute the task in a separate thread with retry/skip support."""
        try:
            # Set up status callback for VM operations
            self.vm.set_status_callback(lambda msg: self.progress.emit(msg))
            
            self.progress.emit("Preparing VM (reverting snapshot)...")
            
            # Prepare VM for task with retry support
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    prepare_for_task(self.vm)
                    break
                except Exception as e:
                    if attempt < max_attempts - 1:
                        self.error_occurred.emit("VM Preparation", f"Attempt {attempt + 1} failed: {str(e)}")
                        # Wait for user decision (retry/skip)
                        self.should_retry = False
                        self.should_skip = False
                        while not self.should_retry and not self.should_skip:
                            self.msleep(100)  # Wait 100ms
                        
                        if self.should_skip:
                            raise Exception("VM preparation skipped by user")
                        # Continue with retry
                    else:
                        raise e
            
            self.progress.emit("Preparing task environment...")
            
            # Execute task configuration with retry support
            for attempt in range(max_attempts):
                try:
                    self.task_runner.run_config(self.task, self.vm)
                    break
                except Exception as e:
                    if attempt < max_attempts - 1:
                        self.error_occurred.emit("Task Execution", f"Attempt {attempt + 1} failed: {str(e)}")
                        # Wait for user decision (retry/skip)
                        self.should_retry = False
                        self.should_skip = False
                        while not self.should_retry and not self.should_skip:
                            self.msleep(100)
                        
                        if self.should_skip:
                            self.progress.emit("Task execution skipped by user")
                            break
                        # Continue with retry
                    else:
                        raise e
            
            self.progress.emit("Task environment prepared successfully")
            self.finished.emit(True, "Task started successfully")
            
        except Exception as e:
            error_msg = f"Task execution failed: {str(e)}"
            logger.error(error_msg)
            self.finished.emit(False, error_msg)


class AnnotatorKitGUI(QMainWindow):
    """Main GUI window for the Annotator Kit with enhanced features."""
    
    def __init__(self):
        super().__init__()
        self.current_task: Optional[Task] = None
        self.current_run_id: Optional[str] = None
        self.tasks: List[Task] = []
        self.filtered_tasks: List[Task] = []
        self.current_task_index: int = 0
        self.execution_thread: Optional[TaskExecutionThread] = None
        
        # Create floating overlay
        self.floating_overlay = FloatingOverlay()
        self.floating_overlay.validate_requested.connect(self.validate_task)
        self.floating_overlay.close_requested.connect(self.hide_floating_overlay)
        
        self.init_ui()
        self.apply_modern_styling()
        self.load_tasks()
    
    def init_ui(self):
        """Initialize the user interface with enhanced features."""
        self.setWindowTitle("OSWorld Annotator Kit - Day 3 Enhanced")
        self.setGeometry(100, 100, 1400, 900)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        central_widget.setLayout(QHBoxLayout())
        central_widget.layout().addWidget(splitter)
        
        # Left panel - Task list with filtering
        left_panel = self.create_task_list_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Task details and controls
        right_panel = self.create_task_details_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter proportions
        splitter.setSizes([400, 1000])
        
        # Create enhanced status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Create progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # Add task counter to status bar
        self.task_counter_label = QLabel("No tasks loaded")
        self.status_bar.addPermanentWidget(self.task_counter_label)
        
        self.status_bar.showMessage("Ready - Enhanced OSWorld Annotator Kit")
    
    def create_task_list_panel(self) -> QWidget:
        """Create the left panel with task list and filtering."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Title
        title = QLabel("Tasks")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)
        
        # Filtering section
        filter_group = QGroupBox("Filters")
        filter_layout = QVBoxLayout(filter_group)
        
        # App filter
        app_layout = QHBoxLayout()
        app_layout.addWidget(QLabel("App:"))
        self.app_filter = QComboBox()
        self.app_filter.addItem("All Apps")
        self.app_filter.currentTextChanged.connect(self.apply_filters)
        app_layout.addWidget(self.app_filter)
        filter_layout.addLayout(app_layout)
        
        # Status filter
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Not Started", "Completed", "Failed"])
        self.status_filter.currentTextChanged.connect(self.apply_filters)
        status_layout.addWidget(self.status_filter)
        filter_layout.addLayout(status_layout)
        
        # Search box
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search tasks...")
        self.search_box.textChanged.connect(self.apply_filters)
        search_layout.addWidget(self.search_box)
        filter_layout.addLayout(search_layout)
        
        layout.addWidget(filter_group)
        
        # Task list
        self.task_list = QListWidget()
        self.task_list.itemSelectionChanged.connect(self.on_task_selected)
        layout.addWidget(self.task_list)
        
        # Navigation buttons
        nav_layout = QHBoxLayout()
        
        self.prev_button = QPushButton("◀ Previous")
        self.prev_button.setEnabled(False)
        self.prev_button.clicked.connect(self.previous_task)
        nav_layout.addWidget(self.prev_button)
        
        self.next_button = QPushButton("Next ▶")
        self.next_button.setEnabled(False)
        self.next_button.clicked.connect(self.next_task)
        nav_layout.addWidget(self.next_button)
        
        layout.addLayout(nav_layout)
        
        return panel
    
    def create_task_details_panel(self) -> QWidget:
        """Create the right panel with enhanced task details and controls."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Task instruction (large text)
        self.instruction_label = QLabel("Select a task to view instructions")
        self.instruction_label.setFont(QFont("Arial", 14))
        self.instruction_label.setWordWrap(True)
        self.instruction_label.setStyleSheet("""
            padding: 20px; 
            border: 2px solid #3498db; 
            background-color: #ecf0f1;
            border-radius: 8px;
            color: #2c3e50;
        """)
        self.instruction_label.setMinimumHeight(120)
        layout.addWidget(self.instruction_label)
        
        # Source link
        self.source_label = QLabel("")
        self.source_label.setOpenExternalLinks(True)
        self.source_label.setStyleSheet("padding: 10px; color: #3498db;")
        layout.addWidget(self.source_label)
        
        # Task details
        self.details_text = QTextEdit()
        self.details_text.setMaximumHeight(200)
        self.details_text.setReadOnly(True)
        self.details_text.setStyleSheet("""
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            background-color: #ffffff;
        """)
        layout.addWidget(self.details_text)
        
        # Enhanced control buttons
        button_layout = QVBoxLayout()
        
        # Main action buttons
        main_buttons = QHBoxLayout()
        
        self.start_button = QPushButton("🚀 Start Task")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_task)
        self.start_button.setStyleSheet("""
            QPushButton { 
                background-color: #27ae60; 
                color: white; 
                padding: 12px; 
                font-size: 14px; 
                font-weight: bold;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #2ecc71; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        main_buttons.addWidget(self.start_button)
        
        self.validate_button = QPushButton("✓ Validate")
        self.validate_button.setEnabled(False)
        self.validate_button.clicked.connect(self.validate_task)
        self.validate_button.setStyleSheet("""
            QPushButton { 
                background-color: #3498db; 
                color: white; 
                padding: 12px; 
                font-size: 14px; 
                font-weight: bold;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #5dade2; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        main_buttons.addWidget(self.validate_button)
        
        button_layout.addLayout(main_buttons)
        
        # Error handling buttons (initially hidden)
        self.error_buttons_layout = QHBoxLayout()
        
        self.retry_button = QPushButton("🔄 Retry")
        self.retry_button.setVisible(False)
        self.retry_button.clicked.connect(self.retry_operation)
        self.retry_button.setStyleSheet("""
            QPushButton { 
                background-color: #f39c12; 
                color: white; 
                padding: 10px; 
                font-size: 12px; 
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #e67e22; }
        """)
        self.error_buttons_layout.addWidget(self.retry_button)
        
        self.skip_button = QPushButton("⏭ Skip")
        self.skip_button.setVisible(False)
        self.skip_button.clicked.connect(self.skip_operation)
        self.skip_button.setStyleSheet("""
            QPushButton { 
                background-color: #e74c3c; 
                color: white; 
                padding: 10px; 
                font-size: 12px; 
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        self.error_buttons_layout.addWidget(self.skip_button)
        
        button_layout.addLayout(self.error_buttons_layout)
        layout.addLayout(button_layout)
        
        # Notes section
        notes_group = QGroupBox("Annotator Notes")
        notes_layout = QVBoxLayout(notes_group)
        
        self.notes_text = QTextEdit()
        self.notes_text.setMaximumHeight(100)
        self.notes_text.setPlaceholderText("Add your notes about this task...")
        self.notes_text.setStyleSheet("""
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            background-color: #ffffff;
        """)
        notes_layout.addWidget(self.notes_text)
        
        save_notes_button = QPushButton("💾 Save Notes")
        save_notes_button.clicked.connect(self.save_notes)
        save_notes_button.setStyleSheet("""
            QPushButton { 
                background-color: #9b59b6; 
                color: white; 
                padding: 8px; 
                font-size: 12px; 
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #8e44ad; }
        """)
        notes_layout.addWidget(save_notes_button)
        
        layout.addWidget(notes_group)
        
        # Status text with enhanced styling
        status_group = QGroupBox("Execution Status")
        status_layout = QVBoxLayout(status_group)
        
        self.status_text = QTextEdit()
        self.status_text.setMaximumHeight(150)
        self.status_text.setReadOnly(True)
        self.status_text.setPlaceholderText("Task execution status will appear here...")
        self.status_text.setStyleSheet("""
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            background-color: #f8f9fa;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 11px;
        """)
        status_layout.addWidget(self.status_text)
        
        layout.addWidget(status_group)
        
        return panel
    
    def apply_modern_styling(self):
        """Apply modern styling to the application."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #2c3e50;
            }
            QListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: #ffffff;
                selection-background-color: #3498db;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #ecf0f1;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            QComboBox, QLineEdit {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 6px;
                background-color: #ffffff;
            }
            QComboBox:focus, QLineEdit:focus {
                border-color: #3498db;
            }
        """)
    
    def show_error_buttons(self):
        """Show retry/skip buttons when an error occurs."""
        self.retry_button.setVisible(True)
        self.skip_button.setVisible(True)
    
    def hide_error_buttons(self):
        """Hide retry/skip buttons."""
        self.retry_button.setVisible(False)
        self.skip_button.setVisible(False)
    
    def retry_operation(self):
        """Retry the current operation."""
        if self.execution_thread:
            self.execution_thread.set_retry_flag()
        self.hide_error_buttons()
        self.add_status_message("🔄 Retrying operation...")
    
    def skip_operation(self):
        """Skip the current operation."""
        if self.execution_thread:
            self.execution_thread.set_skip_flag()
        self.hide_error_buttons()
        self.add_status_message("⏭ Skipping operation...")
    
    def on_execution_error(self, operation_name: str, error_message: str):
        """Handle execution errors with retry/skip options."""
        self.add_status_message(f"❌ {operation_name} failed: {error_message}")
        self.show_error_buttons()
        self.status_bar.showMessage(f"Error in {operation_name} - Choose Retry or Skip")
    
    def apply_filters(self):
        """Apply filters to the task list."""
        app_filter = self.app_filter.currentText()
        status_filter = self.status_filter.currentText()
        search_text = self.search_box.text().lower()
        
        self.filtered_tasks = []
        
        for task in self.tasks:
            # App filter
            if app_filter != "All Apps":
                if not task.related_apps or app_filter.lower() not in [app.lower() for app in task.related_apps]:
                    continue
            
            # Search filter
            if search_text:
                if (search_text not in task.id.lower() and 
                    search_text not in task.instruction.lower()):
                    continue
            
            # Status filter (simplified - would need to check actual run results)
            # For now, just include all tasks
            
            self.filtered_tasks.append(task)
        
        self.update_task_list()
        self.update_navigation_buttons()
    
    def update_task_list(self):
        """Update the task list display with filtered tasks."""
        self.task_list.clear()
        
        for task in self.filtered_tasks:
            item = QListWidgetItem(f"{task.id}")
            item.setData(Qt.UserRole, task)
            
            # Add visual indicators
            if task.related_apps:
                item.setText(f"{task.id} [{', '.join(task.related_apps[:2])}]")
            
            self.task_list.addItem(item)
        
        # Update counter
        total_tasks = len(self.tasks)
        filtered_count = len(self.filtered_tasks)
        self.task_counter_label.setText(f"Tasks: {filtered_count}/{total_tasks}")
    
    def update_navigation_buttons(self):
        """Update the state of navigation buttons."""
        has_tasks = len(self.filtered_tasks) > 0
        self.prev_button.setEnabled(has_tasks and self.current_task_index > 0)
        self.next_button.setEnabled(has_tasks and self.current_task_index < len(self.filtered_tasks) - 1)
    
    def previous_task(self):
        """Navigate to the previous task."""
        if self.current_task_index > 0:
            self.current_task_index -= 1
            self.select_task_by_index(self.current_task_index)
    
    def next_task(self):
        """Navigate to the next task."""
        if self.current_task_index < len(self.filtered_tasks) - 1:
            self.current_task_index += 1
            self.select_task_by_index(self.current_task_index)
    
    def select_task_by_index(self, index: int):
        """Select a task by its index in the filtered list."""
        if 0 <= index < len(self.filtered_tasks):
            task = self.filtered_tasks[index]
            
            # Find and select the corresponding item in the list widget
            for i in range(self.task_list.count()):
                item = self.task_list.item(i)
                if item.data(Qt.UserRole) == task:
                    self.task_list.setCurrentItem(item)
                    break
            
            self.update_navigation_buttons()
    
    def save_notes(self):
        """Save notes for the current task."""
        if not self.current_run_id:
            self.show_info("No Active Task", "Please start a task before saving notes.")
            return
        
        notes_content = self.notes_text.toPlainText()
        if not notes_content.strip():
            return
        
        try:
            run_dir = config_manager.get_output_dir() / self.current_run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            
            notes_file = run_dir / "notes.txt"
            with open(notes_file, 'w', encoding='utf-8') as f:
                f.write(f"# Annotator Notes - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Task: {self.current_task.id if self.current_task else 'Unknown'}\n\n")
                f.write(notes_content)
            
            self.add_status_message(f"💾 Notes saved to: {notes_file}")
            self.status_bar.showMessage("Notes saved successfully", 3000)
            
        except Exception as e:
            self.show_error("Save Notes Failed", f"Could not save notes: {str(e)}")
    
    def load_tasks(self):
        """Load tasks from the tasks directory with enhanced filtering setup."""
        tasks_dir = config_manager.get_tasks_dir()
        
        if not tasks_dir.exists():
            self.show_error("Tasks directory not found", f"Directory does not exist: {tasks_dir}")
            return
        
        self.tasks.clear()
        
        # Find all JSON files in tasks directory and subdirectories
        json_files = list(tasks_dir.rglob("*.json"))
        
        if not json_files:
            self.status_bar.showMessage("No task files found in tasks directory")
            return
        
        # Collect all apps for filter
        all_apps = set()
        
        for json_file in json_files:
            try:
                task = Task.parse_file(str(json_file))
                self.tasks.append(task)
                
                # Collect apps for filter
                if task.related_apps:
                    all_apps.update(task.related_apps)
                
            except Exception as e:
                logger.error(f"Failed to load task from {json_file}: {e}")
        
        # Populate app filter
        self.app_filter.clear()
        self.app_filter.addItem("All Apps")
        for app in sorted(all_apps):
            self.app_filter.addItem(app.title())
        
        # Apply initial filters
        self.filtered_tasks = self.tasks.copy()
        self.update_task_list()
        
        self.status_bar.showMessage(f"Loaded {len(self.tasks)} tasks from {len(json_files)} files")
        
        # Select first task if available
        if self.filtered_tasks:
            self.current_task_index = 0
            self.select_task_by_index(0)
    
    def on_task_selected(self):
        """Handle task selection in the list."""
        current_item = self.task_list.currentItem()
        if not current_item:
            return
        
        task = current_item.data(Qt.UserRole)
        self.current_task = task
        
        # Update current task index in filtered list
        try:
            self.current_task_index = self.filtered_tasks.index(task)
        except ValueError:
            self.current_task_index = 0
        
        self.display_task_details(task)
        self.start_button.setEnabled(True)
        self.update_navigation_buttons()
        
        # Load existing notes if available
        self.load_existing_notes()
    
    def display_task_details(self, task: Task):
        """Display task details in the right panel."""
        # Update instruction
        self.instruction_label.setText(task.instruction)
        
        # Update source link
        if task.source:
            self.source_label.setText(f'<a href="{task.source}">📖 Source: {task.source}</a>')
        else:
            self.source_label.setText("")
        
        # Update details
        details = []
        details.append(f"📋 Task ID: {task.id}")
        details.append(f"📸 Snapshot: {task.snapshot or 'N/A'}")
        details.append(f"🔧 Related Apps: {', '.join(task.related_apps) if task.related_apps else 'N/A'}")
        details.append(f"⚙️ Config Actions: {len(task.config)}")
        
        if task.config:
            details.append("\n🔄 Configuration Actions:")
            for i, action in enumerate(task.config, 1):
                params_str = str(action.parameters)
                if len(params_str) > 100:
                    params_str = params_str[:97] + "..."
                details.append(f"  {i}. {action.type}: {params_str}")
        
        # Add evaluator info
        if hasattr(task, 'evaluator') and task.evaluator:
            evaluator = task.evaluator
            details.append(f"\n✅ Evaluator Function: {evaluator.func_name}")
            if hasattr(evaluator, 'postconfig') and evaluator.postconfig:
                details.append(f"📋 Post-config Actions: {len(evaluator.postconfig)}")
        
        self.details_text.setPlainText("\n".join(details))
    
    def load_existing_notes(self):
        """Load existing notes for the current task if available."""
        if not self.current_task:
            return
        
        # Try to find existing notes from previous runs
        output_dir = config_manager.get_output_dir()
        task_id = self.current_task.id
        
        # Look for the most recent run directory for this task
        matching_dirs = []
        for run_dir in output_dir.glob(f"*_{task_id}"):
            if run_dir.is_dir():
                matching_dirs.append(run_dir)
        
        if matching_dirs:
            # Get the most recent one
            latest_dir = max(matching_dirs, key=lambda d: d.stat().st_mtime)
            notes_file = latest_dir / "notes.txt"
            
            if notes_file.exists():
                try:
                    with open(notes_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Remove header lines and load content
                    lines = content.split('\n')
                    content_lines = []
                    for line in lines:
                        if not line.startswith('#'):
                            content_lines.append(line)
                    
                    if content_lines:
                        self.notes_text.setPlainText('\n'.join(content_lines).strip())
                        self.add_status_message(f"📝 Loaded existing notes from: {notes_file}")
                except Exception as e:
                    logger.warning(f"Could not load existing notes: {e}")
        
        # Clear notes if no existing ones found
        if not matching_dirs:
            self.notes_text.clear()
    
    def start_task(self):
        """Start the selected task with enhanced error handling."""
        if not self.current_task:
            return
        
        # Generate run ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_run_id = f"{timestamp}_{self.current_task.id}"
        
        # Create run directory
        run_dir = config_manager.get_output_dir() / self.current_run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Save task JSON to run directory
        task_file = run_dir / "task.json"
        with open(task_file, 'w', encoding='utf-8') as f:
            json.dump(self.current_task.model_dump(), f, indent=2, ensure_ascii=False)
        
        # Disable buttons during execution
        self.start_button.setEnabled(False)
        self.validate_button.setEnabled(False)
        self.hide_error_buttons()
        
        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        
        # Clear status
        self.status_text.clear()
        self.add_status_message("🚀 Starting task execution...")
        
        # Start execution in separate thread
        self.execution_thread = TaskExecutionThread(self.current_task, self.current_run_id)
        self.execution_thread.progress.connect(self.add_status_message)
        self.execution_thread.finished.connect(self.on_task_execution_finished)
        self.execution_thread.error_occurred.connect(self.on_execution_error)
        self.execution_thread.start()
    
    def on_task_execution_finished(self, success: bool, message: str):
        """Handle task execution completion with enhanced feedback."""
        # Hide progress bar and error buttons
        self.progress_bar.setVisible(False)
        self.hide_error_buttons()
        
        # Re-enable buttons
        self.start_button.setEnabled(True)
        
        # Show result
        if success:
            self.add_status_message(f"✅ {message}")
            self.status_bar.showMessage("Task execution completed successfully")
            self.validate_button.setEnabled(True)
            
            # Show floating overlay if VM is in fullscreen mode
            if config_manager.config.start_fullscreen:
                self.show_floating_overlay()
        else:
            self.add_status_message(f"❌ {message}")
            self.status_bar.showMessage("Task execution failed")
            self.show_error("Task Execution Failed", message)
    
    def validate_task(self):
        """Validate the completed task with enhanced error handling."""
        if not self.current_task or not self.current_run_id:
            return
        
        # Disable validate button during validation
        self.validate_button.setEnabled(False)
        self.floating_overlay.enable_validate(False)
        
        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.add_status_message("🔍 Starting task validation...")
        self.update_floating_overlay_status("Validating...")
        
        try:
            # Create VM controller and evaluator runner
            vm = VMController()
            evaluator_runner = EvaluatorRunner()
            
            # Set up status callback
            vm.set_status_callback(lambda msg: self.add_status_message(msg))
            
            # Prepare guest environment
            self.add_status_message("🔧 Preparing guest environment for evaluation...")
            evaluator_runner.prepare_guest_env(vm)
            
            # Get run directory
            run_dir = config_manager.get_output_dir() / self.current_run_id
            
            # Run evaluation
            self.add_status_message("⚡ Running evaluation in guest VM...")
            result = evaluator_runner.run(self.current_task, vm, host_runs_dir=str(run_dir))
            
            # Save evaluation result
            eval_result_file = run_dir / "eval_result.json"
            with open(eval_result_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            # Save current notes
            if self.notes_text.toPlainText().strip():
                self.save_notes()
            
            # Show result
            passed = result.get('passed', False)
            details = result.get('details', {})
            
            if passed:
                self.add_status_message("✅ Task validation PASSED")
                self.status_bar.showMessage("Task validation completed - PASSED")
                self.update_floating_overlay_status("✅ PASSED")
                
                # Enhanced success message
                success_msg = "🎉 The task was completed successfully!"
                if details.get('message'):
                    success_msg += f"\n\nDetails: {details['message']}"
                
                self.show_validation_result("Validation Passed", success_msg, True)
            else:
                error_msg = details.get('error', details.get('message', 'Unknown validation error'))
                
                # Truncate very long error messages for display
                display_error = error_msg
                if len(display_error) > 200:
                    display_error = display_error[:197] + "..."
                
                self.add_status_message(f"❌ Task validation FAILED: {display_error}")
                self.status_bar.showMessage("Task validation completed - FAILED")
                self.update_floating_overlay_status("❌ FAILED")
                
                # Enhanced failure message with better formatting
                failure_msg = "The task validation failed.\n\n"
                failure_msg += f"Error Details:\n{error_msg}\n\n"
                
                if details.get('evaluator_type'):
                    failure_msg += f"Evaluator: {details['evaluator_type']}\n"
                
                # Add helpful context
                failure_msg += "\nPossible causes:\n"
                failure_msg += "• Task requirements not fully completed\n"
                failure_msg += "• VM environment issues\n"
                failure_msg += "• Network connectivity problems\n"
                failure_msg += "• Application state not as expected"
                
                self.show_validation_result("Validation Failed", failure_msg, False)
            
            self.add_status_message(f"💾 Results saved to: {run_dir}")
            
        except Exception as e:
            error_msg = f"Validation error: {str(e)}"
            logger.error(error_msg)
            self.add_status_message(f"❌ {error_msg}")
            self.status_bar.showMessage("Task validation failed")
            self.show_error("Validation Error", error_msg)
        
        finally:
            # Hide progress bar and re-enable button
            self.progress_bar.setVisible(False)
            self.validate_button.setEnabled(True)
            self.floating_overlay.enable_validate(True)
    
    def add_status_message(self, message: str):
        """Add a status message to the status text area with enhanced formatting."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.status_text.append(formatted_message)
        
        # Auto-scroll to bottom
        scrollbar = self.status_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        logger.info(message)
    
    def show_error(self, title: str, message: str):
        """Show an error message dialog with enhanced styling."""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #f8d7da;
                border: 2px solid #e74c3c;
            }
            QMessageBox QPushButton {
                background-color: #e74c3c;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
        """)
        msg_box.exec()
    
    def show_info(self, title: str, message: str):
        """Show an info message dialog with enhanced styling."""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #d1ecf1;
                border: 2px solid #3498db;
            }
            QMessageBox QPushButton {
                background-color: #3498db;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
        """)
        msg_box.exec()
    
    def show_validation_result(self, title: str, message: str, passed: bool):
        """Show validation result with enhanced styling and animations."""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        
        if passed:
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #d4edda;
                    border: 3px solid #27ae60;
                    border-radius: 8px;
                }
                QMessageBox QPushButton {
                    background-color: #27ae60;
                    color: white;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                }
                QMessageBox QPushButton:hover {
                    background-color: #2ecc71;
                }
            """)
        else:
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #f8d7da;
                    border: 3px solid #e74c3c;
                    border-radius: 8px;
                }
                QMessageBox QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                }
                QMessageBox QPushButton:hover {
                    background-color: #c0392b;
                }
            """)
        
        msg_box.exec()
    
    def show_floating_overlay(self):
        """Show the floating overlay window with enhanced features."""
        if self.current_task:
            self.floating_overlay.set_task(self.current_task)
            self.floating_overlay.enable_validate(self.validate_button.isEnabled())
            self.floating_overlay.show_overlay()
            self.add_status_message("🔄 Floating overlay shown for fullscreen VM")
    
    def hide_floating_overlay(self):
        """Hide the floating overlay window."""
        self.floating_overlay.hide_overlay()
        self.add_status_message("🔄 Floating overlay hidden")
    
    def update_floating_overlay_status(self, status: str):
        """Update the floating overlay status."""
        if self.floating_overlay.isVisible():
            self.floating_overlay.set_status(status)


def main():
    """Main entry point for the application."""
    # Setup logging
    setup_logging("INFO")
    
    # Create application
    app = QApplication(sys.argv)
    
    # Create and show main window
    window = AnnotatorKitGUI()
    window.show()
    
    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
