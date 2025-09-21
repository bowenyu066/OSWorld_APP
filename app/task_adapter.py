"""Task adapter for executing OSWorld task configurations."""

import time
import json
import os
import subprocess
import requests
from pathlib import Path
from typing import Dict, Any, Callable
from .models import Task, Action
from .vm_control import VMController
from .logging_setup import get_logger

logger = get_logger(__name__)

# Global action registry
ACTION_HANDLERS: Dict[str, Callable[[Action, VMController, Task], None]] = {}

def register(action_type: str):
    """Decorator to register action handlers."""
    def decorator(func):
        ACTION_HANDLERS[action_type] = func
        logger.debug(f"Registered action handler: {action_type}")
        return func
    return decorator


class TaskRunner:
    """Executes OSWorld task configurations with comprehensive action support."""
    
    def __init__(self):
        # Initialize with registered handlers
        self.action_handlers = ACTION_HANDLERS.copy()
        logger.info(f"TaskRunner initialized with {len(self.action_handlers)} action handlers")
    
    def run_config(self, task: Task, vm: VMController) -> None:
        """Execute all actions in the task configuration with retry logic.
        
        Args:
            task: The task to execute
            vm: VM controller instance
        """
        logger.info(f"Starting task configuration for: {task.id}")
        
        for i, action in enumerate(task.config):
            logger.info(f"Executing action {i+1}/{len(task.config)}: {action.type}")
            
            # Try to find specific handler
            handler = self.action_handlers.get(action.type)
            if handler:
                try:
                    handler(action, vm, task)
                    logger.info(f"Action {action.type} completed successfully")
                except Exception as e:
                    logger.error(f"Action {action.type} failed: {e}")
                    raise
            else:
                # Fallback to generic handler
                logger.warning(f"Unknown action type: {action.type}, using generic handler")
                try:
                    self._handle_generic_action(action, vm, task)
                    logger.info(f"Generic action {action.type} completed")
                except Exception as e:
                    logger.error(f"Generic action {action.type} failed: {e}")
                    raise
            
            # Add delay between actions to prevent timing issues
            if i < len(task.config) - 1:  # Don't delay after the last action
                # Different delays for different action types
                action_delays = {
                    "launch": 3.0,      # Programs need time to start
                    "chrome_open_tabs": 2.0,  # Tabs need time to load
                    "chrome_close_tabs": 1.0, # Quick action
                    "download": 1.0,    # Downloads are async
                    "execute": 2.0,     # Commands need time
                    "activate_window": 1.0,  # Quick action
                    "sleep": 0.0,       # Sleep has its own timing
                }
                
                next_action_type = task.config[i + 1].type if i + 1 < len(task.config) else None
                delay = action_delays.get(action.type, 2.0)  # Default 2 seconds
                
                if delay > 0:
                    logger.info(f"Waiting {delay} seconds before next action ({next_action_type})...")
                    time.sleep(delay)
        
        logger.info("Task configuration completed")
    
    def _handle_generic_action(self, action: Action, vm: VMController, task: Task) -> None:
        """Handle unknown action types using the generic action runner."""
        logger.warning(f"Unknown action type: {action.type}, using generic handler")
        
        # Create action file for the generic runner
        action_data = {
            "type": action.type,
            "parameters": action.parameters,
            "task_id": task.id
        }
        
        # Create temporary action file
        import tempfile
        import json
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(action_data, f, indent=2)
            temp_file = f.name
        
        try:
            # Copy action file to guest
            guest_actions_dir = "C:\\Tasks\\actions"
            vm.ensure_guest_dir(guest_actions_dir)
            
            action_filename = f"{task.id}_{action.type}.json"
            guest_action_file = f"{guest_actions_dir}\\{action_filename}"
            
            vm.copy_to_guest(temp_file, guest_action_file)
            
            # Copy generic action runner to guest if not already there
            runner_script = "C:\\evaluators\\generic_action_runner.py"
            host_runner = os.path.join(os.path.dirname(__file__), "..", "evaluators", "generic_action_runner.py")
            
            try:
                vm.copy_to_guest(host_runner, runner_script)
            except Exception as e:
                logger.warning(f"Could not copy generic runner to guest: {e}")
            
            # Run generic action runner in guest using full PowerShell command
            ps_command = f'python "{runner_script}" --action "{guest_action_file}"'
            
            logger.info(f"Executing generic action via: {ps_command}")
            result = vm.run_in_guest(
                "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
                ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
                interactive=True,
                nowait=True
            )
            
            if result == 0:
                logger.info(f"Generic action {action.type} completed")
            else:
                logger.warning(f"Generic action runner returned non-zero exit code: {result}")

        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file)
            except:
                pass


