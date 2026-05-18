#!/bin/bash
# =============================================================================
# pyMC_WM1303 One-Line Installer / Upgrade Bootstrap (with Region+Preset Wizard)
# =============================================================================
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/HansvanMeer/pyMC_WM1303/main/bootstrap.sh | sudo bash
#
# Optional environment overrides (skip interactive prompts):
#   WM1303_REGION=EU868|US915|AU915|AS923|IN865|JP920|KR920|CUSTOM
#   WM1303_PRESET=<preset-name-from-presets.json>
#   WM1303_SYNC_WORD=private|public|<hex>   (device-wide LoRa network sync word;
#                                            hex example: 0x1234; default: private)
#
# Optional flag:
#   --non-interactive   skip all wizard prompts, fall back to EU-Default preset
#
# This script:
#   1. Installs git + jq (if not present)
#   2. Clones or updates the pyMC_WM1303 repository
#   3. On NEW install only: runs an interactive wizard to choose region + preset
#      and writes /etc/pymc_repeater/wm1303_ui.json with those defaults.
#   4. Detects existing installation:
#      - New install: runs install.sh
#      - Existing install: runs upgrade.sh (wizard is SKIPPED to preserve config)
# =============================================================================

set -e

REPO_URL="https://github.com/HansvanMeer/pyMC_WM1303.git"
INSTALL_DIR="/home/pi/pyMC_WM1303"
PI_USER="pi"
CONFIG_DIR="/etc/pymc_repeater"
UI_JSON="${CONFIG_DIR}/wm1303_ui.json"

# --- Parse --non-interactive flag (also honoured if stdin is not a TTY) ------
NON_INTERACTIVE=0
for arg in "$@"; do
    if [ "${arg}" = "--non-interactive" ] || [ "${arg}" = "-y" ]; then
        NON_INTERACTIVE=1
    fi
done
if [ ! -t 0 ]; then
    # stdin is not a TTY (e.g. piped from curl). Wizard becomes non-interactive
    # unless env vars are explicitly set; we still respect WM1303_REGION/WM1303_PRESET.
    NON_INTERACTIVE=1
fi

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

# Install jq if not present (used by the wizard for JSON merging)
if ! command -v jq &>/dev/null; then
    echo "  ℹ Installing jq..."
    apt-get install -y -qq jq
    echo "  ✓ jq installed"
else
    echo "  ✓ jq already available"
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
# Detect existing installation up-front (we need this for wizard skip logic)
# ---------------------------------------------------------------------------
IS_UPGRADE=0
if [ -d "/opt/pymc_repeater" ] && systemctl is-enabled pymc-repeater &>/dev/null; then
    IS_UPGRADE=1
fi

