# escape=`

# Please Note: Any " requires \" in the Dockerfile for windows.

# The windows version has to match the host system.
# 1809 ->	10.0.17763.805 -> windows-2019
# Compare: https://hub.docker.com/_/microsoft-windows-servercore
ARG WINDOWS_VERSION=1809-amd64

FROM mcr.microsoft.com/windows/servercore:$WINDOWS_VERSION

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
RUN iex ((new-object net.webclient).DownloadString('https://chocolatey.org/install.ps1'));             `
    choco feature disable --name showDownloadProgress;                                                 `
    choco install git.install --yes --version=${ENV:GIT_VERSION};                                      `
    choco install cmake --yes --version=${ENV:CMAKE_VERSION} --installargs 'ADD_CMAKE_TO_PATH=System'; `
    choco install pwsh --yes --version=${PWSH_VERSION};                                                `
    choco install --yes choco-cleaner;                                                                 `
    C:\ProgramData\chocolatey\bin\choco-cleaner.ps1;                                                   `
    choco uninstall --yes choco-cleaner

ENTRYPOINT ["powershell.exe", "-NoLogo", "-ExecutionPolicy", "ByPass"]