# Core Action Handlers

@register("launch")
def handle_launch(action: Action, vm: VMController, task: Task) -> bool:
    """Handle program launch actions."""
    # Handle multiple parameter formats for launch actions
    program = action.parameters.get("program", "")
    command = action.parameters.get("command", [])
    args = action.parameters.get("args", [])
    shell = action.parameters.get("shell", False)
    
    # Format 1: command as list ["program", "arg1", "arg2"]
    if command and isinstance(command, list):
        program = command[0] if command else ""
        args = command[1:] if len(command) > 1 else []
    # Format 2: command as string "program arg1 arg2" with shell=true
    elif command and isinstance(command, str):
        if shell:
            # For shell commands, use the full string as program
            program = command
            args = []
        else:
            # Split string into program and args
            parts = command.split()
            program = parts[0] if parts else ""
            args = parts[1:] if len(parts) > 1 else []
    
    if not program:
        logger.error("Launch action missing 'program' parameter")
        return False
    
    # Skip socat launches - they're not needed for basic Chrome functionality
    if "socat" in program.lower():
        logger.info(f"Skipping socat launch (not required): {program}")
        return True
    
    logger.info(f"Launching program: {program} with args: {args}")
    
    # Map common program names to Windows paths
    program_mappings = {
        "google-chrome": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "chrome": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "notepad": "C:\\Windows\\System32\\notepad.exe",
        "powershell": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
        "code": "C:\\Users\\user\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe",
        "vlc": "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe",
    }
    
    # Use mapping if available, otherwise use as-is
    if program in program_mappings:
        program = program_mappings[program]
    
    try:
        if shell:
            # For shell commands, use PowerShell to execute
            result = vm.run_in_guest(
                "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
                ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", program],
                interactive=True,
                nowait=True
            )
        else:
            result = vm.run_in_guest(program, args, interactive=True, nowait=True)
        
        if result == 0:
            logger.info("Action launch completed successfully")
            
            # Add extra delay for Chrome to fully start
            if "chrome" in program.lower():
                logger.info("Waiting extra 3 seconds for Chrome to fully initialize...")
                time.sleep(3.0)
            
            return True
        else:
            logger.warning(f"Program exited with non-zero code: {result}")
            return True  # Still consider it successful for launch actions
    except Exception as e:
        logger.error(f"Failed to launch program: {e}")
        return False


@register("sleep")
def handle_sleep(action: Action, vm: VMController, task: Task) -> None:
    """Handle sleep action - pause execution for specified seconds."""
    seconds = action.parameters.get("seconds", 1)
    logger.info(f"Sleeping for {seconds} seconds")
    time.sleep(seconds)


@register("execute")
def handle_execute(action: Action, vm: VMController, task: Task) -> bool:
    """Handle execute action - run commands in the guest VM."""
    command = action.parameters.get("command", [])
    if not command:
        logger.error("Execute action requires 'command' parameter")
        return False
    
    logger.info(f"Executing command: {command}")
    
    try:
        if isinstance(command, str):
            # Execute as shell command
            result = vm.run_in_guest(
                "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
                ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                interactive=True,
                nowait=True
            )
        elif isinstance(command, list):
            # Execute as program with arguments
            program = command[0]
            args = command[1:] if len(command) > 1 else []
            
            # Handle special cases for Python scripts
            if program == "python" and len(args) >= 2 and args[0] == "-c":
                # Python -c "script" format - combine into single command
                python_script = " ".join(args[1:])
                result = vm.run_in_guest(
                    "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
                    ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f'python -c "{python_script}"'],
                    interactive=True,
                    nowait=True
                )
            else:
                result = vm.run_in_guest(program, args, interactive=True, nowait=True)
        else:
            logger.error("Command must be string or list")
            return False
        
        if result == 0:
            logger.info("Execute action completed successfully")
            return True
        else:
            logger.warning(f"Execute command returned exit code: {result}")
            return True  # Still consider successful for execute actions
            
    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return False


