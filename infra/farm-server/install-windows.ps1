<#
.SYNOPSIS
  Algaroshy Farm server for Windows (Milestone G7): starts the farm app when the PC boots,
  without anyone signing in, and restarts it if it stops.

.DESCRIPTION
  Registers a Windows scheduled task "AlgaroshyFarmServer" that runs
      node scripts\start.mjs server
  at system start-up as the current Windows user (no password is stored: S4U logon).
  The launcher itself restarts any part that crashes; the task restarts the launcher.
  Logs: logs\farm-server.log in the project folder.

  Run once from an elevated PowerShell (Run as administrator), in the project folder:
      powershell -ExecutionPolicy Bypass -File infra\farm-server\install-windows.ps1
  Remove:
      powershell -ExecutionPolicy Bypass -File infra\farm-server\install-windows.ps1 -Uninstall
  Also useful: -NoSleep turns off sleep/hibernate on mains power so the server stays up.

  Run run.bat demo once by hand first: it sets up Python, packages and .env.
#>
param(
  [switch]$Uninstall,
  [switch]$NoSleep
)

$ErrorActionPreference = 'Stop'
$TaskName = 'AlgaroshyFarmServer'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
  [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
  Write-Host '[!] Please run this from PowerShell opened with "Run as administrator".' -ForegroundColor Red
  exit 1
}

if ($Uninstall) {
  if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed the '$TaskName' task. Run stop.bat if the app is still running."
  } else {
    Write-Host "No '$TaskName' task is installed."
  }
  exit 0
}

$node = (Get-Command node -ErrorAction SilentlyContinue).Source
if (-not $node) { Write-Host '[!] Node.js 20+ is required: https://nodejs.org' -ForegroundColor Red; exit 1 }
if (-not (Test-Path (Join-Path $Root '.env')) -or -not (Test-Path (Join-Path $Root 'apps\api\.venv'))) {
  Write-Host '[!] Run "run.bat demo" once first (it sets up Python, packages and .env), then run this again.' -ForegroundColor Red
  exit 1
}

# pnpm and python must be found by the task too: give it the PATH this shell has now.
$pathNow = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
$runDir = Join-Path $Root '.run'
New-Item -ItemType Directory -Force $runDir | Out-Null
$wrapper = Join-Path $runDir 'farm-server.cmd'
@(
  '@echo off',
  "set `"PATH=$pathNow`"",
  "cd /d `"$Root`"",
  "`"$node`" scripts\start.mjs server"
) | Set-Content -Path $wrapper -Encoding ascii

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "/d /c `"$wrapper`"" -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -AtStartup
$trigger.Delay = 'PT30S'  # let the network come up first
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
  -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal `
  -Settings $settings -Description 'Algaroshy Farm irrigation server (API, controller link, web app)' -Force | Out-Null
Write-Host "Installed the '$TaskName' task: the farm app now starts with Windows." -ForegroundColor Green

if ($NoSleep) {
  powercfg /change standby-timeout-ac 0
  powercfg /change hibernate-timeout-ac 0
  Write-Host 'Sleep and hibernate are off while on mains power.'
}

Start-ScheduledTask -TaskName $TaskName
Write-Host 'Started. First start builds the web app (a minute or two); then open http://localhost:4173'
Write-Host "Log: $Root\logs\farm-server.log"
