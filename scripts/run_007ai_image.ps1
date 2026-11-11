param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillRoot = Split-Path -Parent $ScriptDir
$RuntimeConfig = Join-Path $SkillRoot ".config\runtime.json"
$Bootstrap = Join-Path $ScriptDir "bootstrap_environment.ps1"
$Generator = Join-Path $ScriptDir "generate_007ai_image.py"

function Test-RuntimeConfig {
    if (-not (Test-Path -LiteralPath $RuntimeConfig)) {
        return $false
    }
    try {
        $runtime = Get-Content -Raw -LiteralPath $RuntimeConfig | ConvertFrom-Json
        $command = @($runtime.python_command)
        if (-not $command -or $command.Count -eq 0) {
            return $false
        }
        $pythonExe = [string]$command[0]
        $pythonArgs = @()
        if ($command.Count -gt 1) {
            $pythonArgs = @($command[1..($command.Count - 1)])
        }
        & $pythonExe @pythonArgs -c "import sys" 2>$null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
}

if (-not (Test-RuntimeConfig)) {
    $bootstrapResultRaw = & powershell -NoProfile -ExecutionPolicy Bypass -File $Bootstrap -InstallIfMissing
    if ($LASTEXITCODE -ne 0) {
        Write-Error "007AI skill environment initialization failed: $bootstrapResultRaw"
        exit $LASTEXITCODE
    }
}

$runtime = Get-Content -Raw -LiteralPath $RuntimeConfig | ConvertFrom-Json
$command = @($runtime.python_command)
if (-not $command -or $command.Count -eq 0) {
    Write-Error "runtime.json is missing python_command. Re-run bootstrap_environment.ps1."
    exit 1
}

$pythonExe = [string]$command[0]
$pythonArgs = @()
if ($command.Count -gt 1) {
    $pythonArgs = @($command[1..($command.Count - 1)])
}

& $pythonExe @pythonArgs $Generator @RemainingArgs
exit $LASTEXITCODE