@register("command")
def handle_command(action: Action, vm: VMController, task: Task) -> bool:
    """Handle command action - alias for execute."""
    return handle_execute(action, vm, task)

def _render_open(ps_template: str, port: int, profile: str, urls: list[str]) -> str:
    arr = ", ".join("'" + u.replace("'", "''") + "'" for u in urls)
    return (ps_template
            .replace("<<PORT>>", str(port))
            .replace("<<PROFILE>>", profile.replace("\\", "\\\\"))
            .replace("<<URLS_ARRAY>>", arr))

def _render_close(ps_template: str, port: int, profile: str, match_mode: str, urls: list[str]) -> str:
    arr = ", ".join("'" + u.replace("'", "''") + "'" for u in urls)
    return (ps_template
            .replace("<<PORT>>", str(port))
            .replace("<<PROFILE>>", profile.replace("\\", "\\\\"))
            .replace("<<MATCH_MODE>>", match_mode)
            .replace("<<URLS_ARRAY>>", arr))

@register("chrome_open_tabs")
def handle_chrome_open_tabs(action: Action, vm: VMController, task: Task) -> bool:
    import hashlib

    def _stable_port_from_tag(tag: str) -> int:
        h = int(hashlib.md5(tag.encode("utf-8")).hexdigest(), 16)
        return 9222 + (h % 2000)

    def _to_ps_single_quoted_array(items):
        # -> 'a', 'b', 'c'
        out = []
        for s in items:
            s = str(s).replace("'", "''")  # PowerShell 单引号转义
            out.append(f"'{s}'")
        return ", ".join(out)

    urls = action.parameters.get("urls", []) or action.parameters.get("urls_to_open", [])
    if not urls:
        logger.info("chrome_open_tabs: no URLs")
        return True

    window_tag = action.parameters.get("window_tag", "osworld")
    port = action.parameters.get("debug_port") or _stable_port_from_tag(window_tag)
    profile = rf"C:\ChromeProfile\{window_tag}"

    PS_OPEN = r'''$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

$port    = <<PORT>>
$profile = '<<PROFILE>>'

# 找浏览器（Chrome 优先，找不到就用 Edge）
$chromeCandidates = @(
  (Join-Path $env:ProgramFiles              'Google\Chrome\Application\chrome.exe'),
  (Join-Path ${env:ProgramFiles(x86)}       'Google\Chrome\Application\chrome.exe'),
  (Join-Path $env:LOCALAPPDATA              'Google\Chrome\Application\chrome.exe'),
  (Join-Path $env:ProgramFiles              'Microsoft\Edge\Application\msedge.exe'),
  (Join-Path ${env:ProgramFiles(x86)}       'Microsoft\Edge\Application\msedge.exe'),
  (Join-Path $env:LOCALAPPDATA              'Microsoft\Edge\Application\msedge.exe')
)
$chrome = $null
foreach ($p in $chromeCandidates) {
  if (Test-Path $p) { $chrome = $p; break }
}
if (-not $chrome) {
  try { $p=(Get-Command chrome.exe -ErrorAction SilentlyContinue).Path; if($p){$chrome=$p} } catch {}
}
if (-not $chrome) {
  try { $p=(Get-Command msedge.exe -ErrorAction SilentlyContinue).Path; if($p){$chrome=$p} } catch {}
}
if (-not $chrome) { Write-Host 'CHROME_NOT_FOUND'; exit 1 }
Write-Host ('Using: ' + $chrome)

# 准备 profile
try {
  New-Item -ItemType Directory -Force -Path $profile | Out-Null
} catch {
  Write-Host ('Profile dir failed: ' + $_); exit 1
}

function Test-PortReady {
  try {
    Invoke-WebRequest -Uri ('http://127.0.0.1:' + $port + '/json/version') -UseBasicParsing -TimeoutSec 2 | Out-Null
    return $true
  } catch { return $false }
}

Write-Host ('Checking CDP port ' + $port + ' ...')
if (-not (Test-PortReady)) {
  Write-Host ('Starting browser on port ' + $port + ' ...')

  # 用数组传参，避免引号问题
  $argList = @(
    ('--remote-debugging-port=' + $port),
    ('--user-data-dir=' + $profile),
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-web-security',
    '--disable-features=VizDisplayCompositor'
  )

  try {
    $proc = Start-Process -FilePath $chrome -ArgumentList $argList -PassThru
    Write-Host ('PID: ' + $proc.Id)
  } catch {
    Write-Host ('Start failed: ' + $_); exit 1
  }

  $ready = $false
  for ($i=0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 250
    if (Test-PortReady) { $ready = $true; break }
    if (($i % 8) -eq 0) { Write-Host ('Waiting CDP ... ' + ($i*250) + 'ms') }
  }
  if (-not $ready) { Write-Host 'CDP not ready (timeout)'; exit 2 }
} else {
  Write-Host 'CDP port already ready'
}

# 打开 URL
$opened = 0
$urls = @(<<URLS_ARRAY>>)
Write-Host ('Opening ' + $urls.Count + ' URLs ...')

foreach ($u in $urls) {
  try {
    $createTabUrl = 'http://127.0.0.1:' + $port + '/json/new?' + $u
    $resp = Invoke-WebRequest -Uri $createTabUrl -UseBasicParsing -TimeoutSec 5
    if ($resp.StatusCode -eq 200) { $opened++ } else { Write-Host ('Open failed: ' + $u) }
    Start-Sleep -Milliseconds 200
  } catch {
    Write-Host ('CDP error, fallback: ' + $u + ' ; ' + $_)
    try {
      Start-Process -FilePath $chrome -ArgumentList @(
        ('--user-data-dir=' + $profile),
        $u
      ) | Out-Null
      $opened++
    } catch { Write-Host ('Fallback failed: ' + $u) }
  }
}

if ($opened -le 0) { Write-Host 'No URL opened'; exit 3 }
Write-Host ('SUCCESS OPENED=' + $opened + ' PORT=' + $port + ' PROFILE=' + $profile)
exit 0
'''

    ps_open = _render_open(PS_OPEN, port, profile, urls)

    # 写入并执行
    script_path = r"C:\temp\chrome_open.ps1"
    create_ps = f"""
New-Item -ItemType Directory -Force -Path "C:\\temp" | Out-Null
@'
{ps_open}
'@ | Out-File -FilePath "{script_path}" -Encoding UTF8
"""
    try:
        vm.run_in_guest(
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", create_ps],
            interactive=True, nowait=False
        )
        rc = vm.run_in_guest(
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path],
            interactive=True, nowait=False
        )
        if rc == 0:
            logger.info("chrome_open_tabs: success")
            return True
        logger.warning(f"chrome_open_tabs: exit code {rc}")
        return False
    except Exception as e:
        logger.error(f"chrome_open_tabs error: {e}")
        return False


