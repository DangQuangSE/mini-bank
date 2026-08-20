param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$ScriptPath,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArgs
)

$ErrorActionPreference = 'Stop'

if ($env:PYTHON -and (Test-Path -LiteralPath $env:PYTHON -PathType Leaf)) {
    $python = $env:PYTHON
} else {
    $python = Get-Command python.exe -All -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -notlike '*\WindowsApps\*' } |
        Select-Object -First 1 -ExpandProperty Source
}

if (-not $python) {
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        & $launcher.Source -3 $ScriptPath @ScriptArgs
        exit $LASTEXITCODE
    }

    [Console]::Error.WriteLine('No usable Python interpreter found. Set PYTHON to a python.exe path.')
    exit 127
}

& $python $ScriptPath @ScriptArgs
exit $LASTEXITCODE
