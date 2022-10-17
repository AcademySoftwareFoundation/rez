# escape=`

ARG BASE_IMAGE_NAME
FROM $BASE_IMAGE_NAME

LABEL org.opencontainers.image.description="WARNING: This is an internal image and should not be used outside of the rez repository!"

# Name of this image
ARG IMAGE_NAME
ENV _IMAGE_NAME=$IMAGE_NAME

# NOTE: Any " requires \" in the Dockerfile for windows.
# NOTE: The order matters. ARG after the shell command will allow access via
# the PowerShell environment like ${ENV:PYTHON_VERSION}.
SHELL ["powershell.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "ByPass"]

# Python version to install (full chocolatey compatible version required)
# For example: 3.7.5
#
ARG PYTHON_VERSION


# ------------------------------------------------------------------------------------------------------------
# Python
#
# Installs given Python version to C:\Python
# Python 2.x uses msi while 3.x has an exe with separate arguments
# Verifies the installation by running python explicitly and via `python`
#
RUN ${PYTHON_INSTALL_PATH} = 'C:\Python'; `
    ${PYTHON_MAJOR_VERSION} = ${ENV:PYTHON_VERSION}.Split('.')[0]; `
    if (${PYTHON_MAJOR_VERSION} -eq "2") { `
        ${INSTALLARGS} = \"'/qn /norestart ADDLOCAL=ALL ALLUSERS=1 TARGETDIR=`\"\" + ${PYTHON_INSTALL_PATH} + \"`\"'\"; `
    } else { `
        ${INSTALLARGS} = \"'/quiet InstallAllUsers=1 PrependPath=1 TargetDir=`\"\" + ${PYTHON_INSTALL_PATH} + \"`\"'\"; `
    } `
    choco install python${PYTHON_MAJOR_VERSION} --yes --version=\"${ENV:PYTHON_VERSION}\" --override --installargs=${INSTALLARGS}; `
    if (-not $?) {exit 1}

# Verify
RUN $python_relative_ver = (& python --version 2>&1).ToString().Trim().Split(" ")[1]; `
    $python_explicit_ver = (& C:\python\python.exe --version 2>&1).ToString().Trim().Split(" ")[1]; `
    if (-not $?) {exit 1}; `
    $python_relative_ver = (& python --version 2>&1).ToString().Trim().Split(" ")[1]; `
    $python_explicit_ver = (& C:\python\python.exe --version 2>&1).ToString().Trim().Split(" ")[1]; `
    if (-not ($python_explicit_ver -eq $python_relative_ver -and $python_explicit_ver -eq ${ENV:PYTHON_VERSION})) {exit 1}


# ------------------------------------------------------------------------------------------------------------
# Git Bash (git for windows)
#
RUN choco install git --yes --params "/GitAndUnixToolsOnPath"


# ------------------------------------------------------------------------------------------------------------
# Cleanup
#
RUN choco install --yes choco-cleaner; `
    C:\ProgramData\chocolatey\bin\choco-cleaner.bat; `
    choco uninstall --yes choco-cleaner


COPY entrypoint.ps1 /entrypoint.ps1

ENTRYPOINT ["powershell.exe", "-NoLogo", "-ExecutionPolicy", "ByPass", "-File", "/entrypoint.ps1"]