@register("chrome_close_tabs")
def handle_chrome_close_tabs(action: Action, vm: VMController, task: Task) -> bool:
    import hashlib

    def _stable_port_from_tag(tag: str) -> int:
        h = int(hashlib.md5(tag.encode("utf-8")).hexdigest(), 16)
        return 9222 + (h % 2000)

    def _to_ps_single_quoted_array(items):
        out = []
        for s in (items or []):
            s = str(s).replace("'", "''")
            out.append(f"'{s}'")
        return ", ".join(out)

    urls_to_close = action.parameters.get("urls_to_close", [])
    match_mode = action.parameters.get("match_mode", "substring")  # substring|prefix|exact
    window_tag = action.parameters.get("window_tag", "osworld")
    port = action.parameters.get("debug_port") or _stable_port_from_tag(window_tag)
    profile = rf"C:\ChromeProfile\{window_tag}"

    PS_CLOSE = r'''$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

$port      = <<PORT>>
$profile   = '<<PROFILE>>'
$matchMode = '<<MATCH_MODE>>'
$filterUrls = @(<<URLS_ARRAY>>)

function Try-CDP-Close {
  try {
    $list = Invoke-WebRequest -Uri ('http://127.0.0.1:' + $port + '/json') -UseBasicParsing -TimeoutSec 1
  } catch { return $false }
  $targets = ($list.Content | ConvertFrom-Json)
  if (-not $targets) { return $false }

  $want = @()
  if ($filterUrls.Count -gt 0) {
    foreach ($t in $targets) {
      if (-not $t.url -or $t.type -ne 'page') { continue }
      foreach ($f in $filterUrls) {
        switch ($matchMode) {
          'exact'  { if ($t.url -eq $f)                 { $want += $t; break } }
          'prefix' { if ($t.url -like ($f + '*'))       { $want += $t; break } }
          default  { if ($t.url -like ('*' + $f + '*')) { $want += $t; break } }
        }
      }
    }
  } else {
    $want = $targets | Where-Object { $_.type -eq 'page' -and $_.id }
  }

  $count = 0
  foreach ($t in $want) {
    try {
      $u = 'http://127.0.0.1:' + $port + '/json/close/' + $t.id
      Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 1 | Out-Null
      Start-Sleep -Milliseconds 100
      $count++
    } catch { }
  }
  if ($count -gt 0) { Write-Host ('CDP_CLOSED=' + $count); return $true }
  return $false
}

if (Try-CDP-Close) { exit 0 }

# Fallback：按 profile 关闭（兼容 Chrome / Edge）
try {
  $procs = Get-CimInstance -ClassName Win32_Process -Filter "Name='chrome.exe' OR Name='msedge.exe'"
  $mine  = $procs | Where-Object { $_.CommandLine -and ($_.CommandLine -like ('*' + $profile + '*')) }

  if ($mine) {
    foreach ($p in $mine) {
      try { (Get-Process -Id $p.ProcessId).CloseMainWindow() | Out-Null } catch { }
    }
    Start-Sleep -Seconds 2
    $alive = $mine | ForEach-Object { $_.ProcessId } | ForEach-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue } | Where-Object { $_ }
    if ($alive) {
      foreach ($p in $alive) {
        try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch { }
      }
    }
    Write-Host 'CHROME_CLOSED_FALLBACK'
  } else {
    Write-Host 'NO_CHROME_FOUND'
  }
} catch {
  Write-Host 'CHROME_CLOSE_ERROR'
}

exit 0
'''

    ps_close = _render_close(PS_CLOSE, port, profile, match_mode, urls_to_close)

    script_path = r"C:\temp\chrome_close.ps1"
    create_ps = f"""
New-Item -ItemType Directory -Force -Path "C:\\temp" | Out-Null
@'
{ps_close}
'@ | Out-File -FilePath "{script_path}" -Encoding UTF8
"""
    try:
        vm.run_in_guest(
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", create_ps],
            interactive=True, nowait=False
        )
        rc = vm.run_in_guest(
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path],
            interactive=True, nowait=False
        )
        if rc == 0:
            logger.info("chrome_close_tabs: success")
            return True
        logger.warning(f"chrome_close_tabs: exit code {rc}")
        return True  # best-effort
    except Exception as e:
        logger.error(f"chrome_close_tabs error: {e}")
        return False




