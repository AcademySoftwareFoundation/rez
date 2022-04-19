#
# Entrypoint that installs given python version and runs tests.
#

# Stop on errors; .exe has to be checked manually
Set-StrictMode -Version latest
$ErrorActionPreference = "Stop"

# Fixes encoding issue on Windows 10 local docker run.
#
${ENV:PYTHONIOENCODING} = "UTF-8"

# Print name of image being run, for debugging purposes
Write-Output "Using docker image ${ENV:_IMAGE_NAME}"

# Verify Python
Write-Output "python found at $((Get-Command python).Path)"
python --version
if (-not $?) {exit 1}

# Verify cmake
Write-Output "cmake found at $((Get-Command cmake).Path)"
cmake.exe --version
if (-not $?) {exit 1}

# Verify pwsh
Write-Output "pwsh found at $((Get-Command pwsh).Path)"
pwsh --version
if (-not $?) {exit 1}

# Verify git
Write-Output "git found at $((Get-Command git).Path)"
git --version
if (-not $?) {exit 1}

# Verify git-bash
Write-Output "bash (via Git for windows) found at $((Get-Command bash).Path)"
bash --version
if (-not $?) {exit 1}

# Install rez
# Note that the workflow's checkout has been bind mounted to /checkout
mkdir build
python .\checkout\install.py build
if (-not $?) {exit 1}

# Install pytest for better rez-selftest output
.\build\Scripts\rez\rez-python -m pip install pytest-cov
.\build\Scripts\rez\rez-python -m pip install parameterized

# Run Rez Tests
.\build\Scripts\rez\rez-selftest.exe -v

# Pass on exit code to runner
exit $LASTEXITCODE
