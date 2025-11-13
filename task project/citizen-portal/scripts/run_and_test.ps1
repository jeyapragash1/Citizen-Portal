# Run and smoke-test the citizen-portal app inside the project's virtualenv.
# Usage: Open PowerShell as the project user and run this script.
# It will:
#  - Activate the virtualenv
#  - Upgrade pip
#  - Install required runtime packages
#  - Compile app.py to check syntax
#  - Start the app in background using the venv python
#  - Wait for the server and call a few endpoints
#  - Stop the server when you press Enter

$project = "G:\\INTERNSHIP\\task project\\citizen-portal"
Set-Location -Path $project

Write-Host "Activating virtual environment..."
# Activate the venv for this session (no-op if already active)
$activate = Join-Path $project ".venv\Scripts\Activate.ps1"
if (Test-Path $activate) {
    & $activate
} else {
    Write-Host "Virtual environment activation script not found at $activate" -ForegroundColor Yellow
    Write-Host "If you don't have a venv, create one: python -m venv .venv" -ForegroundColor Yellow
}

Write-Host "Upgrading pip and installing runtime packages..."
python -m pip install --upgrade pip
$packages = @('bcrypt','python-dotenv','pymongo','flask','flask-cors','Flask-Session','flask-login','dnspython','requests')
python -m pip install $packages

Write-Host "Checking Python syntax for app.py..."
try {
    python -m py_compile app.py
    Write-Host "app.py compiled OK"
} catch {
    Write-Host "Syntax check FAILED:" $_ -ForegroundColor Red
    exit 1
}

# Start the server using the venv python executable to ensure same environment
$venvPython = Join-Path $project ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    # fallback to 'python' in PATH
    $venvPython = "python"
}

Write-Host "Starting Flask app using: $venvPython app.py"
$proc = Start-Process -FilePath $venvPython -ArgumentList 'app.py' -PassThru
Write-Host "Started process Id=$($proc.Id)" 

# Wait for server to become available
$timeout = 30
$elapsed = 0
$serverUp = $false
while ($elapsed -lt $timeout) {
    try {
        $r = Invoke-RestMethod -Uri 'http://127.0.0.1:5000/api/services' -Method Get -TimeoutSec 3
        $serverUp = $true
        break
    } catch {
        Start-Sleep -Seconds 1
        $elapsed += 1
    }
}

if (-not $serverUp) {
    Write-Host "Server did not respond within $timeout seconds. Check logs. Process Id: $($proc.Id)" -ForegroundColor Red
    Write-Host "You can view server logs in the terminal where this script started the process." -ForegroundColor Yellow
    exit 1
}

Write-Host "Server is up. Running smoke tests..."
$endpoints = @('/api/services','/api/ads','/api/store/products')
foreach ($e in $endpoints) {
    try {
        $uri = "http://127.0.0.1:5000$e"
        $res = Invoke-RestMethod -Uri $uri -Method Get -TimeoutSec 10
        Write-Host "OK: $e -> returned" -NoNewline; Write-Host (if ($res -is [System.Array]) { "array (count=$(($res).Length))" } else { "object" })
    } catch {
        Write-Host "ERROR calling $e: $_" -ForegroundColor Red
    }
}

Write-Host "Smoke tests complete. Press Enter to stop the server and exit."
Read-Host | Out-Null

try {
    if ($proc -and $proc.Id) {
        Write-Host "Stopping process Id=$($proc.Id)"
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
} catch {
    Write-Host "Failed to stop process: $_" -ForegroundColor Yellow
}

Write-Host "Done."