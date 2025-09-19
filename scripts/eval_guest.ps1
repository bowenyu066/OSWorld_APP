# PowerShell script to run evaluation in guest VM
param(
    [Parameter(Mandatory=$true)]
    [string]$TaskFile,
    
    [Parameter(Mandatory=$true)]
    [string]$OutputFile,
    
    [Parameter(Mandatory=$false)]
    [string]$EvaluatorPath = "C:\evaluators\eval.py",
    
    [Parameter(Mandatory=$false)]
    [string]$LogFile = "C:\Tasks\evaluation.log"
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
    Write-Log "Starting task evaluation in guest VM"
    Write-Log "Task file: $TaskFile"
    Write-Log "Output file: $OutputFile"
    Write-Log "Evaluator: $EvaluatorPath"
    
    # Check if required files exist
    if (-not (Test-Path $TaskFile)) {
        throw "Task file not found: $TaskFile"
    }
    
    if (-not (Test-Path $EvaluatorPath)) {
        throw "Evaluator script not found: $EvaluatorPath"
    }
    
    # Ensure output directory exists
    $outputDir = Split-Path -Parent $OutputFile
    if (-not (Test-Path $outputDir)) {
        New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    }
    
    # Run the Python evaluator
    Write-Log "Executing Python evaluator..."
    $pythonArgs = @(
        $EvaluatorPath,
        "--task", $TaskFile,
        "--out", $OutputFile
    )
    
    $process = Start-Process -FilePath "python" -ArgumentList $pythonArgs -Wait -PassThru -NoNewWindow -RedirectStandardOutput "eval_stdout.txt" -RedirectStandardError "eval_stderr.txt"
    
    # Check execution result
    if ($process.ExitCode -eq 0) {
        Write-Log "Evaluation completed successfully"
        
        # Read and log the output if it exists
        if (Test-Path $OutputFile) {
            $result = Get-Content -Path $OutputFile -Raw
            Write-Log "Evaluation result: $result"
        }
    } else {
        $stderr = ""
        if (Test-Path "eval_stderr.txt") {
            $stderr = Get-Content -Path "eval_stderr.txt" -Raw
        }
        throw "Evaluation failed with exit code $($process.ExitCode). Error: $stderr"
    }
    
    Write-Log "Task evaluation completed"
    exit 0
    
} catch {
    Write-Log "Error during evaluation: $($_.Exception.Message)"
    
    # Create error result file
    $errorResult = @{
        passed = $false
        details = @{
            error = $_.Exception.Message
            timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        }
    } | ConvertTo-Json -Depth 3
    
    Set-Content -Path $OutputFile -Value $errorResult -Encoding UTF8
    exit 1
} finally {
    # Clean up temporary files
    Remove-Item -Path "eval_stdout.txt" -ErrorAction SilentlyContinue
    Remove-Item -Path "eval_stderr.txt" -ErrorAction SilentlyContinue
}
