# OSWorld Annotator Kit - Quick Start Guide

## Overview

The OSWorld Annotator Kit is a comprehensive tool for executing and evaluating OSWorld tasks in VMware virtual machines. This Day 3 Enhanced Edition includes robust error handling, comprehensive action type support, and an improved user interface.

## System Requirements

- **Operating System**: Windows 10/11 (64-bit)
- **VMware**: VMware Workstation Pro 15+ or VMware Player 15+
- **Memory**: 8GB RAM minimum (16GB recommended)
- **Storage**: 2GB free space for the application and logs
- **Network**: Internet connection for downloading task files (optional)

## Installation

### Option 1: Standalone Executable (Recommended)

1. Download `AnnotatorKit.exe` from the distribution package
2. Extract to a folder of your choice (e.g., `C:\OSWorld_Annotator`)
3. Ensure VMware Workstation is installed and running
4. Run `AnnotatorKit.exe` or use the provided `run_annotator.bat`

### Option 2: From Source

1. Clone or download the source code
2. Install Python 3.8+ with required packages:
   ```bash
   pip install PySide6 pydantic requests rich
   ```
3. Run the application:
   ```bash
   python app/gui.py
   ```

## Initial Setup

### 1. Configure VMware Settings

1. **Create or prepare your VM**:
   - Install Windows 10/11 in VMware
   - Install required applications (Chrome, Office, etc.)
   - Create a snapshot named "clean" for task execution

2. **Update configuration** (if needed):
   - Edit `config.yaml` to point to your VM file
   - Ensure guest credentials are correct
   - Verify VMware paths are accurate

### 2. Prepare Task Files

1. **Task Directory Structure**:
   ```
   tasks/
   ├── samples/          # Sample tasks included
   │   ├── chrome_*.json
   │   ├── notepad_*.json
   │   └── ...
   └── custom/           # Your custom tasks
   ```

2. **Task Format**: Tasks are JSON files following OSWorld format with:
   - `id`: Unique task identifier
   - `instruction`: Human-readable task description
   - `config`: Array of actions to execute
   - `evaluator`: Validation configuration

## Getting Started

### Step 1: Launch the Application

1. **Start AnnotatorKit**:
   - Double-click `AnnotatorKit.exe`
   - Or run `run_annotator.bat` for console output

2. **Main Interface Overview**:
   - **Left Panel**: Task list with filtering options
   - **Right Panel**: Task details, controls, and status
   - **Status Bar**: Progress and task counters

### Step 2: Load and Filter Tasks

1. **Task Loading**:
   - Tasks are automatically loaded from the `tasks/` directory
   - Use filters to narrow down tasks:
     - **App Filter**: Filter by application (Chrome, Office, etc.)
     - **Status Filter**: Filter by completion status
     - **Search**: Text search in task ID and instructions

2. **Navigation**:
   - Use **Previous/Next** buttons for sequential workflow
   - Click tasks in the list for direct selection

### Step 3: Execute a Task

1. **Select a Task**:
   - Click on a task in the filtered list
   - Review the instruction and configuration details

2. **Start Execution**:
   - Click **🚀 Start Task**
   - The system will:
     - Revert VM to "clean" snapshot
     - Execute configuration actions
     - Prepare the task environment

3. **Monitor Progress**:
   - Watch status updates in the execution log
   - Progress bar shows current operation
   - VM will start in fullscreen mode (if configured)

### Step 4: Complete the Task

1. **Perform Manual Steps**:
   - Switch to the VM (fullscreen mode)
   - Follow the task instructions
   - Complete the required actions

2. **Use Floating Overlay** (if available):
   - Small overlay window for quick validation
   - Stays on top during VM interaction

### Step 5: Validate Results

1. **Click Validate**:
   - Returns to main application
   - Click **✓ Validate** button
   - System runs automated evaluation

2. **Review Results**:
   - ✅ **PASSED**: Task completed successfully
   - ❌ **FAILED**: Task validation failed
   - Detailed results saved to `runs/` directory

### Step 6: Add Notes and Continue

1. **Add Annotations**:
   - Use the **Annotator Notes** section
   - Document observations, issues, or insights
   - Click **💾 Save Notes** to persist

