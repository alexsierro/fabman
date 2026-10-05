$GitBash = "C:\Program Files\Git\bin\bash.exe"
# Forward slashes so `dirname "$0"` works inside the bash script.
& $GitBash ((Join-Path $PSScriptRoot "pull_prod_data.sh") -replace '\\', '/')
exit $LASTEXITCODE