# ---------------------------------------------------------------------------
# Wizard: choose regulatory region + channel preset (new installs only)
# ---------------------------------------------------------------------------
run_wizard() {
    local presets_file="${INSTALL_DIR}/config/presets.json"
    if [ ! -f "${presets_file}" ]; then
        echo "  ⚠ presets.json not found at ${presets_file}, skipping wizard"
        return 0
    fi

    echo ""
    echo "  ╔══════════════════════════════════════════════════════════╗"
    echo "  ║  Installation Wizard: Region + Preset selection          ║"
    echo "  ╚══════════════════════════════════════════════════════════╝"
    echo ""

    # Build region list from presets.json (unique region codes)
    local regions
    regions=$(jq -r '.presets[].region' "${presets_file}" | sort -u)
    if [ -z "${regions}" ]; then
        echo "  ⚠ No regions found in presets.json, falling back to EU868/EU-Default"
        WM1303_REGION="${WM1303_REGION:-EU868}"
        WM1303_PRESET="${WM1303_PRESET:-EU-Default}"
        write_wizard_config
        return 0
    fi

    # --- Region selection -------------------------------------------------
    if [ -n "${WM1303_REGION}" ]; then
        echo "  ✓ Region from env: ${WM1303_REGION}"
    elif [ "${NON_INTERACTIVE}" -eq 1 ]; then
        WM1303_REGION="EU868"
        echo "  ℹ Non-interactive mode: defaulting region to EU868"
    else
        echo "  Available regions:"
        local i=1
        local region_arr=()
        while IFS= read -r rg; do
            region_arr+=("${rg}")
            echo "    ${i}) ${rg}"
            i=$((i+1))
        done <<< "${regions}"
        echo ""
        read -rp "  Select region [1-${#region_arr[@]}, default 1=EU868]: " reg_choice
        reg_choice=${reg_choice:-1}
        if ! [[ "${reg_choice}" =~ ^[0-9]+$ ]] || [ "${reg_choice}" -lt 1 ] || [ "${reg_choice}" -gt "${#region_arr[@]}" ]; then
            echo "  ⚠ Invalid choice, defaulting to EU868"
            WM1303_REGION="EU868"
        else
            WM1303_REGION="${region_arr[$((reg_choice-1))]}"
        fi
    fi
    echo "  ► Selected region: ${WM1303_REGION}"

    # --- Preset selection -------------------------------------------------
    local presets_for_region
    presets_for_region=$(jq -r --arg rg "${WM1303_REGION}" '.presets[] | select(.region==$rg) | .name' "${presets_file}")
    if [ -z "${presets_for_region}" ]; then
        echo "  ⚠ No presets for region ${WM1303_REGION}, using EU-Default"
        WM1303_PRESET="EU-Default"
    else
        if [ -n "${WM1303_PRESET}" ]; then
            echo "  ✓ Preset from env: ${WM1303_PRESET}"
        elif [ "${NON_INTERACTIVE}" -eq 1 ]; then
            WM1303_PRESET=$(echo "${presets_for_region}" | head -n1)
            echo "  ℹ Non-interactive mode: using first preset for ${WM1303_REGION}: ${WM1303_PRESET}"
        else
            echo ""
            echo "  Available presets for ${WM1303_REGION}:"
            local j=1
            local preset_arr=()
            while IFS= read -r pr; do
                preset_arr+=("${pr}")
                local desc
                desc=$(jq -r --arg n "${pr}" '.presets[] | select(.name==$n) | .description // ""' "${presets_file}")
                echo "    ${j}) ${pr} — ${desc}"
                j=$((j+1))
            done <<< "${presets_for_region}"
            echo ""
            read -rp "  Select preset [1-${#preset_arr[@]}, default 1]: " pr_choice
            pr_choice=${pr_choice:-1}
            if ! [[ "${pr_choice}" =~ ^[0-9]+$ ]] || [ "${pr_choice}" -lt 1 ] || [ "${pr_choice}" -gt "${#preset_arr[@]}" ]; then
                echo "  ⚠ Invalid choice, using first preset"
                WM1303_PRESET="${preset_arr[0]}"
            else
                WM1303_PRESET="${preset_arr[$((pr_choice-1))]}"
            fi
        fi
    fi
    echo "  ► Selected preset: ${WM1303_PRESET}"

    # --- Device-wide LoRa network Sync Word ------------------------------
    # WM1303_SYNC_WORD env var accepts only 'private' or 'public'.
    # SX1302 hardware supports ONLY these two values via the board-level
    # lorawan_public flag (lgw_conf_board_t). Custom sync words are NOT
    # hardware-supported and any invalid value falls back to Private.
    WM1303_SYNC_WORD_MODE="private"
    WM1303_SYNC_WORD_VALUE=5156   # 0x1424 Private
    if [ -n "${WM1303_SYNC_WORD}" ]; then
        local _sw_in
        _sw_in=$(echo "${WM1303_SYNC_WORD}" | tr '[:upper:]' '[:lower:]')
        case "${_sw_in}" in
            private)
                WM1303_SYNC_WORD_MODE="private"; WM1303_SYNC_WORD_VALUE=5156 ;;
            public)
                WM1303_SYNC_WORD_MODE="public"; WM1303_SYNC_WORD_VALUE=13380 ;;
            *)
                echo "  ⚠ Invalid WM1303_SYNC_WORD='${WM1303_SYNC_WORD}' (only 'private' or 'public' supported), falling back to Private (0x1424)" ;;
        esac
        echo "  ✓ Sync word from env: ${WM1303_SYNC_WORD_MODE} (value=${WM1303_SYNC_WORD_VALUE})"
    elif [ "${NON_INTERACTIVE}" -eq 1 ]; then
        echo "  ℹ Non-interactive mode: defaulting sync word to Private (0x1424)"
    else
        echo ""
        echo "  LoRa Network Sync Word (device-wide):"
        echo "    1) Private (0x1424, default)  [most networks incl. MeshCore]"
        echo "    2) Public  (0x3444)           [LoRaWAN public networks]"
        echo ""
        read -rp "  Select sync word [1-2, default 1=Private]: " sw_choice
        sw_choice=${sw_choice:-1}
        case "${sw_choice}" in
            1)
                WM1303_SYNC_WORD_MODE="private"; WM1303_SYNC_WORD_VALUE=5156 ;;
            2)
                WM1303_SYNC_WORD_MODE="public"; WM1303_SYNC_WORD_VALUE=13380 ;;
            *)
                echo "  ⚠ Invalid choice, falling back to Private (0x1424)"
                WM1303_SYNC_WORD_MODE="private"; WM1303_SYNC_WORD_VALUE=5156 ;;
        esac
    fi
    printf "  ► Selected sync word: %s (0x%04X)\n" "${WM1303_SYNC_WORD_MODE}" "${WM1303_SYNC_WORD_VALUE}"

    write_wizard_config
}

