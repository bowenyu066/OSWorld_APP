# PowerShell script to run configuration actions in guest VM
param(
    [Parameter(Mandatory=$true)]
    [string]$TaskFile,
    
    [Parameter(Mandatory=$false)]
    [string]$LogFile = "C:\Tasks\execution.log"
)

# Function to log messages
function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] $Message"
    Write-Host $logMessage
    if ($LogFile) {
        Add-Content -Path $LogFile -Value $logMessage -ErrorAction SilentlyContinue
    }
}

try {
    Write-Log "Starting guest configuration execution"
    Write-Log "Task file: $TaskFile"
    
    # Check if task file exists
    if (-not (Test-Path $TaskFile)) {
        throw "Task file not found: $TaskFile"
    }
    
    # Read and parse task JSON
    $taskContent = Get-Content -Path $TaskFile -Raw -Encoding UTF8
    $task = $taskContent | ConvertFrom-Json
    
    Write-Log "Task ID: $($task.id)"
    Write-Log "Number of config actions: $($task.config.Count)"
    
    # Execute each configuration action
    foreach ($action in $task.config) {
        Write-Log "Executing action: $($action.type)"
        
        switch ($action.type) {
            "launch" {
                $command = $action.parameters.command
                if ($command -is [array]) {
                    $program = $command[0]
                    $args = $command[1..($command.Length-1)]
                } else {
                    $program = $command
                    $args = @()
                }
                
                Write-Log "Launching: $program with args: $($args -join ' ')"
                
                # Map common programs to Windows paths
                switch ($program) {
                    "google-chrome" { $program = "C:\Program Files\Google\Chrome\Application\chrome.exe" }
                    "chrome" { $program = "C:\Program Files\Google\Chrome\Application\chrome.exe" }
                    "notepad" { $program = "C:\Windows\System32\notepad.exe" }
                }
                
                if ($args) {
                    Start-Process -FilePath $program -ArgumentList $args -ErrorAction Stop
                } else {
                    Start-Process -FilePath $program -ErrorAction Stop
                }
            }
            
            "sleep" {
                $seconds = $action.parameters.seconds
                Write-Log "Sleeping for $seconds seconds"
                Start-Sleep -Seconds $seconds
            }
            
            "chrome_open_tabs" {
                $urls = $action.parameters.urls_to_open
                $chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
                
                foreach ($url in $urls) {
                    Write-Log "Opening URL: $url"
                    Start-Process -FilePath $chromePath -ArgumentList $url
                    Start-Sleep -Seconds 1
                }
            }
            
            default {
                Write-Log "Unknown action type: $($action.type), skipping"
            }
        }
    }
    
    Write-Log "Guest configuration execution completed successfully"
    exit 0
    
} catch {
    Write-Log "Error during execution: $($_.Exception.Message)"
    Write-Log "Stack trace: $($_.ScriptStackTrace)"
    exit 1
}
