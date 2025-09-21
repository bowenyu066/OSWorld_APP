"""Main GUI application for OSWorld Annotator Kit."""

import time
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QPushButton, QTextEdit,
    QSplitter, QMessageBox, QProgressBar, QStatusBar
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QDesktopServices
from PySide6.QtCore import QUrl

from .models import Task
from .config import config_manager
from .vm_control import VMController
from .task_adapter import TaskRunner
from .evaluator_runner import EvaluatorRunner
from .snapshot import prepare_for_task
from .logging_setup import setup_logging, get_logger

logger = get_logger(__name__)


class TaskExecutionThread(QThread):
    """Thread for executing tasks to avoid blocking the GUI."""
    
    finished = Signal(bool, str)  # success, message
    progress = Signal(str)  # status message
    
    def __init__(self, task: Task, run_id: str):
        super().__init__()
        self.task = task
        self.run_id = run_id
        self.vm = VMController()
        self.task_runner = TaskRunner()
    
    def run(self):
        """Execute the task in a separate thread."""
        try:
            self.progress.emit("Preparing VM (reverting snapshot)...")
            
            # Prepare VM for task
            prepare_for_task(self.vm, config_manager.config.snapshot_name)

            self.progress.emit("Waiting for system to get ready...")

            time.sleep(40) # Wait for VM to fully start before running anything; TODO: make a progress bar
            
            self.progress.emit("Executing task configuration...")
            
            # Execute task configuration
            self.task_runner.run_config(self.task, self.vm)
            
            self.progress.emit("Task execution completed")
            self.finished.emit(True, "Task started successfully")
            
        except Exception as e:
            error_msg = f"Task execution failed: {str(e)}"
            logger.error(error_msg)
            self.finished.emit(False, error_msg)