# Write wizard output to /etc/pymc_repeater/wm1303_ui.json by merging the
# preset's channel/channel_e/channel_f defaults plus the chosen region into
# the template wm1303_ui.json. install.sh's "copy template if missing" step
# will then leave our wizard-written file untouched.
write_wizard_config() {
    local presets_file="${INSTALL_DIR}/config/presets.json"
    local template="${INSTALL_DIR}/config/wm1303_ui.json"
    if [ ! -f "${template}" ]; then
        echo "  ⚠ Template wm1303_ui.json missing, cannot write wizard config"
        return 0
    fi
    mkdir -p "${CONFIG_DIR}"

    # Extract the chosen preset object
    local preset_obj
    preset_obj=$(jq --arg n "${WM1303_PRESET}" '.presets[] | select(.name==$n)' "${presets_file}")
    if [ -z "${preset_obj}" ] || [ "${preset_obj}" = "null" ]; then
        echo "  ⚠ Preset '${WM1303_PRESET}' not found in presets.json; using template defaults"
        cp "${template}" "${UI_JSON}"
        # Still apply region + device-wide sync_word
        jq --arg code "${WM1303_REGION}" \
           --arg sw_mode "${WM1303_SYNC_WORD_MODE}" \
           --argjson sw_value "${WM1303_SYNC_WORD_VALUE}" \
           '.region = {"code": $code, "tx_freq_min": null, "tx_freq_max": null}
            | .sync_word = {"value": $sw_value, "mode": $sw_mode}' \
           "${UI_JSON}" > "${UI_JSON}.tmp" && mv "${UI_JSON}.tmp" "${UI_JSON}"
        chown ${PI_USER}:${PI_USER} "${UI_JSON}"
        echo "  ✓ Wrote ${UI_JSON} (region + sync_word only, default preset)"
        return 0
    fi

    # Build merged config: template + preset channels/channel_e/channel_f + region + sync_word.
    # sync_word is DEVICE-WIDE (top-level), never per-channel. We always write
    # the wizard-selected sync_word, ignoring any leftover per-channel values
    # from older presets.
    local merged
    merged=$(jq -n \
        --slurpfile tpl "${template}" \
        --argjson preset "${preset_obj}" \
        --arg region_code "${WM1303_REGION}" \
        --arg sw_mode "${WM1303_SYNC_WORD_MODE}" \
        --argjson sw_value "${WM1303_SYNC_WORD_VALUE}" \
        '
        ($tpl[0]) as $t
        | $t
          + ({"channels": ($preset.channels // $t.channels)})
          + ({"channel_e": ($preset.channel_e // $t.channel_e)})
          + ({"channel_f": ($preset.channel_f // $t.channel_f)})
          + ({"region": {"code": $region_code, "tx_freq_min": null, "tx_freq_max": null}})
          + ({"sync_word": {"value": $sw_value, "mode": $sw_mode}})
        ')

    echo "${merged}" > "${UI_JSON}"
    chown ${PI_USER}:${PI_USER} "${UI_JSON}"
    printf "  ✓ Wrote %s with region=%s, preset=%s, sync_word=%s (0x%04X)\n" \
        "${UI_JSON}" "${WM1303_REGION}" "${WM1303_PRESET}" \
        "${WM1303_SYNC_WORD_MODE}" "${WM1303_SYNC_WORD_VALUE}"
}

if [ "${IS_UPGRADE}" -eq 0 ]; then
    if [ -f "${UI_JSON}" ]; then
        echo "  ℹ Existing ${UI_JSON} found — skipping wizard to preserve config"
    else
        run_wizard
    fi
else
    echo "  ℹ Upgrade detected — wizard skipped, existing config preserved"
fi

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

if [ "${IS_UPGRADE}" -eq 1 ]; then
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
