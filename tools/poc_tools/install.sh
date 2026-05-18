#!/bin/bash

set -e

PYTHON_PATH="python3.11"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Starting poc_tools installation..."

if [ "$(id -u)" != "0" ]; then
    echo -e "\033[31mError: This script must be run as root or with sudo!\033[0m" >&2
    exit 1
fi

echo "Creating directory structure..."
mkdir -p "/usr/lib/${PYTHON_PATH}/site-packages/poc_tools"
mkdir -p "/etc/poc_tools"
mkdir -p "/var/log/poc_tools"
mkdir -p "/etc/poc_tools/xml"
mkdir -p "/usr/bin"

echo "Copying files..."
cp -r "${SCRIPT_DIR}/"* "/usr/lib/${PYTHON_PATH}/site-packages/poc_tools/"
cp -f "${SCRIPT_DIR}/common/poc_tools.toml" "/etc/poc_tools/poc_tools.toml"
cp -f "${SCRIPT_DIR}/poc_tools" "/usr/bin/poc_tools"

echo "Setting permissions..."
chmod -R 0750 "/usr/lib/${PYTHON_PATH}/site-packages/poc_tools"
chmod -R 0750 "/var/log/poc_tools"
chmod -R 0750 "/etc/poc_tools"
chmod 0400 "/etc/poc_tools/poc_tools.toml"
chmod 0750 "/usr/bin/poc_tools"

find "/usr/lib/${PYTHON_PATH}/site-packages/poc_tools" \
    -type f \( -name "*.py" -o -name "*.service" -o -name "*.proto" -o -name "*.toml" \) \
    -exec chmod 0400 {} + 2>/dev/null || true

echo "Installation completed successfully!"
echo ""
echo "Installed paths:"
echo "  - Python package: /usr/lib/${PYTHON_PATH}/site-packages/poc_tools"
echo "  - Config file: /etc/poc_tools/poc_tools.toml"
echo "  - Executable: /usr/bin/poc_tools"
echo "  - Log directory: /var/log/poc_tools"