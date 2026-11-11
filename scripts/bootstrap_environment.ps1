param(
    [switch]$InstallIfMissing,
    [switch]$CheckOnly,
    [string]$MinVersion = "3.10"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillRoot = Split-Path -Parent $ScriptDir
$ConfigDir = Join-Path $SkillRoot ".config"
$RuntimeConfig = Join-Path $ConfigDir "runtime.json"
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null

function Test-PythonCandidate {
    param([string[]]$CommandParts)

    if (-not $CommandParts -or $CommandParts.Count -eq 0) {
        return $null
    }

    $exe = $CommandParts[0]
    $prefixArgs = @()
    if ($CommandParts.Count -gt 1) {
        $prefixArgs = $CommandParts[1..($CommandParts.Count - 1)]
    }

    try {
        $probe = @(
            '-c',
            'import sys; print(sys.version.split()[0], sys.executable, sep=chr(124))'
        )
        $raw = & $exe @prefixArgs @probe 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $raw) {
            return $null
        }

        $firstLine = [string](($raw | Select-Object -First 1))
        $parts = $firstLine.Split('|', 2)
        if ($parts.Count -lt 2) {
            return $null
        }

        $version = [Version]$parts[0]
        $minimum = [Version]$MinVersion
        if ($version -lt $minimum) {
            return $null
        }

        return [ordered]@{
            command = $CommandParts
            executable = $parts[1]
            version = $version.ToString()
        }
    }
    catch {
        return $null
    }
}

function Find-PythonRuntime {
    $candidates = @()

    if ($env:CODEX_007AI_PYTHON) {
        $candidates += ,@($env:CODEX_007AI_PYTHON)
    }

    $candidates += ,@('python')
    $candidates += ,@('py', '-3')
    $candidates += ,@('py')

    $knownPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "$env:ProgramFiles\Python311\python.exe"
    )

    foreach ($path in $knownPaths) {
        if ($path -and (Test-Path -LiteralPath $path)) {
            $candidates += ,@($path)
        }
    }

    foreach ($candidate in $candidates) {
        $result = Test-PythonCandidate -CommandParts $candidate
        if ($result) {
            return $result
        }
    }

    return $null
}

function Save-RuntimeConfig {
    param([hashtable]$Runtime)

    $payload = [ordered]@{
        python_command = $Runtime.command
        python_executable = $Runtime.executable
        python_version = $Runtime.version
        checked_at = (Get-Date).ToString('o')
        dependency_mode = 'python-stdlib-only'
    }
    $payload | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $RuntimeConfig -Encoding UTF8
}

function Install-PythonWithWinget {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "winget was not found. Install Python 3.10+ manually, or grant permission and retry."
    }

    & winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "winget failed to install Python. Exit code: $LASTEXITCODE"
    }

    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machinePath;$userPath;$env:Path"
}

$runtime = Find-PythonRuntime
if ($runtime) {
    Save-RuntimeConfig -Runtime $runtime
    [ordered]@{
        ok = $true
        installed = $false
        python = $runtime
        runtime_config = $RuntimeConfig
        message = "Python runtime is available. This skill uses Python stdlib only."
    } | ConvertTo-Json -Depth 6
    exit 0
}

if ($CheckOnly -or -not $InstallIfMissing) {
    [ordered]@{
        ok = $false
        installed = $false
        runtime_config = $RuntimeConfig
        message = "Python 3.10+ was not found. In full-access mode run this script with -InstallIfMissing; otherwise request user permission first."
    } | ConvertTo-Json -Depth 6
    exit 2
}

Install-PythonWithWinget
$runtime = Find-PythonRuntime
if (-not $runtime) {
    throw "Python installation was attempted, but Python 3.10+ is still unavailable."
}

Save-RuntimeConfig -Runtime $runtime
[ordered]@{
    ok = $true
    installed = $true
    python = $runtime
    runtime_config = $RuntimeConfig
    message = "Python runtime has been installed and configured."
} | ConvertTo-Json -Depth 6
