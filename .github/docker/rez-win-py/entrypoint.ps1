#
# Entrypoint that installs given python version and runs tests from commit.
#
# $repo is the repository like 'nerdvegas/rez'
# $commit is the revision to test
param( $repo, $commit )

# Stop on errors; .exe has to be checked manually
Set-StrictMode -Version latest
$ErrorActionPreference = "Stop"

echo "Testing $repo at $commit"

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

# Clone repo
git clone https://github.com/$repo rez
if (-not $?) {exit 1}
cd rez
git checkout $commit
if (-not $?) {exit 1}

# Install rez
mkdir build
python install.py build
if (-not $?) {exit 1}

# Run Rez Tests
#
.\build\Scripts\rez\rez-selftest.exe

# Pass on exit code to runner
exit $LASTEXITCODE
