#!/bin/bash
# =============================================================================
# SPI Bus Stability Optimizer for WM1303
# =============================================================================
# Called at service start (ExecStartPre) to apply runtime SPI optimizations.
# These settings are not persistent across reboots, so they must be re-applied.
#
# Optimizations applied:
#   1. CPU governor -> performance (all cores)
#   2. SPI polling_limit_us -> 250 (eliminates interrupt-mode jitter gap)
#   3. RT scheduling for spi0 kernel thread (multi-core systems)
#
# Note: core_freq_min=500 and spidev.bufsiz=32768 are set in boot config
# and persist across reboots. They are NOT handled here.
# =============================================================================

LOG_TAG="spi-optimize"

log_info() {
    echo "[${LOG_TAG}] $1"
    logger -t "${LOG_TAG}" "$1" 2>/dev/null || true
}

log_warn() {
    echo "[${LOG_TAG}] WARNING: $1" >&2
    logger -t "${LOG_TAG}" -p user.warning "$1" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# 1. CPU Governor -> performance
# ---------------------------------------------------------------------------
set_cpu_governor() {
    local target="performance"
    local changed=0
    local total=0

    for gov_file in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
        [ -f "$gov_file" ] || continue
        total=$((total + 1))
        current=$(cat "$gov_file" 2>/dev/null)
        if [ "$current" != "$target" ]; then
            echo "$target" > "$gov_file" 2>/dev/null && changed=$((changed + 1))
        fi
    done

    if [ $total -eq 0 ]; then
        log_warn "No CPU governor files found"
    elif [ $changed -gt 0 ]; then
        log_info "CPU governor: set to '${target}' on ${changed}/${total} cores"
    else
        log_info "CPU governor: already '${target}' on all ${total} cores"
    fi
}

# ---------------------------------------------------------------------------
# 2. SPI polling_limit_us -> 250
# ---------------------------------------------------------------------------
set_spi_polling_limit() {
    local target=250
    local param_file="/sys/module/spi_bcm2835/parameters/polling_limit_us"

    if [ ! -f "$param_file" ]; then
        log_warn "SPI polling_limit_us parameter not found (spi_bcm2835 not loaded?)"
        return
    fi

    current=$(cat "$param_file" 2>/dev/null)
    if [ "$current" != "$target" ]; then
        echo "$target" > "$param_file" 2>/dev/null
        log_info "SPI polling_limit_us: ${current} -> ${target}"
    else
        log_info "SPI polling_limit_us: already ${target}"
    fi
}

# ---------------------------------------------------------------------------
# 3. RT scheduling for spi0 kernel thread (multi-core only)
# ---------------------------------------------------------------------------
set_spi_rt_priority() {
    local num_cores
    num_cores=$(nproc 2>/dev/null || echo 1)

    if [ "$num_cores" -lt 2 ]; then
        log_info "SPI RT priority: skipped (single-core system)"
        return
    fi

    # Find the spi0 kernel thread
    local spi_pid
    spi_pid=$(pgrep -x spi0 2>/dev/null | head -1)

    if [ -z "$spi_pid" ]; then
        log_warn "SPI RT priority: spi0 kernel thread not found"
        return
    fi

    # Check current scheduling policy
    local current_policy
    current_policy=$(chrt -p "$spi_pid" 2>/dev/null | grep -o 'SCHED_[A-Z]*' | head -1)

    if [ "$current_policy" = "SCHED_FIFO" ]; then
        log_info "SPI RT priority: spi0 (PID ${spi_pid}) already SCHED_FIFO"
    else
        if chrt -f -p 91 "$spi_pid" 2>/dev/null; then
            log_info "SPI RT priority: spi0 (PID ${spi_pid}) set to SCHED_FIFO:91"
        else
            log_warn "SPI RT priority: failed to set SCHED_FIFO on spi0 (PID ${spi_pid})"
        fi
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
log_info "Applying SPI bus stability optimizations..."
set_cpu_governor
set_spi_polling_limit
set_spi_rt_priority
log_info "SPI optimization complete"