2. **Move to Next Task**:
   - Use **Next ▶** button for sequential workflow
   - Or select another task from the filtered list

## Advanced Features

### Error Handling and Recovery

- **Retry/Skip Options**: When errors occur, choose to retry or skip operations
- **Automatic Retries**: Built-in exponential backoff for transient failures
- **Timeout Management**: Configurable timeouts prevent hanging operations

### Batch Processing Workflow

1. **Filter Tasks**: Use app and search filters to create focused task sets
2. **Sequential Processing**: Navigate through filtered tasks systematically
3. **Progress Tracking**: Task counter shows progress through the set
4. **Note Management**: Persistent notes across task sessions

### Action Type Support

The system supports comprehensive OSWorld action types:

- **Core Actions**: `launch`, `sleep`, `execute`, `command`
- **File Operations**: `download`, `open`, `copy_to_guest`, `write_file`, `unzip`
- **Window Management**: `activate_window`, `close_window`
- **Browser Actions**: `chrome_open_tabs`
- **System Operations**: `set_env`, `kill_process`, `powershell`, `shell`
- **Fallback Handling**: Unknown actions use generic PowerShell execution

### Configuration Options

Edit `config.yaml` to customize:

```yaml
# VM Configuration
vmx_path: "C:\\VMs\\Windows10\\Windows10.vmx"
guest_username: "user"
guest_password: "password"

# Application Settings
start_fullscreen: true
output_dir: "runs"
tasks_dir: "tasks"

# VMware Paths (auto-detected if not specified)
vmrun_path: "C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmrun.exe"
vmware_path: "C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmware.exe"
```

## Troubleshooting

### Common Issues

1. **VM Not Starting**:
   - Verify VMware Workstation is running
   - Check VM file path in `config.yaml`
   - Ensure VM is not already running

2. **Snapshot Not Found**:
   - Create a snapshot named "clean" in your VM
   - Verify snapshot exists using VMware interface
   - Check VM file permissions

3. **Task Execution Fails**:
   - Use **Retry** button for transient failures
   - Check VM guest credentials
   - Verify required applications are installed in VM

4. **Validation Errors**:
   - Review task requirements carefully
   - Check if manual steps were completed correctly
   - Examine detailed error messages in status log

### Performance Tips

1. **VM Optimization**:
   - Allocate sufficient RAM to VM (4GB+)
   - Use SSD storage for better performance
   - Disable unnecessary VM features

2. **Application Settings**:
   - Close other VMware instances
   - Run as administrator if needed
   - Ensure adequate host system resources

### Getting Help

1. **Log Files**: Check execution logs in the status panel
2. **Run Directory**: Detailed results saved in `runs/<timestamp>_<task_id>/`
3. **Configuration**: Verify settings in `config.yaml`
4. **VM State**: Ensure VM snapshot "clean" is properly configured

## File Structure

```
AnnotatorKit/
├── AnnotatorKit.exe          # Main executable
├── config.yaml               # Configuration file
├── README.txt                # Basic information
├── run_annotator.bat         # Launch script
├── tasks/                    # Task definitions
│   └── samples/              # Sample tasks
├── runs/                     # Execution results
│   └── <timestamp>_<task>/   # Individual run data
│       ├── task.json         # Task configuration
│       ├── eval_result.json  # Validation results
│       └── notes.txt         # Annotator notes
└── logs/                     # Application logs
```

## Best Practices

1. **Task Organization**:
   - Group related tasks in subdirectories
   - Use descriptive task IDs
   - Maintain consistent naming conventions

2. **Annotation Workflow**:
   - Read instructions carefully before starting
   - Document unexpected behaviors in notes
   - Use filters to focus on specific app categories

3. **VM Management**:
   - Regularly update the "clean" snapshot
   - Keep VM applications up to date
   - Monitor VM performance and resources

4. **Quality Assurance**:
   - Validate tasks immediately after completion
   - Review failed tasks for patterns
   - Maintain notes for future reference

---

**Version**: 3.0 (Day 3 Enhanced)  
**Last Updated**: September 2024  
**Support**: Check project repository for updates and issues
