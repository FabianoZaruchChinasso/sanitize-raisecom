#!/bin/bash
set -euo pipefail

_SCRIPT_DIR_="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_SOURCE_DIR_="$(cd "${_SCRIPT_DIR_}/.." && pwd)"
_PATH_=/etc/sanitize
_EXECUTABLE_=/usr/bin/sanitize-3
_SCRIPT_TARGET_="${_PATH_}/sanitize-3.py"

trap 'echo "Error installing sanitize-3. Aborting"; exit 1;' ERR

function check_installation {
    if [ -d "$_PATH_" ] && [ -f "$_SCRIPT_TARGET_" ] && [ -L "$_EXECUTABLE_" ]; then
        echo "sanitize-3 is already installed."
        return 0
    else
        echo "sanitize-3 is not installed."
        return 1
    fi
}

function install {
    echo "Installing sanitize-3 for user $(whoami). Proceed? [y/n]: "
    read -r confirmation

    # Validate user input
    if [[ "$confirmation" != "y" && "$confirmation" != "Y" ]]; then
        echo "Installation aborted."
        return 1
    fi

    sudo mkdir -p "${_PATH_}/config" "${_PATH_}/scripts"
    sudo install -m 0755 "${_SOURCE_DIR_}/sanitize-3.py" "${_SCRIPT_TARGET_}"
    sudo cp -a "${_SOURCE_DIR_}/config/." "${_PATH_}/config/"
    sudo cp -a "${_SOURCE_DIR_}/scripts/." "${_PATH_}/scripts/"

    sudo ln -sfn "$_SCRIPT_TARGET_" "$_EXECUTABLE_"

    echo "sanitize-3 installed successfully."
}

function main {
    check_installation && echo "sanitize-3 is already installed. Aborting." && exit 1
    install
}

main
