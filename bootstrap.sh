#!/bin/bash
# =============================================================================
# pyMC_WM1303 One-Line Installer / Upgrade Bootstrap
# =============================================================================
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/HansvanMeer/pyMC_WM1303/main/bootstrap.sh | sudo bash
#
# This script:
#   1. Installs git (if not present)
#   2. Clones or updates the pyMC_WM1303 repository
#   3. Detects existing installation:
#      - New install: runs install.sh
#      - Existing install: runs upgrade.sh
# =============================================================================

set -e

REPO_URL="https://github.com/fahimshariff-au/pyMC_WM1303.git"
INSTALL_DIR="/home/pi/pyMC_WM1303"
PI_USER="pi"

echo ""
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║     pyMC_WM1303 Bootstrap                                ║"
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

# Fix git 'dubious ownership' error (CVE-2022-24765)
git config --global --add safe.directory "${INSTALL_DIR}" 2>/dev/null
sudo -u ${PI_USER} git config --global --add safe.directory "${INSTALL_DIR}" 2>/dev/null

# Clone or update repository
if [ -d "${INSTALL_DIR}/.git" ]; then
    echo "  ℹ Repository already exists, pulling latest changes..."
    chown -R ${PI_USER}:${PI_USER} "${INSTALL_DIR}"
    cd "${INSTALL_DIR}"
    sudo -u ${PI_USER} git fetch origin
    sudo -u ${PI_USER} git reset --hard origin/main
    sudo -u ${PI_USER} git clean -fd
    echo "  ✓ Repository updated"
else
    echo "  ℹ Cloning repository..."
    sudo -u ${PI_USER} git clone "${REPO_URL}" "${INSTALL_DIR}"
    echo "  ✓ Repository cloned"
fi

cd "${INSTALL_DIR}"

# ---------------------------------------------------------------------------
# SSH timeout protection: run install/upgrade with nohup so the process
# survives if the SSH session disconnects (HAL build can take >10 minutes).
# Output is logged and tailed so the user still sees live progress.
# ---------------------------------------------------------------------------
BOOTSTRAP_LOG="/tmp/wm1303_bootstrap.log"
rm -f "${BOOTSTRAP_LOG}"

run_protected() {
    local script="$1"
    echo "  ℹ Running ${script} (nohup-protected against SSH timeout)..."
    echo "  ℹ Log: ${BOOTSTRAP_LOG}"
    nohup bash "${script}" > "${BOOTSTRAP_LOG}" 2>&1 &
    BGPID=$!
    tail -f "${BOOTSTRAP_LOG}" &
    TAILPID=$!
    wait $BGPID
    EXIT_CODE=$?
    kill $TAILPID 2>/dev/null
    wait $TAILPID 2>/dev/null
    return $EXIT_CODE
}

# Detect existing installation
if [ -d "/opt/pymc_repeater" ] && systemctl is-enabled pymc-repeater &>/dev/null; then
    echo ""
    echo "  ╔══════════════════════════════════════════════════════════╗"
    echo "  ║  Existing installation detected — running UPGRADE        ║"
    echo "  ╚══════════════════════════════════════════════════════════╝"
    echo ""
    run_protected upgrade.sh
else
    echo ""
    echo "  ╔══════════════════════════════════════════════════════════╗"
    echo "  ║  No installation found — running INSTALL                 ║"
    echo "  ╚══════════════════════════════════════════════════════════╝"
    echo ""
    run_protected install.sh
fi
