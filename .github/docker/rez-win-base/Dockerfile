# escape=`

# Please Note: Any " requires \" in the Dockerfile for windows.

ARG WINDOWS_VERSION
FROM mcr.microsoft.com/windows/servercore:$WINDOWS_VERSION

LABEL org.opencontainers.image.description="WARNING: This is an internal image and should not be used outside of the rez repository!"

SHELL ["powershell.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "ByPass"]

ARG GIT_VERSION=2.23.0
ARG CMAKE_VERSION=3.15.4
ARG PWSH_VERSION=6.2.2

# ------------------------------------------------------------------------------------------------------------
# Install:
# - Chocolatey
# - Git
# - Cmake
# - PowerShellCore
#
ENV chocolateyUseWindowsCompression false
RUN iex ((new-object net.webclient).DownloadString('https://chocolatey.org/install.ps1')); `
    choco feature disable --name showDownloadProgress; `
    choco install git.install --yes --version=${ENV:GIT_VERSION}; `
    choco install cmake --yes --version=${ENV:CMAKE_VERSION} --installargs 'ADD_CMAKE_TO_PATH=System'; `
    choco install pwsh --yes --version=${PWSH_VERSION}; `
    choco install --yes choco-cleaner; `
    C:\ProgramData\chocolatey\bin\choco-cleaner.bat; `
    choco uninstall --yes choco-cleaner

ENTRYPOINT ["powershell.exe", "-NoLogo", "-ExecutionPolicy", "ByPass"]
