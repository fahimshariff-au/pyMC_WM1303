#!/bin/bash
# =============================================================================
# pyMC_WM1303 One-Line Installer Bootstrap
# =============================================================================
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/HansvanMeer/pyMC_WM1303/main/bootstrap.sh | sudo bash
#
# This script:
#   1. Installs git (if not present)
#   2. Clones the pyMC_WM1303 repository
#   3. Runs the full installation script
# =============================================================================

set -e

REPO_URL="https://github.com/HansvanMeer/pyMC_WM1303.git"
INSTALL_DIR="/home/pi/pyMC_WM1303"

echo ""
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║     pyMC_WM1303 One-Line Installer                     ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo ""

# Ensure running as root
if [ "$(id -u)" -ne 0 ]; then
    echo "  ✗ This script must be run as root (use sudo)"
    exit 1
fi

# Install git if not present
if ! command -v git &>/dev/null; then
    echo "  ℹ Installing git..."
    apt-get update -qq
    apt-get install -y -qq git
    echo "  ✓ git installed"
else
    echo "  ✓ git already available"
fi

# Clone or update repository
if [ -d "${INSTALL_DIR}" ]; then
    echo "  ℹ Repository already exists, pulling latest changes..."
    cd "${INSTALL_DIR}"
    git pull
    echo "  ✓ Repository updated"
else
    echo "  ℹ Cloning repository..."
    git clone "${REPO_URL}" "${INSTALL_DIR}"
    echo "  ✓ Repository cloned"
fi

# Run installation
echo ""
echo "  ℹ Starting installation..."
echo ""
cd "${INSTALL_DIR}"
bash install.sh
