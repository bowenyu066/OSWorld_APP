# Incomplete Day 1 Features

This document records two features that were not fully implemented or have issues in Day 1.

## 1. Revert Snapshot Issue

### Problem
The snapshot revert functionality has logic issues:
- Initially tried to revert snapshots even when no VM was running
- Current logic was modified but still doesn't successfully revert when starting another task
- The revert process should happen before starting a new task to ensure clean state

### Current Implementation
- Located in `app/vm_control.py` in the `revert_snapshot()` method
- Has pre-check logic via `can_revert_snapshot()` to avoid long waits
- Stops VM before reverting if it's running

### Intended Behavior
- When starting a new task, the VM should be shut down, reverted to clean snapshot, then restarted
- This ensures each task starts with a clean environment (e.g., browser history cleared)

### Status
- **Temporarily set aside** - needs further debugging and testing
- The logic exists but doesn't work reliably in the task-switching workflow

## 2. Floating Overlay Window

### Problem
When VM starts in fullscreen mode, it covers the main GUI window, making it impossible to access task instructions and the Validate button.

### Proposed Solution
- Create a small floating overlay window that stays on top of the fullscreen VM
- Much smaller than the current GUI window
- Should display:
  - Current task instructions
  - A Validate button
  - Possibly task progress/status

### Technical Requirements
- Always-on-top window behavior
- Small, non-intrusive design
- Positioned in top-right corner or similar
- Should remain accessible even when VM is fullscreen

### Status
- **Not implemented** - can be added in future iterations
- Current workaround: Users need to Alt+Tab or use window switching to access the main GUI

## Impact on Day 1 Completion

Despite these two incomplete features, Day 1 core objectives were achieved:
- ✅ VM can be started and controlled
- ✅ GUI interface works for task selection and execution
- ✅ Basic task execution (launch, sleep, chrome_open_tabs) implemented
- ✅ Integration with VMware via vmrun/vmware.exe
- ✅ Task JSON parsing and validation
- ✅ Interactive mode for running programs in guest

The missing features are quality-of-life improvements that don't block the core functionality or Day 2 development.
