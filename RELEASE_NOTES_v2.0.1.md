# Release Notes — v2.0.1

**Release date:** 2026-04-16  
**Type:** Patch release

---

## Summary

Version 2.0.1 is a patch release that adds **SPI optimizations**, fixes the **spidev kernel buffer size configuration** for Debian Trixie compatibility, and adds **Channel E to all Spectrum tab charts**.

---

## SPI Optimizations

### Optimized SPI driver (loragw_spi.c / loragw_spi.h)

The SPI driver has been optimized for significantly faster data transfers between the Raspberry Pi and the SX1302/SX1261 radios:

| Parameter | Default (before) | Optimized (now) |
|-----------|-----------------|------------------|
| `LGW_BURST_CHUNK` | 1024 bytes | **16384 bytes** (16×) |
| `SPI_SPEED` | 2 MHz | **16 MHz** (8×) |
| `lgw_spi_speed_override` | Not available | **Dynamic speed override** for capture reads |

These optimizations reduce SPI transfer overhead and improve RX/TX timing.

### Kernel spidev buffer size (bufsiz=32768)

The kernel SPI device buffer has been increased from 4096 to 32768 bytes to support the larger burst transfers. The install and upgrade scripts now configure this using **two methods** for maximum compatibility:

1. **modprobe.d** — `/etc/modprobe.d/spidev.conf` with `options spidev bufsiz=32768` (works on older kernels)
2. **Kernel command line** — `spidev.bufsiz=32768` appended to `/boot/firmware/cmdline.txt` (required for Debian Trixie and newer, where spidev loads before modprobe.d is processed)

A reboot is required after installation for this change to take effect.

---

## Spectrum Tab — Channel E Support

Channel E is now visible in all Spectrum tab charts:

- **CAD chart** — Channel E shown in orange
- **TX Activity chart** — Channel E included with orange color coding
- **LBT History chart** — Extended color palette to include Channel E
- Other dynamic charts (RSSI, SNR, Noise Floor) already supported Channel E

---

## Installation Bug Fixes

### Missing capture_thread files
- **Fixed:** HAL compilation failed on fresh installations because `capture_thread.c` and `capture_thread.h` were missing from the overlay.

### Missing sudoers configuration
- **Fixed:** The systemd service failed to execute `sudo` commands after installation because the `pi` user lacked passwordless sudo privileges. The install script now configures sudoers NOPASSWD and adds the `pi` user to hardware groups (spi, i2c, gpio, dialout).

---

## Files Changed

### New Files
- `overlay/hal/libloragw/src/loragw_spi.c` — Optimized SPI driver
- `overlay/hal/libloragw/inc/loragw_spi.h` — Optimized SPI header
- `overlay/hal/packet_forwarder/src/capture_thread.c` — CAPTURE_RAM streaming thread
- `overlay/hal/packet_forwarder/inc/capture_thread.h` — Capture thread header

### Modified Files
- `install.sh` — SPI overlay copies, spidev bufsiz (modprobe.d + cmdline.txt), sudoers NOPASSWD, hardware groups
- `upgrade.sh` — SPI overlay copies, spidev bufsiz (modprobe.d + cmdline.txt), file comparison list
- `overlay/hal/packet_forwarder/Makefile` — Compile/link capture_thread.o
- `overlay/pymc_repeater/repeater/web/html/wm1303.html` — Channel E color maps for Spectrum charts

---

## Upgrade Instructions

```bash
cd /home/pi/pyMC_WM1303
git pull
sudo bash upgrade.sh --force-rebuild
sudo reboot  # Required for spidev bufsiz change
```