class AnnotatorKitGUI(QMainWindow):
    """Main GUI window for the Annotator Kit."""
    
    def __init__(self):
        super().__init__()
        self.current_task: Optional[Task] = None
        self.current_run_id: Optional[str] = None
        self.tasks: List[Task] = []
        self.execution_thread: Optional[TaskExecutionThread] = None
        
        self.init_ui()
        self.load_tasks()
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("OSWorld Annotator Kit")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        central_widget.setLayout(QHBoxLayout())
        central_widget.layout().addWidget(splitter)
        
        # Left panel - Task list
        left_panel = self.create_task_list_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Task details and controls
        right_panel = self.create_task_details_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter proportions
        splitter.setSizes([300, 900])
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Create progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        self.status_bar.showMessage("Ready")
    
    def create_task_list_panel(self) -> QWidget:
        """Create the left panel with task list."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Title
        title = QLabel("Tasks")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title)
        
        # Task list
        self.task_list = QListWidget()
        self.task_list.itemSelectionChanged.connect(self.on_task_selected)
        layout.addWidget(self.task_list)
        
        return panel
    
    def create_task_details_panel(self) -> QWidget:
        """Create the right panel with task details and controls."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Task instruction (large text)
        self.instruction_label = QLabel("Select a task to view instructions")
        self.instruction_label.setFont(QFont("Arial", 14))
        self.instruction_label.setWordWrap(True)
        self.instruction_label.setStyleSheet("padding: 20px; border: 1px solid #ccc; background-color: #f9f9f9;")
        self.instruction_label.setMinimumHeight(100)
        layout.addWidget(self.instruction_label)
        
        # Source link
        self.source_label = QLabel("")
        self.source_label.setOpenExternalLinks(True)
        self.source_label.setStyleSheet("padding: 10px;")
        layout.addWidget(self.source_label)
        
        # Task details
        self.details_text = QTextEdit()
        self.details_text.setMaximumHeight(200)
        self.details_text.setReadOnly(True)
        layout.addWidget(self.details_text)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Start Task")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_task)
        self.start_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 10px; font-size: 14px; }")
        button_layout.addWidget(self.start_button)
        
        self.validate_button = QPushButton("Validate")
        self.validate_button.setEnabled(False)  # Enabled after task execution
        self.validate_button.clicked.connect(self.validate_task)
        self.validate_button.setStyleSheet("QPushButton { background-color: #2196F3; color: white; padding: 10px; font-size: 14px; }")
        button_layout.addWidget(self.validate_button)
        
        layout.addLayout(button_layout)
        
        # Status text
        self.status_text = QTextEdit()
        self.status_text.setMaximumHeight(150)
        self.status_text.setReadOnly(True)
        self.status_text.setPlaceholderText("Task execution status will appear here...")
        layout.addWidget(self.status_text)
        
        return panel
    
    def load_tasks(self):
        """Load tasks from the tasks directory."""
        tasks_dir = config_manager.get_tasks_dir()
        
        if not tasks_dir.exists():
            self.show_error("Tasks directory not found", f"Directory does not exist: {tasks_dir}")
            return
        
        self.tasks.clear()
        self.task_list.clear()
        
        # Find all JSON files in tasks directory
        json_files = list(tasks_dir.glob("*.json"))
        
        if not json_files:
            self.status_bar.showMessage("No task files found in tasks directory")
            return
        
        for json_file in json_files:
            try:
                task = Task.parse_file(str(json_file))
                self.tasks.append(task)
                
                # Add to list widget
                item = QListWidgetItem(task.id)
                item.setData(Qt.UserRole, task)
                self.task_list.addItem(item)
                
            except Exception as e:
                logger.error(f"Failed to load task from {json_file}: {e}")
        
        self.status_bar.showMessage(f"Loaded {len(self.tasks)} tasks")
    
    def on_task_selected(self):
        """Handle task selection in the list."""
        current_item = self.task_list.currentItem()
        if not current_item:
            return
        
        self.current_task = current_item.data(Qt.UserRole)
        self.display_task_details(self.current_task)
        self.start_button.setEnabled(True)
    
    def display_task_details(self, task: Task):
        """Display task details in the right panel."""
        # Update instruction
        self.instruction_label.setText(task.instruction)
        
        # Update source link
        if task.source:
            self.source_label.setText(f'<a href="{task.source}">Source: {task.source}</a>')
        else:
            self.source_label.setText("")
        
        # Update details
        details = []
        details.append(f"Task ID: {task.id}")
        details.append(f"Snapshot: {task.snapshot or 'N/A'}")
        details.append(f"Related Apps: {', '.join(task.related_apps) if task.related_apps else 'N/A'}")
        details.append(f"Config Actions: {len(task.config)}")
        
        if task.config:
            details.append("\nConfiguration Actions:")
            for i, action in enumerate(task.config, 1):
                details.append(f"  {i}. {action.type}: {action.parameters}")
        
        self.details_text.setPlainText("\n".join(details))
    
    def start_task(self):
        """Start the selected task."""
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
        
        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        
        # Clear status
        self.status_text.clear()
        self.add_status_message("Starting task execution...")
        
        # Start execution in separate thread
        self.execution_thread = TaskExecutionThread(self.current_task, self.current_run_id)
        self.execution_thread.progress.connect(self.add_status_message)
        self.execution_thread.finished.connect(self.on_task_execution_finished)
        self.execution_thread.start()
    
    def on_task_execution_finished(self, success: bool, message: str):
        """Handle task execution completion."""
        # Hide progress bar
        self.progress_bar.setVisible(False)
        
        # Re-enable buttons
        self.start_button.setEnabled(True)
        
        # Show result
        if success:
            self.add_status_message(f"✓ {message}")
            self.status_bar.showMessage("Task execution completed successfully")
            # Enable validate button for Day 2
            self.validate_button.setEnabled(True)
        else:
            self.add_status_message(f"✗ {message}")
            self.status_bar.showMessage("Task execution failed")
            self.show_error("Task Execution Failed", message)
    
    def validate_task(self):
        """Validate the completed task (Day 2 implementation)."""
        if not self.current_task or not self.current_run_id:
            return
        
        # Disable validate button during validation
        self.validate_button.setEnabled(False)
        
        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.add_status_message("Starting task validation...")
        
        try:
            # Create VM controller and evaluator runner
            vm = VMController()
            evaluator_runner = EvaluatorRunner()
            
            # Prepare guest environment
            self.add_status_message("Preparing guest environment for evaluation...")
            evaluator_runner.prepare_guest_env(vm)
            
            # Get run directory
            run_dir = config_manager.get_output_dir() / self.current_run_id
            
            # Run evaluation
            self.add_status_message("Running evaluation in guest VM...")
            result = evaluator_runner.run(self.current_task, vm, host_runs_dir=str(run_dir))
            
            # Save evaluation result
            eval_result_file = run_dir / "eval_result.json"
            with open(eval_result_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            # Create notes.txt placeholder
            notes_file = run_dir / "notes.txt"
            if not notes_file.exists():
                with open(notes_file, 'w', encoding='utf-8') as f:
                    f.write("# Annotator Notes\n")
                    f.write("# Add your notes about this task execution here\n")
            
            # Show result
            passed = result.get('passed', False)
            if passed:
                self.add_status_message("✓ Task validation PASSED")
                self.status_bar.showMessage("Task validation completed - PASSED")
                self.show_validation_result("Validation Passed", "The task was completed successfully!", True)
            else:
                details = result.get('details', {})
                error_msg = details.get('error', 'Unknown validation error')
                self.add_status_message(f"✗ Task validation FAILED: {error_msg}")
                self.status_bar.showMessage("Task validation completed - FAILED")
                self.show_validation_result("Validation Failed", f"The task validation failed:\n\n{error_msg}", False)
            
            self.add_status_message(f"Results saved to: {run_dir}")
            
        except Exception as e:
            error_msg = f"Validation error: {str(e)}"
            logger.error(error_msg)
            self.add_status_message(f"✗ {error_msg}")
            self.status_bar.showMessage("Task validation failed")
            self.show_error("Validation Error", error_msg)
        
        finally:
            # Hide progress bar and re-enable button
            self.progress_bar.setVisible(False)
            self.validate_button.setEnabled(True)
    
    def add_status_message(self, message: str):
        """Add a status message to the status text area."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.status_text.append(formatted_message)
        logger.info(message)
    
    def show_error(self, title: str, message: str):
        """Show an error message dialog."""
        QMessageBox.critical(self, title, message)
    
    def show_info(self, title: str, message: str):
        """Show an info message dialog."""
        QMessageBox.information(self, title, message)
    
    def show_validation_result(self, title: str, message: str, passed: bool):
        """Show validation result with appropriate styling."""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        
        if passed:
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setStyleSheet("QMessageBox { background-color: #d4edda; }")
        else:
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setStyleSheet("QMessageBox { background-color: #f8d7da; }")
        
        msg_box.exec()


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
