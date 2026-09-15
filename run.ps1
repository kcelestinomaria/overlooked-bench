# overlooked-bench - one command to run the whole pipeline.
#
#   .\run.ps1                      # full run, today's date as the run id
#   .\run.ps1 --run-id 2026-10-01  # ...or a specific run id
#   .\run.ps1 doctor               # check environment before a long run
#
# Any argument that is not a known subcommand is passed through to `obench.py run`.

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (Test-Path ".venv\Scripts\python.exe") {
    $py = ".\.venv\Scripts\python.exe"
} elseif (Test-Path ".venv/bin/python") {
    $py = "./.venv/bin/python"
} else {
    Write-Host "No virtualenv found. Create one first:"
    Write-Host "  python -m venv .venv"
    Write-Host "  .venv\Scripts\pip install -r requirements.txt"
    exit 1
}

$known = @("run", "eval", "charts", "social", "readme", "site", "validate", "doctor")
if ($args.Count -eq 0) {
    & $py obench.py run
} elseif ($known -contains $args[0]) {
    & $py obench.py @args
} else {
    & $py obench.py run @args
}
exit $LASTEXITCODE
