# Repository Information

> Repository structure, fork strategy, overlay approach, and development workflow

## Overview

The WM1303 system is built from four Git repositories: one main project repository and three upstream fork repositories. The forks are kept clean — all WM1303-specific modifications live in the main repository as overlay files that are copied on top of the forks during installation.

## Repositories

### Main Repository

| | |
|---|---|
| **Repository** | [pyMC_WM1303](https://github.com/HansvanMeer/pyMC_WM1303) |
| **Purpose** | Installation scripts, overlay files, configuration templates, documentation |
| **Branch** | `main` |
| **Contains** | `install.sh`, `upgrade.sh`, `overlay/`, `config/`, `docs/`, `README.md` |

This is the repository you clone to install the system. It does not contain the full source code of pyMC_core or pyMC_Repeater — instead, it contains only the modified files (overlays) that are applied on top of the upstream forks.

### Fork Repositories

| Repository | Upstream | Branch | Purpose |
|------------|----------|--------|--------|
| [sx1302_hal](https://github.com/HansvanMeer/sx1302_hal) | Semtech SX1302 HAL | `master` | LoRa concentrator HAL library and packet forwarder |
| [pyMC_core](https://github.com/HansvanMeer/pyMC_core) | MeshCore Python core | `dev` | MeshCore core library with hardware abstraction |
| [pyMC_Repeater](https://github.com/HansvanMeer/pyMC_Repeater) | MeshCore Python Repeater | `dev` | MeshCore repeater application with web UI |

These forks are unmodified copies of the original upstream repositories. No changes are committed directly to these forks.

## Why Forks?

The fork strategy serves several purposes:

1. **Clean upstream tracking** — The forks mirror the original repositories exactly, making it easy to pull upstream changes without merge conflicts.

2. **Independence from upstream availability** — If the original repositories are moved, deleted, or restructured, the forks ensure continued access to the required code.

3. **Controlled updates** — New upstream releases can be reviewed and tested before being integrated, preventing unexpected breaking changes.

4. **Reproducible builds** — By pinning specific branches (`master` for HAL, `dev` for pyMC), installations are reproducible regardless of upstream activity.

## Overlay Approach

Instead of modifying the fork repositories directly, all WM1303-specific changes are maintained as **overlay files** in the main `pyMC_WM1303` repository under the `overlay/` directory.

### How It Works

```
┌───────────────────────────┐
│  pyMC_WM1303 (main repo)  │
│                           │
│  overlay/                 │
│  ├── hal/                 │  ─── Modified HAL source files
│  ├── pymc_core/           │  ─── WM1303 hardware drivers
│  └── pymc_repeater/       │  ─── Bridge engine, API, UI
│                           │
│  install.sh / upgrade.sh  │  ─── Orchestration scripts
└───────────┬───────────────┘
            │
            │  Step 1: Clone forks (unmodified)
            │  Step 2: Copy overlay files on top
            ▼
┌───────────────────────────┐
│  Installation on Pi       │
│                           │
│  /home/pi/sx1302_hal/     │  ← fork + HAL overlay
│  /opt/.../pyMC_core/      │  ← fork + core overlay
│  /opt/.../pyMC_Repeater/  │  ← fork + repeater overlay
└───────────────────────────┘
```

### Step-by-Step Process

During installation (`install.sh` Phase 4-5) or upgrade (`upgrade.sh` Phase 3-4):

1. **Clone or update forks** — The three fork repositories are cloned to the Pi (or pulled if already present). Any local modifications are discarded with `git checkout -- .` to ensure a clean state.

2. **Apply overlay** — Files from `overlay/` are copied on top of the cloned repositories, replacing the upstream versions:

   ```bash
   # HAL overlay (C source modifications)
   cp overlay/hal/libloragw/src/loragw_hal.c     → sx1302_hal/libloragw/src/
   cp overlay/hal/libloragw/src/loragw_sx1302.c   → sx1302_hal/libloragw/src/
   cp overlay/hal/libloragw/inc/loragw_sx1302.h   → sx1302_hal/libloragw/inc/
   cp overlay/hal/packet_forwarder/src/lora_pkt_fwd.c → sx1302_hal/packet_forwarder/src/
   cp overlay/hal/libloragw/Makefile              → sx1302_hal/libloragw/
   cp overlay/hal/packet_forwarder/Makefile       → sx1302_hal/packet_forwarder/

   # pyMC_core overlay (Python hardware drivers)
   cp overlay/pymc_core/.../wm1303_backend.py     → pyMC_core/.../hardware/
   cp overlay/pymc_core/.../sx1302_hal.py          → pyMC_core/.../hardware/
   cp overlay/pymc_core/.../tx_queue.py            → pyMC_core/.../hardware/
   cp overlay/pymc_core/.../sx1261_driver.py       → pyMC_core/.../hardware/
   cp overlay/pymc_core/.../signal_utils.py        → pyMC_core/.../hardware/
   cp overlay/pymc_core/.../virtual_radio.py       → pyMC_core/.../hardware/

   # pyMC_Repeater overlay (API, UI, bridge, engine)
   cp overlay/pymc_repeater/.../bridge_engine.py   → pyMC_Repeater/repeater/
   cp overlay/pymc_repeater/.../config_manager.py  → pyMC_Repeater/repeater/
   cp overlay/pymc_repeater/.../engine.py           → pyMC_Repeater/repeater/
   cp overlay/pymc_repeater/.../main.py             → pyMC_Repeater/repeater/
   cp overlay/pymc_repeater/.../wm1303_api.py       → pyMC_Repeater/repeater/web/
   cp overlay/pymc_repeater/.../wm1303.html         → pyMC_Repeater/repeater/web/html/
   # ... and more
   ```

3. **Build** — If HAL files were modified, the C code is recompiled. Python overlay files take effect immediately (packages are installed in editable mode).

### Advantages of the Overlay Approach

| Advantage | Description |
|-----------|-------------|
| **Clean separation** | WM1303 changes are clearly separated from upstream code |
| **Easy upstream sync** | Pull upstream changes, re-apply overlay — no merge conflicts |
| **Transparent diffs** | Compare overlay files against upstream originals to see exactly what changed |
| **Single-repo development** | All WM1303 work happens in one repository |
| **Safe upgrades** | `upgrade.sh` discards local changes and re-applies overlay, ensuring consistency |

### Overlay Directory Structure

```
overlay/
├── hal/
│   ├── libloragw/
│   │   ├── src/
│   │   │   ├── loragw_hal.c          # Modified HAL main source
│   │   │   └── loragw_sx1302.c       # Modified SX1302 driver
│   │   ├── inc/
│   │   │   └── loragw_sx1302.h       # Modified SX1302 header
│   │   └── Makefile                  # Modified build rules
│   └── packet_forwarder/
│       ├── src/
│       │   └── lora_pkt_fwd.c        # Modified packet forwarder
│       └── Makefile                  # Modified build rules
├── pymc_core/
│   └── src/pymc_core/hardware/
│       ├── __init__.py               # Hardware module init
│       ├── wm1303_backend.py         # WM1303 backend (largest file)
│       ├── sx1302_hal.py             # Python HAL wrapper
│       ├── tx_queue.py               # TX queue implementation
│       ├── sx1261_driver.py          # SX1261 companion driver
│       ├── signal_utils.py           # Signal processing utilities
│       └── virtual_radio.py          # VirtualLoRaRadio abstraction
└── pymc_repeater/
    └── repeater/
        ├── bridge_engine.py          # Modified bridge engine
        ├── config_manager.py         # Configuration management
        ├── engine.py                 # Main engine
        ├── main.py                   # Entry point
        ├── identity_manager.py       # Identity/key management
        ├── config.py                 # Config utilities
        ├── packet_router.py          # Packet routing
        ├── web/
        │   ├── wm1303_api.py         # REST API endpoints
        │   ├── http_server.py        # Web server
        │   ├── spectrum_collector.py  # Spectral data collection
        │   ├── cad_calibration_engine.py  # CAD calibration
        │   └── html/
        │       └── wm1303.html       # WM1303 Manager UI
        └── data_acquisition/
            ├── sqlite_handler.py     # Database handler
            └── storage_collector.py  # Metrics storage
```

## Branch Strategy

| Repository | Branch | Rationale |
|------------|--------|----------|
| sx1302_hal | `master` | Stable HAL release (v2.10). HAL changes are infrequent and must be reliable |
| pyMC_core | `dev` | Active development branch with latest features and fixes |
| pyMC_Repeater | `dev` | Active development branch with latest features and fixes |

The `master` branch is used for HAL because concentrator-level code must be very stable — a HAL bug can lock up the radio hardware. The `dev` branch is used for pyMC packages because they are under active development and the overlay system makes it safe to track the latest changes.

## How to Update When Upstream Forks Change

When new commits are available in the upstream fork repositories:

### Automatic Update (Recommended)

```bash
cd ~/pyMC_WM1303
git pull                    # Get latest overlay and scripts
sudo bash upgrade.sh        # Pulls forks, re-applies overlay, rebuilds if needed
```

The upgrade script handles everything automatically:
1. Creates a pre-upgrade backup
2. Pulls latest commits from all three forks
3. Discards any local changes in the forks
4. Re-applies the overlay
5. Rebuilds C code if HAL was updated
6. Reinstalls Python packages if pyMC repos were updated

See [Installation & Upgrade](installation.md) for full upgrade documentation.

### Manual Update (Advanced)

To update a specific repository manually:

```bash
# Update HAL fork
cd /home/pi/sx1302_hal
git fetch --all
git checkout master
git pull origin master

# Re-apply HAL overlay
cd ~/pyMC_WM1303
cp overlay/hal/libloragw/src/* /home/pi/sx1302_hal/libloragw/src/
cp overlay/hal/libloragw/inc/* /home/pi/sx1302_hal/libloragw/inc/
cp overlay/hal/libloragw/Makefile /home/pi/sx1302_hal/libloragw/
cp overlay/hal/packet_forwarder/src/* /home/pi/sx1302_hal/packet_forwarder/src/
cp overlay/hal/packet_forwarder/Makefile /home/pi/sx1302_hal/packet_forwarder/

# Rebuild
cd /home/pi/sx1302_hal/libloragw && make clean && make
cd /home/pi/sx1302_hal/packet_forwarder && make clean && make
cp /home/pi/sx1302_hal/packet_forwarder/lora_pkt_fwd /home/pi/wm1303_pf/

# Restart service
sudo systemctl restart pymc-repeater
```

## Future Development

All future development for the WM1303 system happens in the main [pyMC_WM1303](https://github.com/HansvanMeer/pyMC_WM1303) repository:

- **New features** — Add or modify overlay files, update install/upgrade scripts
- **Bug fixes** — Fix overlay files, test on hardware, commit to main repo
- **Configuration changes** — Update templates in `config/`
- **Documentation** — Update files in `docs/`

The fork repositories remain unmodified mirrors of upstream. If upstream introduces changes that conflict with the overlay, the overlay files are updated to be compatible.

### Contributing

To contribute or make changes:

1. Clone the main repository
2. Make changes to overlay files, scripts, config templates, or docs
3. Test on a WM1303/SenseCAP M1 system using `install.sh` or `upgrade.sh`
4. Commit and push to the main repository

Do not commit changes directly to the fork repositories.

## Programming Languages

The project uses the following languages:

| Language | Usage | Location |
|----------|-------|----------|
| **Python** | Backend, API, bridge engine, TX queue, hardware drivers, web server | `overlay/pymc_core/`, `overlay/pymc_repeater/` |
| **C** | HAL library, packet forwarder | `overlay/hal/` |
| **HTML/CSS/JavaScript** | WM1303 Manager web UI | `overlay/pymc_repeater/.../html/` |
| **Bash** | Installation, upgrade, GPIO reset scripts | `install.sh`, `upgrade.sh`, `config/*.sh` |
| **YAML** | Service configuration | `config/config.yaml.template` |
| **JSON** | HAL config, UI state | `config/global_conf.json`, `config/wm1303_ui.json` |

## Related Documentation

- [Installation & Upgrade](installation.md) — How repositories are cloned and overlays applied
- [System Architecture](architecture.md) — How components from different repos interact
- [Software Components](software.md) — Detailed overlay file documentation
- [Hardware Overview](hardware.md) — HAL and hardware context
- [Configuration Reference](configuration.md) — Config file templates and parameters