@register("download")
def handle_download(action: Action, vm: VMController, task: Task) -> bool:
    """Handle download action - download files to guest VM."""
    files = action.parameters.get("files", [])
    if not files:
        logger.error("Download action requires 'files' parameter")
        return False
    
    success = True
    for file_info in files:
        if isinstance(file_info, dict):
            url = file_info.get("url", "")
            path = file_info.get("path", "")
            
            if not url or not path:
                logger.error(f"Invalid file info: {file_info}")
                success = False
                continue
            
            logger.info(f"Downloading {url} to {path}")
            
            # Use PowerShell to download file
            ps_command = f"""
            try {{
                Invoke-WebRequest -Uri '{url}' -OutFile '{path}' -UseBasicParsing
                Write-Host "Downloaded successfully: {path}"
            }} catch {{
                Write-Error "Download failed: $_"
                exit 1
            }}
            """
            
            try:
                result = vm.run_in_guest(
                    "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
                    ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
                    interactive=True,
                    nowait=True
                )
                
                if result != 0:
                    logger.error(f"Failed to download {url}")
                    success = False
                else:
                    logger.info(f"Successfully downloaded {url} to {path}")
                    
            except Exception as e:
                logger.error(f"Error downloading {url}: {e}")
                success = False
    
    return success


@register("open")
def handle_open(action: Action, vm: VMController, task: Task) -> bool:
    """Handle open action - open files with default applications."""
    path = action.parameters.get("path", "")
    
    if not path:
        logger.error("Open action missing 'path' parameter")
        return False
    
    logger.info(f"Opening file: {path}")
    
    # Use PowerShell Start-Process to open file with default application
    ps_command = f"Start-Process -FilePath '{path}'"
    
    try:
        result = vm.run_in_guest(
            "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
            ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
            interactive=True,
            nowait=True
        )
        
        if result == 0:
            logger.info(f"Successfully opened {path}")
            return True
        else:
            logger.warning(f"Open command returned exit code: {result}")
            return True  # Still consider successful for open actions
            
    except Exception as e:
        logger.error(f"Error opening {path}: {e}")
        return False


