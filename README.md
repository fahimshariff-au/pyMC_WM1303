# pyMC_WM1303

**WM1303 (SX1302/SX1303) LoRa Concentrator Module for MeshCore**

A complete installation and management system for running a [WM1303 LoRa concentrator](https://www.seeedstudio.com/WM1303-LoRaWAN-Gateway-Module-SX1303-p-5154.html) with [MeshCore](https://meshcore.co) (pyMC_core & pyMC_Repeater) on a SenseCAP M1 / Raspberry Pi.

---

## Overview

This project integrates the Semtech SX1302/SX1303-based WM1303 LoRa concentrator HAT with the MeshCore mesh networking stack, providing:

- **Multi-channel LoRa gateway** — Up to 4 simultaneous receive channels across 2 RF chains
- **MeshCore mesh repeater** — Bridge packets between channels, forward across the mesh network
- **Web-based management UI** — Real-time monitoring, channel configuration, spectrum analysis
- **REST API** — Full programmatic control of all gateway functions
- **Automated installation** — Single-script setup from bare Raspberry Pi OS

The system uses an **overlay approach**: unmodified forks of the upstream repositories are cloned during installation, then WM1303-specific modifications are applied on top. This keeps the forks clean while allowing custom hardware integration.

## Features

### Radio & Hardware
- Dual RF chain support (RF0 + RF1) with independent frequency and spreading factor configuration
- Up to 8 IF demodulators (4 per RF chain) for multi-SF reception
- SX1261 companion chip integration for spectral scanning, noise floor monitoring, and Listen Before Talk (LBT)
- GPIO-based hardware control (power, reset, SX1261, AD5338R) with configurable pin mapping
- Automatic AGC management with debounce protection
- FEM (Front-End Module) LNA/PA register management

### Software
- Bridge engine with configurable rules (Single Source of Truth) for inter-channel packet forwarding
- Global TX scheduler with round-robin queuing, batch windows, and echo prevention
- Software LBT/CAD (Listen Before Talk / Channel Activity Detection) per channel
- RX watchdog with 3 automatic detection modes and packet forwarder recovery
- Packet deduplication with configurable TTL
- SQLite database for metrics, signal quality history, and dashboard data
- JWT-based authentication for API and web interface
- Systemd service with security hardening and auto-restart

### Management Interface
- **WM1303 Manager** — Single-page web application for real-time gateway management
- **Channels tab** — Per-channel status, statistics, and configuration
- **Spectrum tab** — Real-time spectral scan visualization with waterfall display
- **Bridge tab** — Visual bridge rule configuration between channels
- **Signal Quality** — RSSI/SNR charts with historical data
- **LBT/CAD charts** — Listen Before Talk decision visualization
- **Advanced Config** — GPIO pins, IF chains, RF chain parameters

## Hardware Requirements

| Component | Specification |
|-----------|---------------|
| **Single Board Computer** | SenseCAP M1 or Raspberry Pi 3B+/4/5 |
| **LoRa Module** | WM1303 LoRaWAN Gateway Module (SX1302/SX1303 + SX1261 + dual SX1250) |
| **HAT/Interface** | SenseCAP M1 Pi HAT or compatible SPI interface |
| **OS** | Raspberry Pi OS Lite (Bookworm or newer) |
| **SPI** | Must be enabled in `/boot/firmware/config.txt` |
| **Internet** | Required during installation for package downloads |

## Quick Start

```bash
# 1. Clone this repository
git clone https://github.com/HansvanMeer/pyMC_WM1303.git
cd pyMC_WM1303

# 2. Run the installation script
sudo bash install.sh

# 3. Access the web interface
# Open http://<your-pi-ip>:8000/wm1303.html
```

The installation script handles everything:
- System package updates and build tool installation
- SPI configuration verification
- Repository cloning (HAL, pyMC_core, pyMC_Repeater)
- Overlay application (WM1303-specific modifications)
- HAL and packet forwarder compilation
- Python virtual environment setup
- Configuration file deployment
- GPIO reset script generation
- Systemd service installation and startup
- NTP synchronization verification

See [docs/installation.md](docs/installation.md) for detailed instructions.

## Upgrading

```bash
cd pyMC_WM1303
git pull
sudo bash upgrade.sh
```

Options:
- `--rebuild` — Force HAL/packet forwarder rebuild
- `--force-config` — Overwrite existing configuration with templates
- `--skip-pull` — Skip pulling from fork repositories

The upgrade script automatically backs up your configuration before making changes.

## Repository Structure

```
pyMC_WM1303/
├── install.sh              # Full installation script (12 phases)
├── upgrade.sh              # Upgrade script (8 phases)
├── README.md               # This file
├── TODO.md                 # Development task tracking
├── LICENSE                 # MIT License
├── config/                 # Configuration templates
│   ├── config.yaml.template    # Main application config
│   ├── wm1303_ui.json          # UI & channel config (SSOT)
│   ├── global_conf.json        # HAL configuration
│   ├── pymc-repeater.service   # Systemd service file
│   ├── reset_lgw.sh            # GPIO reset script template
│   └── power_cycle_lgw.sh      # Power cycle script template
├── overlay/                # Source code modifications
│   ├── hal/                    # HAL & packet forwarder patches
│   │   ├── libloragw/          #   AGC, FEM, LNA, spectral scan
│   │   └── packet_forwarder/   #   TX/RX handling modifications
│   ├── pymc_core/              # MeshCore core library additions
│   │   └── hardware/           #   WM1303Backend, TXQueue, SX1261, etc.
│   └── pymc_repeater/          # MeshCore repeater modifications
│       └── repeater/           #   Bridge engine, API, UI, config
├── docs/                   # Comprehensive documentation
│   ├── architecture.md         # System architecture overview
│   ├── hardware.md             # Hardware & HAL details
│   ├── radio.md                # Radio configuration guide
│   ├── software.md             # Software components
│   ├── ui.md                   # WM1303 Manager UI guide
│   ├── api.md                  # REST API reference
│   ├── lbt_cad.md              # LBT & CAD documentation
│   ├── tx_queue.md             # TX queue & scheduling
│   ├── configuration.md        # Configuration file reference
│   ├── installation.md         # Installation & upgrade guide
│   └── repositories.md         # Repository information
└── scripts/                # Utility scripts
```

## Fork Repositories

This project uses unmodified forks of the upstream repositories. **Do not modify the forks directly** — all changes are managed through the overlay directory.

| Repository | Branch | Purpose |
|------------|--------|---------|
| [sx1302_hal](https://github.com/HansvanMeer/sx1302_hal) | `master` | Semtech HAL v2.10 for SX1302/SX1303 |
| [pyMC_core](https://github.com/HansvanMeer/pyMC_core) | `dev` | MeshCore core library (radio drivers, mesh protocol) |
| [pyMC_Repeater](https://github.com/HansvanMeer/pyMC_Repeater) | `dev` | MeshCore repeater (bridge, web UI, API, service) |

See [docs/repositories.md](docs/repositories.md) for details on the overlay approach.

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | System architecture, component relationships, data flow |
| [Hardware](docs/hardware.md) | WM1303 module, SPI, GPIO, HAL modifications, FEM/LNA/AGC |
| [Radio](docs/radio.md) | RF/IF chains, channels, frequency planning, sync word |
| [Software](docs/software.md) | Backend components, bridge engine, watchdog, database |
| [UI Guide](docs/ui.md) | WM1303 Manager web interface |
| [API Reference](docs/api.md) | REST API endpoints and authentication |
| [LBT & CAD](docs/lbt_cad.md) | Listen Before Talk and Channel Activity Detection |
| [TX Queue](docs/tx_queue.md) | TX processing flow, queue management, scheduling |
| [Configuration](docs/configuration.md) | All configuration files explained |
| [Installation](docs/installation.md) | Installation, upgrade, and troubleshooting guide |
| [Repositories](docs/repositories.md) | Fork repos, branches, and overlay approach |

## Technology Stack

| Layer | Technology |
|-------|------------|
| **Hardware Abstraction** | C (Semtech HAL v2.10, libloragw, lora_pkt_fwd) |
| **Backend** | Python 3 (pyMC_core, pyMC_Repeater, CherryPy) |
| **Frontend** | HTML5, JavaScript, CSS (single-page application) |
| **Charts** | Chart.js with chartjs-adapter-date-fns |
| **Database** | SQLite (metrics, signal history, dedup events) |
| **Service** | systemd (pymc-repeater.service) |
| **Communication** | SPI (HAL ↔ SX1302), UDP (pkt_fwd ↔ backend), WebSocket (backend ↔ UI) |

## Service Management

```bash
# Start / stop / restart
sudo systemctl start pymc-repeater
sudo systemctl stop pymc-repeater
sudo systemctl restart pymc-repeater

# View logs
journalctl -u pymc-repeater -f

# Check status
sudo systemctl status pymc-repeater
```

## Disclaimer

> **⚠️ Use at your own risk.** This software interacts directly with radio hardware via SPI and GPIO.
> The authors accept no responsibility for any damage to hardware, loss of data, or regulatory
> non-compliance resulting from the use of this software. Ensure your radio configuration complies
> with local regulations (e.g., EU868 duty cycle limits).

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
