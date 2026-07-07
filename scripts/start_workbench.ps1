[CmdletBinding()]
param(
    [ValidateSet("menu", "start", "clean-start")]
    [string] $Mode = "menu",
    [switch] $Yes,
    [switch] $NoPause
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ApiPort = 8401
$FrontendPort = 10086

function Write-Section {
    param([string] $Title)
    Write-Host ""
    Write-Host "== $Title =="
}

function Test-TcpPort {
    param([int] $Port)

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(250, $false)) {
            return $false
        }
        $client.EndConnect($async)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Wait-HttpOk {
    param(
        [string] $Url,
        [int] $TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Uri $Url
            if ([int] $response.StatusCode -ge 200 -and [int] $response.StatusCode -lt 300) {
                return $true
            }
        }
        catch {
            Start-Sleep -Seconds 1
        }
    } while ((Get-Date) -lt $deadline)

    return $false
}

function Get-LanIp {
    try {
        $ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
            Where-Object {
                $_.IPAddress -ne "127.0.0.1" -and
                $_.IPAddress -notlike "169.254.*" -and
                $_.PrefixOrigin -ne "WellKnown" -and
                $_.InterfaceOperationalStatus -eq "Up"
            } |
            Sort-Object InterfaceMetric, PrefixLength |
            Select-Object -First 1 -ExpandProperty IPAddress

        if ($ip) {
            return $ip
        }
    }
    catch {
        # Fall through to DNS lookup.
    }

    try {
        return [System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) |
            Where-Object {
                $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and
                $_.IPAddressToString -ne "127.0.0.1" -and
                $_.IPAddressToString -notlike "169.254.*"
            } |
            Select-Object -First 1 -ExpandProperty IPAddressToString
    }
    catch {
        return $null
    }
}

function Show-Addresses {
    $lanIp = Get-LanIp

    Write-Section "Access URLs"
    Write-Host "Local frontend : http://localhost:$FrontendPort/"
    Write-Host "Local backend  : http://localhost:$ApiPort/"

    if ($lanIp) {
        Write-Host "LAN frontend   : http://${lanIp}:$FrontendPort/"
        Write-Host "LAN backend    : http://${lanIp}:$ApiPort/"
    }
    else {
        Write-Host "LAN frontend   : unavailable, LAN IPv4 not found"
        Write-Host "LAN backend    : unavailable, LAN IPv4 not found"
    }
}

function Invoke-Checked {
    param(
        [string] $Label,
        [scriptblock] $Action
    )

    Write-Host "- $Label"
    & $Action
}

function Start-Infra {
    Invoke-Checked "Starting Docker services" {
        if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
            throw "docker was not found in PATH."
        }
        if (-not (Test-Path -LiteralPath (Join-Path $Root ".env"))) {
            throw ".env was not found at $Root"
        }

        Push-Location $Root
        try {
            & docker compose --env-file .env -f infra/compose.yaml up -d
            if ($LASTEXITCODE -ne 0) {
                throw "docker compose up failed with exit code $LASTEXITCODE"
            }
        }
        finally {
            Pop-Location
        }
    }
}

function Start-Api {
    if (Test-TcpPort $ApiPort) {
        Write-Host "- Backend already listening on $ApiPort"
        return
    }

    Invoke-Checked "Starting backend API on $ApiPort" {
        $escapedRoot = $Root.Replace("'", "''")
        $command = "Set-Location -LiteralPath '$escapedRoot'; `$env:API_PORT='$ApiPort'; python -m api.run"
        Start-Process -FilePath "powershell.exe" `
            -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $command) `
            -WorkingDirectory $Root `
            -WindowStyle Normal
    }
}

function Start-Frontend {
    if (Test-TcpPort $FrontendPort) {
        Write-Host "- Frontend already listening on $FrontendPort"
        return
    }

    Invoke-Checked "Starting H5 frontend on $FrontendPort" {
        $command = "title Workbench H5 :$FrontendPort && cd /d ""$Root"" && npm.cmd run dev"
        Start-Process -FilePath "cmd.exe" `
            -ArgumentList @("/k", $command) `
            -WorkingDirectory $Root `
            -WindowStyle Normal
    }
}

function Get-PortOwners {
    param([int] $Port)

    try {
        return @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique)
    }
    catch {
        return @()
    }
}

