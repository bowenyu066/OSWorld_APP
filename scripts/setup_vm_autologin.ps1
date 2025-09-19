# PowerShell script to configure Windows VM for automatic login
# Run this script INSIDE the Windows VM as Administrator

param(
    [Parameter(Mandatory=$true)]
    [string]$Username,
    
    [Parameter(Mandatory=$true)]
    [string]$Password
)

Write-Host "Configuring Windows for automatic login..." -ForegroundColor Green

try {
    # Set registry keys for auto-login
    $regPath = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
    
    Set-ItemProperty -Path $regPath -Name "AutoAdminLogon" -Value "1" -Type String
    Set-ItemProperty -Path $regPath -Name "DefaultUserName" -Value $Username -Type String
    Set-ItemProperty -Path $regPath -Name "DefaultPassword" -Value $Password -Type String
    
    # Disable lock screen (Windows 10/11)
    $regPath2 = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Personalization"
    if (!(Test-Path $regPath2)) {
        New-Item -Path $regPath2 -Force
    }
    Set-ItemProperty -Path $regPath2 -Name "NoLockScreen" -Value 1 -Type DWord
    
    # Disable password expiration for the user
    net accounts /maxpwage:unlimited
    
    # Set user password to never expire
    wmic useraccount where "Name='$Username'" set PasswordExpires=FALSE
    
    Write-Host "Auto-login configured successfully!" -ForegroundColor Green
    Write-Host "Please restart the VM for changes to take effect." -ForegroundColor Yellow
    
} catch {
    Write-Host "Error configuring auto-login: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Optional: Disable Windows Defender real-time protection for better performance
try {
    Set-MpPreference -DisableRealtimeMonitoring $true
    Write-Host "Windows Defender real-time protection disabled." -ForegroundColor Green
} catch {
    Write-Host "Could not disable Windows Defender (may require different permissions)." -ForegroundColor Yellow
}

Write-Host "Setup complete! Restart the VM to enable auto-login." -ForegroundColor Green
