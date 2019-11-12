#
# Entrypoint that installs given python version and runs tests.
#

# Stop on errors; .exe has to be checked manually
Set-StrictMode -Version latest
$ErrorActionPreference = "Stop"

# Fixes encoding issue on Windows 10 local docker run.
#
${ENV:PYTHONIOENCODING} = "UTF-8"

# Verify Python
#
python --version
if (-not $?) {exit 1}

# Verify cmake
#
cmake.exe --version
if (-not $?) {exit 1}

#Verify pwsh
pwsh --version
if (-not $?) {exit 1}

#Verify git
git --version
if (-not $?) {exit 1}

# Install rez
# Note that the workflow's checkout has been bind mounted to /checkout
mkdir build
python .\checkout\install.py build
if (-not $?) {exit 1}

# Run Rez Tests
#
.\build\Scripts\rez\rez-selftest.exe

# Pass on exit code to runner
exit $LASTEXITCODE
