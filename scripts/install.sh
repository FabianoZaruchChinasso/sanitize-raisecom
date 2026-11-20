#!/bin/bash
set -euo pipefail

_SCRIPT_DIR_="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_SOURCE_DIR_="$(cd "${_SCRIPT_DIR_}/.." && pwd)"
_PATH_=/etc/sanitize
_EXECUTABLE_=/usr/bin/sanitize-3
_SCRIPT_TARGET_="${_PATH_}/sanitize-3.py"

trap 'echo "Error managing sanitize-3. Aborting"; exit 1;' ERR

function check_installation {
    if [ -d "$_PATH_" ] && [ -f "$_SCRIPT_TARGET_" ] && [ -L "$_EXECUTABLE_" ]; then
        echo "sanitize-3 is already installed."
        return 0
    else
        echo "sanitize-3 is not installed."
        return 1
    fi
}

function confirm {
    local action="$1"
    echo "${action} sanitize-3 for user $(whoami). Proceed? [y/n]: "
    read -r confirmation

    if [[ "$confirmation" != "y" && "$confirmation" != "Y" ]]; then
        echo "${action^} aborted."
        exit 1
    fi
}

function copy_files {
    sudo mkdir -p "${_PATH_}/config" "${_PATH_}/scripts"
    sudo install -m 0755 "${_SOURCE_DIR_}/sanitize-3.py" "${_SCRIPT_TARGET_}"
    sudo cp -a "${_SOURCE_DIR_}/config/." "${_PATH_}/config/"
    sudo cp -a "${_SOURCE_DIR_}/scripts/." "${_PATH_}/scripts/"
    sudo ln -sfn "$_SCRIPT_TARGET_" "$_EXECUTABLE_"
}

function install {
    if check_installation; then
        echo "sanitize-3 is already installed. Use '$0 update' to update it."
        exit 1
    fi
    confirm "Installing"
    copy_files
    echo "sanitize-3 installed successfully."
}

function update {
    if ! check_installation; then
        echo "Install sanitize-3 first with '$0 install'."
        exit 1
    fi
    confirm "Updating"
    copy_files
    echo "sanitize-3 updated successfully."
}

function uninstall {
    if ! check_installation; then
        echo "sanitize-3 is not installed."
        exit 0
    fi
    confirm "Uninstalling"
    sudo rm -f "$_EXECUTABLE_"
    sudo rm -rf "$_PATH_"
    echo "sanitize-3 uninstalled successfully."
}

function usage {
    cat <<EOF
Usage: $0 [install|update|uninstall]

  install    Install sanitize-3 (default)
  update     Replace the installed script, configuration, and helper scripts
  uninstall  Remove /usr/bin/sanitize-3 and /etc/sanitize
EOF
}

function main {
    local action="${1:-install}"
    case "$action" in
        install) install ;;
        update) update ;;
        uninstall) uninstall ;;
        -h|--help) usage ;;
        *) usage >&2; exit 2 ;;
    esac
}

main "$@"
