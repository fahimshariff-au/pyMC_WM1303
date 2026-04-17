"""WM1303 Debug Bundle Collector.

Generates a comprehensive diagnostic bundle (.tar.gz) for remote
troubleshooting.  All sensitive data (identity keys, JWT secrets) is
automatically redacted before inclusion.

Usage (from API):
    collector = DebugCollector(config, backend, bridge_engine, repeater_engine)
    result = await collector.generate()   # returns dict with path, size, expires
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("DebugCollector")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BUNDLE_DIR = Path("/tmp/wm1303_debug")
BUNDLE_EXPIRY_SECONDS = 15 * 60  # 15 minutes
MIN_DISK_FREE_MB = 50  # Minimum free disk space required
JOURNAL_FULL_MINUTES = 30  # Full journal log window
JOURNAL_ERRORS_HOURS = 24  # Error-only journal window
MAX_JOURNAL_LINES = 10000  # Safety cap

# Secrets to redact in config files
_REDACT_KEYS = {
    "identity_key", "jwt_secret", "password", "secret",
    "private_key", "api_key", "token",
}


class DebugCollector:
    """Collects diagnostic data and packages it into a downloadable bundle."""

    def __init__(
        self,
        config: Dict[str, Any],
        backend: Any = None,
        bridge_engine: Any = None,
        repeater_engine: Any = None,
    ):
        self.config = config or {}
        self.backend = backend
        self.bridge_engine = bridge_engine
        self.repeater_engine = repeater_engine
        self._lock = threading.Lock()
        self._current_bundle: Optional[Dict[str, Any]] = None
        self._cleanup_timer: Optional[threading.Timer] = None
        # Purge any orphaned bundles left over from a previous run/restart
        self._purge_bundle_dir()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return current bundle status for the UI."""
        if self._current_bundle and Path(self._current_bundle["path"]).exists():
            remaining = self._current_bundle["expires"] - time.time()
            if remaining > 0:
                return {
                    "available": True,
                    "filename": self._current_bundle["filename"],
                    "size_bytes": self._current_bundle["size_bytes"],
                    "size_mb": round(self._current_bundle["size_bytes"] / (1024 * 1024), 2),
                    "created": self._current_bundle["created"],
                    "expires": self._current_bundle["expires"],
                    "expires_in_seconds": int(remaining),
                }
            else:
                self._cleanup_bundle()
        return {"available": False}

    async def generate(self) -> Dict[str, Any]:
        """Generate a new debug bundle.  Returns status dict."""
        # Check disk space first
        disk_check = self._check_disk_space()
        if not disk_check["ok"]:
            return {"error": True, "message": disk_check["message"]}

        # Clean up any previous bundle
        self._cleanup_bundle()

        # Create temporary working directory
        work_dir = Path(tempfile.mkdtemp(prefix="wm1303_debug_"))
        try:
            # Collect all data
            await self._collect_system_info(work_dir)
            await self._collect_service_status(work_dir)
            await self._collect_configs(work_dir)
            await self._collect_logs(work_dir)
            await self._collect_runtime_stats(work_dir)
            await self._collect_file_integrity(work_dir)
            await self._collect_database_info(work_dir)
            await self._collect_identity_info(work_dir)

            # Package into tar.gz
            hostname = self._run_cmd("hostname").strip() or "unknown"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"wm1303-debug-{hostname}-{timestamp}.tar.gz"

            BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
            bundle_path = BUNDLE_DIR / filename

            with tarfile.open(str(bundle_path), "w:gz") as tar:
                # Add all files from work_dir with a clean base name
                base_name = filename.replace(".tar.gz", "")
                for item in work_dir.rglob("*"):
                    if item.is_file():
                        arcname = f"{base_name}/{item.relative_to(work_dir)}"
                        tar.add(str(item), arcname=arcname)

            size_bytes = bundle_path.stat().st_size
            now = time.time()

            self._current_bundle = {
                "path": str(bundle_path),
                "filename": filename,
                "size_bytes": size_bytes,
                "created": now,
                "expires": now + BUNDLE_EXPIRY_SECONDS,
            }

            # Schedule auto-cleanup
            self._schedule_cleanup()

            logger.info("Debug bundle generated: %s (%.1f MB)",
                        filename, size_bytes / (1024 * 1024))

            return self.get_status()

        except Exception as exc:
            logger.exception("Failed to generate debug bundle")
            return {"error": True, "message": f"Bundle generation failed: {exc}"}
        finally:
            # Always clean up working directory
            shutil.rmtree(str(work_dir), ignore_errors=True)

    def get_bundle_path(self) -> Optional[str]:
        """Return the path to the current bundle if it exists and hasn't expired."""
        if self._current_bundle:
            path = Path(self._current_bundle["path"])
            if path.exists() and time.time() < self._current_bundle["expires"]:
                return str(path)
        return None

    # ------------------------------------------------------------------
    # Disk space check
    # ------------------------------------------------------------------

    def _check_disk_space(self) -> Dict[str, Any]:
        """Check if there's enough free disk space."""
        try:
            stat = os.statvfs("/tmp")
            free_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)
            if free_mb < MIN_DISK_FREE_MB:
                return {
                    "ok": False,
                    "message": f"Insufficient disk space: {free_mb:.0f} MB free, "
                               f"need at least {MIN_DISK_FREE_MB} MB",
                }
            return {"ok": True, "free_mb": free_mb}
        except Exception as exc:
            return {"ok": False, "message": f"Cannot check disk space: {exc}"}

    # ------------------------------------------------------------------
    # Cleanup / expiry
    # ------------------------------------------------------------------

    def _schedule_cleanup(self):
        """Schedule automatic bundle cleanup after BUNDLE_EXPIRY_SECONDS."""
        if self._cleanup_timer:
            self._cleanup_timer.cancel()
        self._cleanup_timer = threading.Timer(
            BUNDLE_EXPIRY_SECONDS, self._cleanup_bundle
        )
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()

    def _cleanup_bundle(self):
        """Remove current bundle and reset state."""
        if self._cleanup_timer:
            self._cleanup_timer.cancel()
            self._cleanup_timer = None
        if self._current_bundle:
            path = Path(self._current_bundle["path"])
            if path.exists():
                try:
                    path.unlink()
                    logger.info("Debug bundle expired/cleaned: %s",
                                self._current_bundle["filename"])
                except Exception:
                    pass
            self._current_bundle = None
        # Also purge any orphaned files (e.g. from a previous run)
        self._purge_bundle_dir()

    def _purge_bundle_dir(self):
        """Remove ALL files in BUNDLE_DIR and the directory itself.

        This catches orphaned bundles left behind after a service restart
        (when in-memory state is lost but the file remains on disk).
        """
        try:
            if BUNDLE_DIR.exists():
                for f in BUNDLE_DIR.iterdir():
                    try:
                        f.unlink()
                        logger.info("Purged orphaned debug bundle: %s", f.name)
                    except Exception:
                        pass
                # Remove dir if now empty
                if not any(BUNDLE_DIR.iterdir()):
                    BUNDLE_DIR.rmdir()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Helper: run shell commands
    # ------------------------------------------------------------------

    def _run_cmd(self, cmd: str, timeout: int = 10) -> str:
        """Run a shell command and return stdout.  Never raises."""
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout
            )
            return result.stdout
        except Exception:
            return ""

    def _write(self, path: Path, content: str):
        """Write content to a file, creating parent dirs as needed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _write_json(self, path: Path, data: Any):
        """Write JSON data to a file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    # ------------------------------------------------------------------
    # Sanitization
    # ------------------------------------------------------------------

    def _sanitize_config(self, data: Any, depth: int = 0) -> Any:
        """Recursively redact sensitive keys in a config dict."""
        if depth > 20:
            return data
        if isinstance(data, dict):
            result = {}
            for k, v in data.items():
                if any(secret in k.lower() for secret in _REDACT_KEYS):
                    result[k] = "[REDACTED]"
                else:
                    result[k] = self._sanitize_config(v, depth + 1)
            return result
        elif isinstance(data, list):
            return [self._sanitize_config(item, depth + 1) for item in data]
        return data

    # ------------------------------------------------------------------
    # Collectors
    # ------------------------------------------------------------------

    async def _collect_system_info(self, work_dir: Path):
        """Collect system-level information."""
        info = []
        info.append("=== WM1303 Debug Bundle ===")
        info.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        info.append("")

        info.append("=== OS & Kernel ===")
        info.append(self._run_cmd("cat /etc/os-release"))
        info.append(self._run_cmd("uname -a"))

        info.append("=== Hostname ===")
        info.append(self._run_cmd("hostname"))

        info.append("=== Pi Model ===")
        info.append(self._run_cmd("cat /proc/device-tree/model 2>/dev/null || echo 'unknown'"))

        info.append("=== Uptime ===")
        info.append(self._run_cmd("uptime"))

        info.append("=== CPU Temperature ===")
        info.append(self._run_cmd(
            "awk '{printf \"%.1f°C\\n\", $1/1000}' /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 'unknown'"
        ))

        info.append("=== Concentrator Temperature ===")
        info.append(self._run_cmd("cat /tmp/concentrator_temp 2>/dev/null || echo 'unavailable'"))

        info.append("=== Memory ===")
        info.append(self._run_cmd("free -h"))

        info.append("=== Disk Usage ===")
        info.append(self._run_cmd("df -h"))

        info.append("=== NTP Sync ===")
        info.append(self._run_cmd("timedatectl status 2>/dev/null || echo 'timedatectl not available'"))

        info.append("=== SPI Devices ===")
        info.append(self._run_cmd("ls -la /dev/spidev* 2>/dev/null || echo 'no SPI devices'"))

        info.append("=== I2C Devices ===")
        info.append(self._run_cmd("i2cdetect -y 1 2>/dev/null || echo 'i2cdetect not available'"))

        info.append("=== Network Interfaces ===")
        info.append(self._run_cmd("ip addr show"))

        info.append("=== Boot Config (SPI relevant) ===")
        info.append(self._run_cmd(
            "grep -E 'spi|dtoverlay|dtparam' /boot/firmware/config.txt 2>/dev/null "
            "|| grep -E 'spi|dtoverlay|dtparam' /boot/config.txt 2>/dev/null "
            "|| echo 'config.txt not found'"
        ))

        info.append("=== Kernel Messages (SPI/hardware related) ===")
        info.append(self._run_cmd("dmesg | grep -iE 'spi|lora|gpio|thermal|throttl' | tail -50"))

        self._write(work_dir / "system_info.txt", "\n".join(info))

    async def _collect_service_status(self, work_dir: Path):
        """Collect service and process status."""
        info = []

        info.append("=== pymc-repeater Service Status ===")
        info.append(self._run_cmd("systemctl status pymc-repeater --no-pager -l 2>/dev/null"))

        info.append("=== pkt_fwd Process ===")
        info.append(self._run_cmd("ps aux | grep lora_pkt_fwd | grep -v grep"))

        info.append("=== Python Version ===")
        info.append(self._run_cmd("python3 --version"))

        info.append("=== pymc_core Package ===")
        info.append(self._run_cmd("pip3 show pymc-core 2>/dev/null || echo 'not installed'"))

        info.append("=== pymc_repeater Package ===")
        info.append(self._run_cmd("pip3 show pymc-repeater 2>/dev/null || echo 'not installed'"))

        info.append("=== WM1303 Version ===")
        info.append(self._run_cmd("cat /etc/pymc_repeater/version 2>/dev/null || echo 'unknown'"))

        info.append("=== Service Restarts (last 24h) ===")
        info.append(self._run_cmd(
            "journalctl -u pymc-repeater --no-pager --since '24 hours ago' "
            "| grep -iE 'start|stop|restart|failed' | tail -30"
        ))

        info.append("=== Open File Descriptors ===")
        pkt_pid = self._run_cmd("pgrep -x lora_pkt_fwd").strip()
        if pkt_pid:
            info.append(f"pkt_fwd (PID {pkt_pid}): " +
                        self._run_cmd(f"ls /proc/{pkt_pid}/fd 2>/dev/null | wc -l").strip() + " fds")
        svc_pid = self._run_cmd("pgrep -f 'pymc_repeater' | head -1").strip()
        if svc_pid:
            info.append(f"pymc-repeater (PID {svc_pid}): " +
                        self._run_cmd(f"ls /proc/{svc_pid}/fd 2>/dev/null | wc -l").strip() + " fds")

        self._write(work_dir / "service_status.txt", "\n".join(info))

    async def _collect_configs(self, work_dir: Path):
        """Collect configuration files (sanitized)."""
        config_dir = work_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        # config.yaml - SANITIZED
        try:
            import yaml
            config_path = Path("/etc/pymc_repeater/config.yaml")
            if config_path.exists():
                with open(config_path) as f:
                    raw_config = yaml.safe_load(f)
                sanitized = self._sanitize_config(raw_config)
                self._write(config_dir / "config.yaml.sanitized",
                            yaml.dump(sanitized, default_flow_style=False, sort_keys=False))
        except Exception as exc:
            self._write(config_dir / "config.yaml.sanitized", f"Error reading config: {exc}")

        # wm1303_ui.json
        try:
            ui_path = Path("/etc/pymc_repeater/wm1303_ui.json")
            if ui_path.exists():
                with open(ui_path) as f:
                    ui_data = json.load(f)
                self._write_json(config_dir / "wm1303_ui.json", ui_data)
        except Exception as exc:
            self._write(config_dir / "wm1303_ui.json", f"Error: {exc}")

        # bridge_conf.json (generated)
        for name in ["bridge_conf.json", "global_conf.json"]:
            src = Path(f"/home/pi/wm1303_pf/{name}")
            if src.exists():
                try:
                    with open(src) as f:
                        self._write_json(config_dir / name, json.load(f))
                except Exception:
                    try:
                        shutil.copy2(str(src), str(config_dir / name))
                    except Exception:
                        pass

        # pymc-repeater.service
        svc_path = Path("/etc/systemd/system/pymc-repeater.service")
        if svc_path.exists():
            try:
                shutil.copy2(str(svc_path), str(config_dir / "pymc-repeater.service"))
            except Exception:
                pass

        # Boot config (SPI lines only)
        boot_spi = self._run_cmd(
            "grep -nE 'spi|dtoverlay|dtparam' /boot/firmware/config.txt 2>/dev/null "
            "|| grep -nE 'spi|dtoverlay|dtparam' /boot/config.txt 2>/dev/null"
        )
        self._write(config_dir / "boot_config_spi.txt", boot_spi or "not found")

    async def _collect_logs(self, work_dir: Path):
        """Collect journal logs."""
        logs_dir = work_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        # Full journal (last 30 minutes)
        full_log = self._run_cmd(
            f"journalctl -u pymc-repeater --no-pager "
            f"--since '{JOURNAL_FULL_MINUTES} minutes ago' "
            f"| tail -{MAX_JOURNAL_LINES}",
            timeout=30
        )
        self._write(logs_dir / "journal_full_30min.log", full_log or "no logs")

        # Errors/warnings only (last 24 hours)
        error_log = self._run_cmd(
            f"journalctl -u pymc-repeater --no-pager -p warning "
            f"--since '{JOURNAL_ERRORS_HOURS} hours ago' "
            f"| tail -{MAX_JOURNAL_LINES}",
            timeout=30
        )
        self._write(logs_dir / "journal_errors_24h.log", error_log or "no errors")

        # pkt_fwd output (filtered)
        pkt_log = self._run_cmd(
            f"journalctl -u pymc-repeater --no-pager "
            f"--since '{JOURNAL_FULL_MINUTES} minutes ago' "
            f"| grep -E 'pkt_fwd:|\\[hal\\]|\\[down\\]|\\[up\\]|\\[jit\\]|\\[agc\\]|concentrator|SX126|SX130' "
            f"| tail -2000",
            timeout=30
        )
        self._write(logs_dir / "pkt_fwd_output.log", pkt_log or "no pkt_fwd output")

        # Python tracebacks
        traceback_log = self._run_cmd(
            f"journalctl -u pymc-repeater --no-pager "
            f"--since '{JOURNAL_ERRORS_HOURS} hours ago' "
            f"| grep -A5 -E 'Traceback|Error|Exception' "
            f"| tail -2000",
            timeout=30
        )
        self._write(logs_dir / "tracebacks.log", traceback_log or "no tracebacks")

        # TX log
        tx_log = self._run_cmd(
            f"journalctl -u pymc-repeater --no-pager "
            f"--since '{JOURNAL_FULL_MINUTES} minutes ago' "
            f"| grep -E 'TX OK|TX FAIL|TX timeout|TX_ACK|PULL_RESP|tx_queue|TXQueue|GlobalTXScheduler' "
            f"| tail -2000",
            timeout=30
        )
        self._write(logs_dir / "tx_log.log", tx_log or "no TX activity")

        # Bridge forwarding log
        bridge_log = self._run_cmd(
            f"journalctl -u pymc-repeater --no-pager "
            f"--since '{JOURNAL_FULL_MINUTES} minutes ago' "
            f"| grep -E 'BridgeEngine|bridge|forwarded|delivered|Channel E' "
            f"| tail -2000",
            timeout=30
        )
        self._write(logs_dir / "bridge_forwarding.log", bridge_log or "no bridge activity")

        # Startup sequence (from last service start)
        startup_log = self._run_cmd(
            "journalctl -u pymc-repeater --no-pager "
            "-b | head -200",
            timeout=15
        )
        self._write(logs_dir / "startup_sequence.log", startup_log or "no startup logs")

    async def _collect_runtime_stats(self, work_dir: Path):
        """Collect runtime statistics from the running services."""
        stats_dir = work_dir / "stats"
        stats_dir.mkdir(parents=True, exist_ok=True)

        # Channel stats from backend
        if self.backend:
            try:
                ch_stats = self.backend.get_channel_stats()
                self._write_json(stats_dir / "channel_stats.json", ch_stats)
            except Exception as exc:
                self._write(stats_dir / "channel_stats.json", f"Error: {exc}")

            # Backend internal stats
            try:
                bk_stats = {}
                for attr in ["_tx_echo_hashes", "_rx_dedup_cache",
                             "_channel_e_config_cache", "_channel_e_freq"]:
                    val = getattr(self.backend, attr, None)
                    if val is not None:
                        if isinstance(val, dict):
                            bk_stats[attr] = {"size": len(val)}
                        else:
                            bk_stats[attr] = str(val)
                self._write_json(stats_dir / "backend_stats.json", bk_stats)
            except Exception:
                pass

        # Queue stats from tx_queue
        if self.backend:
            try:
                tx_q = getattr(self.backend, "_tx_scheduler", None)
                if tx_q:
                    q_stats = {}
                    for attr in dir(tx_q):
                        if "stat" in attr.lower() or "queue" in attr.lower():
                            try:
                                val = getattr(tx_q, attr)
                                if not callable(val):
                                    q_stats[attr] = str(val)
                            except Exception:
                                pass
                    # Get per-channel queue stats
                    queues = getattr(tx_q, "_queues", {})
                    for ch_name, q in queues.items():
                        q_stats[f"queue_{ch_name}"] = {
                            "pending": q.qsize() if hasattr(q, "qsize") else "unknown",
                            "stats": getattr(q, "stats", {}),
                        }
                    self._write_json(stats_dir / "queue_stats.json", q_stats)
            except Exception as exc:
                self._write(stats_dir / "queue_stats.json", f"Error: {exc}")

        # Bridge engine stats
        if self.bridge_engine:
            try:
                bridge_stats = self.bridge_engine.get_stats()
                bridge_stats["_seen_cache_size"] = len(
                    getattr(self.bridge_engine, "_seen", {})
                )
                self._write_json(stats_dir / "bridge_stats.json", bridge_stats)
            except Exception as exc:
                self._write(stats_dir / "bridge_stats.json", f"Error: {exc}")

        # Repeater engine stats
        if self.repeater_engine:
            try:
                rpt_stats = {
                    "seen_packets_cache_size": len(
                        getattr(self.repeater_engine, "seen_packets", {})
                    ),
                    "cache_ttl": getattr(self.repeater_engine, "cache_ttl", "unknown"),
                }
                self._write_json(stats_dir / "repeater_stats.json", rpt_stats)
            except Exception as exc:
                self._write(stats_dir / "repeater_stats.json", f"Error: {exc}")

        # Spectral scan data
        try:
            scan_path = Path("/tmp/spectral_scan_latest.json")
            if scan_path.exists():
                with open(scan_path) as f:
                    self._write_json(stats_dir / "spectral_scan.json", json.load(f))
        except Exception:
            pass

        # pkt_fwd status (from PUSH_DATA stat)
        try:
            stat_path = Path("/tmp/pkt_fwd_status.json")
            if stat_path.exists():
                with open(stat_path) as f:
                    self._write_json(stats_dir / "pkt_fwd_status.json", json.load(f))
        except Exception:
            pass

    async def _collect_file_integrity(self, work_dir: Path):
        """Collect MD5 checksums of key overlay files."""
        integrity_dir = work_dir / "integrity"
        integrity_dir.mkdir(parents=True, exist_ok=True)

        # Files to checksum
        check_files = []

        # Python overlay files
        site_pkg_base = self._run_cmd(
            "python3 -c 'import pymc_core; import os; print(os.path.dirname(os.path.dirname(pymc_core.__file__)))' 2>/dev/null"
        ).strip()

        if site_pkg_base:
            python_files = [
                f"{site_pkg_base}/pymc_core/hardware/__init__.py",
                f"{site_pkg_base}/pymc_core/hardware/signal_utils.py",
                f"{site_pkg_base}/pymc_core/hardware/sx1261_driver.py",
                f"{site_pkg_base}/pymc_core/hardware/sx1302_hal.py",
                f"{site_pkg_base}/pymc_core/hardware/tx_queue.py",
                f"{site_pkg_base}/pymc_core/hardware/virtual_radio.py",
                f"{site_pkg_base}/pymc_core/hardware/wm1303_backend.py",
            ]
            check_files.extend(python_files)

        # Repeater files
        repeater_base = "/opt/pymc_repeater/repos/pyMC_Repeater/repeater"
        repeater_files = [
            f"{repeater_base}/bridge_engine.py",
            f"{repeater_base}/channel_e_bridge.py",
            f"{repeater_base}/config.py",
            f"{repeater_base}/config_manager.py",
            f"{repeater_base}/engine.py",
            f"{repeater_base}/identity_manager.py",
            f"{repeater_base}/main.py",
            f"{repeater_base}/packet_router.py",
            f"{repeater_base}/web/wm1303_api.py",
            f"{repeater_base}/web/api_endpoints.py",
            f"{repeater_base}/web/http_server.py",
            f"{repeater_base}/web/spectrum_collector.py",
            f"{repeater_base}/web/cad_calibration_engine.py",
            f"{repeater_base}/web/html/wm1303.html",
        ]
        check_files.extend(repeater_files)

        # pkt_fwd binary
        check_files.append("/home/pi/wm1303_pf/lora_pkt_fwd")

        # Generate checksums
        checksums = []
        for fpath in check_files:
            md5 = self._run_cmd(f"md5sum '{fpath}' 2>/dev/null").strip()
            if md5:
                checksums.append(md5)
            else:
                checksums.append(f"MISSING  {fpath}")

        self._write(integrity_dir / "file_checksums.txt", "\n".join(checksums))

        # Version file
        version = self._run_cmd("cat /etc/pymc_repeater/version 2>/dev/null").strip()
        self._write(integrity_dir / "version.txt", version or "unknown")

    async def _collect_database_info(self, work_dir: Path):
        """Collect database status and recent metrics."""
        db_dir = work_dir / "database"
        db_dir.mkdir(parents=True, exist_ok=True)

        info = []

        # Find database files
        db_files = self._run_cmd(
            "find /opt/pymc_repeater /var/lib/pymc_repeater /etc/pymc_repeater "
            "-name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' 2>/dev/null"
        ).strip()

        if db_files:
            info.append("=== Database Files ===")
            for db_path in db_files.split("\n"):
                db_path = db_path.strip()
                if db_path:
                    size = self._run_cmd(f"ls -lh '{db_path}' 2>/dev/null").strip()
                    info.append(size)

                    # Integrity check
                    integrity = self._run_cmd(
                        f"sqlite3 '{db_path}' 'PRAGMA integrity_check' 2>/dev/null"
                    ).strip()
                    info.append(f"  Integrity: {integrity}")

                    # Schema version
                    schema_ver = self._run_cmd(
                        f"sqlite3 '{db_path}' 'PRAGMA user_version' 2>/dev/null"
                    ).strip()
                    info.append(f"  Schema version: {schema_ver}")

                    # Table list
                    tables = self._run_cmd(
                        f"sqlite3 '{db_path}' '.tables' 2>/dev/null"
                    ).strip()
                    info.append(f"  Tables: {tables}")

                    # Row counts per table
                    if tables:
                        for table in tables.split():
                            count = self._run_cmd(
                                f"sqlite3 '{db_path}' 'SELECT COUNT(*) FROM {table}' 2>/dev/null"
                            ).strip()
                            info.append(f"    {table}: {count} rows")
                    info.append("")
        else:
            info.append("No database files found")

        self._write(db_dir / "db_info.txt", "\n".join(info))

        # Recent metrics (last 100 records from the first db found)
        if db_files:
            first_db = db_files.split("\n")[0].strip()
            if first_db:
                metrics = self._run_cmd(
                    f"sqlite3 -json '{first_db}' "
                    f"'SELECT * FROM metrics ORDER BY timestamp DESC LIMIT 100' 2>/dev/null"
                )
                if metrics:
                    self._write(db_dir / "recent_metrics.json", metrics)

    async def _collect_identity_info(self, work_dir: Path):
        """Collect repeater identity (PUBLIC info only!)."""
        identity_dir = work_dir / "identity"
        identity_dir.mkdir(parents=True, exist_ok=True)

        info = {}

        if self.repeater_engine:
            try:
                # Only public info!
                identity = getattr(self.repeater_engine, "identity", None)
                if identity:
                    info["node_name"] = getattr(identity, "name", "unknown")
                    pub_key = getattr(identity, "public_key", None)
                    if pub_key:
                        if isinstance(pub_key, bytes):
                            info["public_key_hex"] = pub_key.hex()
                        else:
                            info["public_key_hex"] = str(pub_key)
                    short_hash = getattr(identity, "short_hash", None)
                    if short_hash:
                        info["short_hash"] = short_hash.hex() if isinstance(short_hash, bytes) else str(short_hash)
            except Exception:
                pass

        # JWT token validity (NOT the actual token)
        try:
            jwt_path = Path("/etc/pymc_repeater/jwt_token")
            if jwt_path.exists():
                info["jwt_token_exists"] = True
                mtime = jwt_path.stat().st_mtime
                info["jwt_token_age_hours"] = round((time.time() - mtime) / 3600, 1)
            else:
                info["jwt_token_exists"] = False
        except Exception:
            pass

        # NEVER include private key or JWT secret
        info["_note"] = "Private keys and JWT secrets are NOT included in this bundle."

        self._write_json(identity_dir / "node_info.json", info)