@register("activate_window")
def handle_activate_window(action: Action, vm: VMController, task: Task) -> bool:
    """Handle activate_window action - bring window to focus."""
    window_name = action.parameters.get("window_name", "")
    strict = action.parameters.get("strict", False)
    
    if not window_name:
        logger.error("activate_window action missing 'window_name' parameter")
        return False
    
    logger.info(f"Activating window: {window_name} (strict={strict})")
    
    # Use PowerShell to activate window
    ps_command = f"""
    Add-Type -AssemblyName Microsoft.VisualBasic
    Add-Type -AssemblyName System.Windows.Forms
    
    $processes = Get-Process | Where-Object {{$_.MainWindowTitle -ne ""}}
    $targetProcess = $null
    
    if ({str(strict).lower()}) {{
        $targetProcess = $processes | Where-Object {{$_.MainWindowTitle -eq "{window_name}"}}
    }} else {{
        $targetProcess = $processes | Where-Object {{$_.MainWindowTitle -like "*{window_name}*"}}
    }}
    
    if ($targetProcess) {{
        [Microsoft.VisualBasic.Interaction]::AppActivate($targetProcess.Id)
        Write-Host "Activated window: $($targetProcess.MainWindowTitle)"
    }} else {{
        Write-Warning "Window not found: {window_name}"
        exit 1
    }}
    """
    
    try:
        result = vm.run_in_guest(
            "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
            ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
            interactive=True,
            nowait=True
        )
        
        if result == 0:
            logger.info(f"Successfully activated window: {window_name}")
            return True
        else:
            logger.warning(f"Could not activate window: {window_name}")
            return False
            
    except Exception as e:
        logger.error(f"Error activating window {window_name}: {e}")
        return False


# File Operation Handlers

@register("download_old")
def handle_download_old(action: Action, vm: VMController, task: Task) -> None:
    """Handle download action - download files to guest VM."""
    files = action.parameters.get("files", [])
    if not files:
        raise ValueError("Download action requires 'files' parameter")
    
    for file_info in files:
        url = file_info.get("url")
        path = file_info.get("path")
        
        if not url or not path:
            logger.warning(f"Skipping invalid file entry: {file_info}")
            continue
        
        # Convert Linux path to Windows path
        windows_path = path.replace("/home/user/", "C:\\Users\\user\\")
        windows_path = windows_path.replace("/", "\\")
        
        # Create directory if needed
        dir_path = Path(windows_path).parent
        powershell_cmd = f"New-Item -ItemType Directory -Force -Path '{dir_path}'"
        vm.run_in_guest("powershell.exe", ["-Command", powershell_cmd])
        
        # Download file using PowerShell
        download_cmd = f"Invoke-WebRequest -Uri '{url}' -OutFile '{windows_path}'"
        logger.info(f"Downloading {url} to {windows_path}")
        vm.run_in_guest("powershell.exe", ["-Command", download_cmd])