function Stop-PortOwners {
    param([int[]] $Ports)

    foreach ($port in $Ports) {
        $owners = Get-PortOwners -Port $port
        foreach ($ownerPid in $owners) {
            if (-not $ownerPid) {
                continue
            }

            $process = Get-Process -Id $ownerPid -ErrorAction SilentlyContinue
            if (-not $process) {
                continue
            }

            Write-Host "- Stopping PID $ownerPid ($($process.ProcessName)) on port $port"
            Stop-Process -Id $ownerPid -Force -ErrorAction Stop
        }
    }
}

function Confirm-CleanStart {
    $portsInUse = @()
    foreach ($port in @($ApiPort, $FrontendPort)) {
        if ((Get-PortOwners -Port $port).Count -gt 0) {
            $portsInUse += $port
        }
    }

    if ($portsInUse.Count -eq 0 -or $Yes) {
        return $true
    }

    Write-Host ""
    Write-Host "Clean start will stop existing processes on ports: $($portsInUse -join ', ')"
    $answer = Read-Host "Continue? [y/N]"
    return $answer -match "^(y|yes)$"
}

function Remove-CachePath {
    param([string] $RelativePath)

    $rootFull = [System.IO.Path]::GetFullPath($Root)
    $fullPath = [System.IO.Path]::GetFullPath((Join-Path $Root $RelativePath))
    $rootPrefix = $rootFull.TrimEnd("\") + "\"

    if (-not $fullPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside repository: $fullPath"
    }

    if (Test-Path -LiteralPath $fullPath) {
        Write-Host "- Removing $RelativePath"
        Remove-Item -LiteralPath $fullPath -Recurse -Force
    }
    else {
        Write-Host "- Cache not present: $RelativePath"
    }
}

function Clear-WorkbenchCache {
    Write-Section "Clear cache"

    if (-not (Confirm-CleanStart)) {
        throw "Clean start was cancelled."
    }

    Stop-PortOwners -Ports @($FrontendPort, $ApiPort)
    Start-Sleep -Seconds 2

    Remove-CachePath "dist"
    Remove-CachePath ".tmp"
    Remove-CachePath ".swc"
    Remove-CachePath "node_modules\.cache"
    Remove-CachePath "node_modules\.taro"
}

function Start-Workbench {
    param([switch] $Clean)

    Set-Location $Root
    Write-Section "Workbench launcher"
    Write-Host "Repository: $Root"

    if ($Clean) {
        Clear-WorkbenchCache
    }

    Start-Infra
    Start-Api
    Start-Frontend

    Show-Addresses

    Write-Section "Health checks"
    if (Wait-HttpOk -Url "http://localhost:$ApiPort/health/live" -TimeoutSeconds 45) {
        Write-Host "- Backend live  : OK"
    }
    else {
        Write-Host "- Backend live  : not ready yet"
    }

    if (Wait-HttpOk -Url "http://localhost:$ApiPort/health/ready" -TimeoutSeconds 60) {
        Write-Host "- Backend ready : OK"
    }
    else {
        Write-Host "- Backend ready : not ready yet, check Docker/database"
    }

    if (Wait-HttpOk -Url "http://localhost:$FrontendPort/" -TimeoutSeconds 150) {
        Write-Host "- Frontend      : OK"
    }
    else {
        Write-Host "- Frontend      : not ready yet, watch the H5 terminal"
    }
}

function Read-ModeFromMenu {
    Write-Section "Workbench launcher"
    Write-Host "1. Start"
    Write-Host "2. Clear cache and start"
    Write-Host "Q. Quit"
    Write-Host ""

    $choice = Read-Host "Choose"
    switch -Regex ($choice) {
        "^[1sS]$" { return "start" }
        "^[2cC]$" { return "clean-start" }
        "^[qQ]$" { return "quit" }
        default { throw "Unknown choice: $choice" }
    }
}

try {
    if ($Mode -eq "menu") {
        $Mode = Read-ModeFromMenu
    }

    switch ($Mode) {
        "start" { Start-Workbench }
        "clean-start" { Start-Workbench -Clean }
        "quit" { return }
    }
}
catch {
    Write-Host ""
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    if (-not $NoPause) {
        Write-Host ""
        Read-Host "Press Enter to close"
    }
}
