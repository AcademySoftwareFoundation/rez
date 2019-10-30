# escape=`

# Please Note: Any " requires \" in the Dockerfile for windows.

# The windows version has to match the host system.
# 1809 ->	10.0.17763.805 -> windows-2019
# Compare: https://hub.docker.com/_/microsoft-windows-servercore
ARG WINDOWS_VERSION=1809-amd64

FROM mcr.microsoft.com/windows/servercore:$WINDOWS_VERSION

SHELL ["powershell.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "ByPass"]

# ------------------------------------------------------------------------------------------------------------
# Chocolatey
#
ENV chocolateyUseWindowsCompression false
RUN iex ((new-object net.webclient).DownloadString('https://chocolatey.org/install.ps1'))
RUN choco feature disable --name showDownloadProgress

# ------------------------------------------------------------------------------------------------------------
# Git
#
RUN choco install git.install --yes --version=2.23.0

# ------------------------------------------------------------------------------------------------------------
# Cmake
#
RUN choco install cmake --yes --version=3.15.4 --installargs 'ADD_CMAKE_TO_PATH=System'

# ------------------------------------------------------------------------------------------------------------
# pwsh (PowerShellCore)
#
RUN choco install pwsh --yes --version=6.2.2

ENTRYPOINT ["powershell.exe", "-NoLogo", "-ExecutionPolicy", "ByPass"]