@register("open")
def handle_open(action: Action, vm: VMController, task: Task) -> None:
    """Handle open action - open files with default application."""
    path = action.parameters.get("path")
    if not path:
        raise ValueError("Open action requires 'path' parameter")
    
    # Convert Linux path to Windows path
    windows_path = path.replace("/home/user/", "C:\\Users\\user\\")
    windows_path = windows_path.replace("/", "\\")
    
    logger.info(f"Opening file: {windows_path}")
    # Use start command to open with default application
    vm.run_in_guest("cmd.exe", ["/c", "start", f'"{windows_path}"'])


# Window Management Handlers

@register("activate_window")
def handle_activate_window(action: Action, vm: VMController, task: Task) -> None:
    """Handle activate_window action - bring window to focus."""
    window_name = action.parameters.get("window_name")
    strict = action.parameters.get("strict", False)
    
    if not window_name:
        raise ValueError("activate_window action requires 'window_name' parameter")
    
    # Use PowerShell to activate window
    if strict:
        powershell_cmd = f"""
        Add-Type -AssemblyName Microsoft.VisualBasic
        [Microsoft.VisualBasic.Interaction]::AppActivate('{window_name}')
        """
    else:
        powershell_cmd = f"""
        $window = Get-Process | Where-Object {{$_.MainWindowTitle -like '*{window_name}*'}} | Select-Object -First 1
        if ($window) {{
            Add-Type -AssemblyName Microsoft.VisualBasic
            [Microsoft.VisualBasic.Interaction]::AppActivate($window.Id)
        }}
        """
    
    logger.info(f"Activating window: {window_name}")
    vm.run_in_guest("powershell.exe", ["-Command", powershell_cmd])


@register("close_window")
def handle_close_window(action: Action, vm: VMController, task: Task) -> None:
    """Handle close_window action - close specific window."""
    window_name = action.parameters.get("window_name")
    strict = action.parameters.get("strict", False)
    
    if not window_name:
        raise ValueError("close_window action requires 'window_name' parameter")
    
    # Use PowerShell to close window
    if strict:
        powershell_cmd = f"Stop-Process -Name '{window_name}' -Force -ErrorAction SilentlyContinue"
    else:
        powershell_cmd = f"""
        Get-Process | Where-Object {{$_.MainWindowTitle -like '*{window_name}*'}} | Stop-Process -Force -ErrorAction SilentlyContinue
        """
    
    logger.info(f"Closing window: {window_name}")
    vm.run_in_guest("powershell.exe", ["-Command", powershell_cmd])


# System Operation Handlers

@register("set_env")
def handle_set_env(action: Action, vm: VMController, task: Task) -> None:
    """Handle set_env action - set environment variables."""
    env_vars = action.parameters.get("variables", {})
    
    for name, value in env_vars.items():
        powershell_cmd = f"[Environment]::SetEnvironmentVariable('{name}', '{value}', 'User')"
        logger.info(f"Setting environment variable: {name}={value}")
        vm.run_in_guest("powershell.exe", ["-Command", powershell_cmd])


@register("kill_process")
def handle_kill_process(action: Action, vm: VMController, task: Task) -> None:
    """Handle kill_process action - terminate processes."""
    process_name = action.parameters.get("name")
    process_id = action.parameters.get("pid")
    
    if process_name:
        powershell_cmd = f"Stop-Process -Name '{process_name}' -Force -ErrorAction SilentlyContinue"
        logger.info(f"Killing process by name: {process_name}")
    elif process_id:
        powershell_cmd = f"Stop-Process -Id {process_id} -Force -ErrorAction SilentlyContinue"
        logger.info(f"Killing process by ID: {process_id}")
    else:
        raise ValueError("kill_process action requires 'name' or 'pid' parameter")
    
    vm.run_in_guest("powershell.exe", ["-Command", powershell_cmd])


