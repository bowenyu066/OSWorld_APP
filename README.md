# OSWorld Annotator Kit

A GUI application for human annotators to perform OSWorld benchmark tasks in VMware virtual machines.

## Local Development

### Prerequisites
- Python 3.10+
- VMware Workstation Pro or Player with vmrun
- Windows operating system

### Setup
1. Install dependencies:
   ```bash
   pip install -e .
   ```

2. Configure the application by editing `config.yaml`

3. Start the application:
   ```bash
   python -m app.gui
   ```

## Directory Structure
```
annotator-kit/
  app/                    # Main application code
    __init__.py
    gui.py               # PySide6 GUI interface
    config.py            # Configuration management
    vm_control.py        # VMware control via vmrun
    task_adapter.py      # Task execution adapter
    evaluator_runner.py  # Evaluation runner
    snapshot.py          # VM snapshot management
    logging_setup.py     # Logging configuration
    models.py            # Pydantic data models
  scripts/               # PowerShell scripts for guest execution
    run_config_guest.ps1
    eval_guest.ps1
    # Other minimal test scripts for guest execution
  tasks/
    samples/             # OSWorld example JSON files
  runs/                  # Task execution results
  assets/                # Application assets
    icon.ico
```

## Usage
1. Launch the application
2. Select a task from the list
3. Click "Start Task" to launch VM and execute configuration
4. Perform the task in the full-screen VM
5. Click "Validate" to check if the task was completed correctly