@register("powershell")
def handle_powershell(action: Action, vm: VMController, task: Task) -> None:
    """Handle powershell action - execute PowerShell commands."""
    script = action.parameters.get("script")
    command = action.parameters.get("command")
    
    if script:
        # Execute PowerShell script
        logger.info(f"Executing PowerShell script")
        vm.run_in_guest("powershell.exe", ["-File", script])
    elif command:
        # Execute PowerShell command
        logger.info(f"Executing PowerShell command: {command}")
        vm.run_in_guest("powershell.exe", ["-Command", command])
    else:
        raise ValueError("powershell action requires 'script' or 'command' parameter")


@register("shell")
def handle_shell(action: Action, vm: VMController, task: Task) -> None:
    """Handle shell action - execute shell commands."""
    command = action.parameters.get("command")
    if not command:
        raise ValueError("shell action requires 'command' parameter")
    
    logger.info(f"Executing shell command: {command}")
    vm.run_in_guest("cmd.exe", ["/c", command])


# File Transfer Handlers

@register("copy_to_guest")
def handle_copy_to_guest(action: Action, vm: VMController, task: Task) -> None:
    """Handle copy_to_guest action - copy files to VM."""
    source = action.parameters.get("source")
    destination = action.parameters.get("destination")
    
    if not source or not destination:
        raise ValueError("copy_to_guest action requires 'source' and 'destination' parameters")
    
    logger.info(f"Copying file to guest: {source} -> {destination}")
    # This would need VM-specific implementation
    # For now, log the operation
    logger.warning("copy_to_guest not fully implemented - requires VM file transfer capability")


@register("copy_from_guest")
def handle_copy_from_guest(action: Action, vm: VMController, task: Task) -> None:
    """Handle copy_from_guest action - copy files from VM."""
    source = action.parameters.get("source")
    destination = action.parameters.get("destination")
    
    if not source or not destination:
        raise ValueError("copy_from_guest action requires 'source' and 'destination' parameters")
    
    logger.info(f"Copying file from guest: {source} -> {destination}")
    # This would need VM-specific implementation
    # For now, log the operation
    logger.warning("copy_from_guest not fully implemented - requires VM file transfer capability")


@register("write_file")
def handle_write_file(action: Action, vm: VMController, task: Task) -> None:
    """Handle write_file action - write content to files."""
    path = action.parameters.get("path")
    content = action.parameters.get("content")
    encoding = action.parameters.get("encoding", "utf-8")
    
    if not path or content is None:
        raise ValueError("write_file action requires 'path' and 'content' parameters")
    
    # Convert Linux path to Windows path
    windows_path = path.replace("/home/user/", "C:\\Users\\user\\")
    windows_path = windows_path.replace("/", "\\")
    
    # Escape content for PowerShell
    escaped_content = content.replace("'", "''").replace("`", "``")
    
    powershell_cmd = f"""
    $content = '{escaped_content}'
    $path = '{windows_path}'
    New-Item -ItemType Directory -Force -Path (Split-Path $path -Parent) | Out-Null
    Set-Content -Path $path -Value $content -Encoding {encoding}
    """
    
    logger.info(f"Writing file: {windows_path}")
    vm.run_in_guest("powershell.exe", ["-Command", powershell_cmd])


@register("unzip")
def handle_unzip(action: Action, vm: VMController, task: Task) -> None:
    """Handle unzip action - extract archives."""
    source = action.parameters.get("source")
    destination = action.parameters.get("destination")
    
    if not source:
        raise ValueError("unzip action requires 'source' parameter")
    
    if not destination:
        destination = str(Path(source).parent)
    
    # Convert paths to Windows format
    windows_source = source.replace("/home/user/", "C:\\Users\\user\\").replace("/", "\\")
    windows_dest = destination.replace("/home/user/", "C:\\Users\\user\\").replace("/", "\\")
    
    powershell_cmd = f"Expand-Archive -Path '{windows_source}' -DestinationPath '{windows_dest}' -Force"
    
    logger.info(f"Extracting archive: {windows_source} -> {windows_dest}")
    vm.run_in_guest("powershell.exe", ["-Command", powershell_cmd])
