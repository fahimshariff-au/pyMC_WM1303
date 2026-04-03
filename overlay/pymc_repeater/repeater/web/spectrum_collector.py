"""Spectrum data collector - tails lora_pkt_fwd logs, stores in SQLite.

Parses the Semtech HAL SPECTRAL SCAN output format:
  SPECTRAL SCAN - 863000000 Hz: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 36 0 0 0 0 0 0 0 0 0
The 33 values are RSSI histogram bins covering roughly -140 dBm to -76 dBm (2 dBm per bin).

Also parses:
- LBT events from TX rejection/acceptance messages
- Periodic status JSON with RX/TX counters
- Concentrator temperature
"""
import sqlite3
import threading
import subprocess
import re
import time
import os
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger('spectrum_collector')

DB_PATH = '/var/lib/pymc_repeater/spectrum_history.db'

# RSSI histogram: 33 bins from -140 dBm to -74 dBm (2 dBm steps)
RSSI_BIN_START = -140.0  # dBm for bin 0
RSSI_BIN_STEP = 2.0      # dBm per bin
NUM_BINS = 33


def histogram_to_rssi(bins):
    """Convert a list of histogram bin counts to a weighted average RSSI (dBm).
    Returns None if all bins are zero."""
    total = sum(bins)
    if total == 0:
        return None
    weighted = 0.0
    for i, count in enumerate(bins):
        rssi_center = RSSI_BIN_START + (i * RSSI_BIN_STEP) + (RSSI_BIN_STEP / 2)
        weighted += rssi_center * count
    return weighted / total


def histogram_to_peak_rssi(bins):
    """Return the RSSI of the highest-count bin (peak energy)."""
    if not bins or max(bins) == 0:
        return None
    peak_idx = bins.index(max(bins))
    return RSSI_BIN_START + (peak_idx * RSSI_BIN_STEP) + (RSSI_BIN_STEP / 2)


class SpectrumCollector:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
        logger.info(f'SpectrumCollector initialized, db={db_path}')

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS spectrum_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            freq_mhz REAL NOT NULL,
            rssi_dbm REAL NOT NULL
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS lbt_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            channel_freq_hz INTEGER NOT NULL,
            rssi_dbm REAL,
            channel_clear INTEGER NOT NULL,
            tx_allowed INTEGER NOT NULL
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS cad_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            freq_hz INTEGER,
            cad_detected INTEGER NOT NULL,
            rssi_dbm REAL
        )''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_spec_ts ON spectrum_scans(timestamp)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_lbt_ts ON lbt_events(timestamp)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_cad_ts ON cad_events(timestamp)')
        conn.commit()
        conn.close()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._collect_loop, daemon=True)
        self._thread.start()
        logger.info('SpectrumCollector started - tailing lora_pkt_fwd journal')

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _collect_loop(self):
        """Tail journalctl for lora_pkt_fwd and parse spectral/LBT data."""
        while self._running:
            try:
                logger.info('Starting journalctl tail for pymc-repeater (lora_pkt_fwd output)...')
                proc = subprocess.Popen(
                    ['journalctl', '-u', 'pymc-repeater', '-f', '-n', '0', '--no-pager', '--output=cat'],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                for line in proc.stdout:
                    if not self._running:
                        break
                    line = line.strip()
                    if line:
                        self._parse_line(line)
                proc.terminate()
            except Exception as e:
                logger.error(f'Collector error: {e}')
                if self._running:
                    time.sleep(10)

    def _parse_line(self, line):
        # Strip WM1303Backend log prefix to get raw pkt_fwd output
        # Format: "2026-04-01 22:44:02,334 WM1303Backend INFO pkt_fwd: SPECTRAL SCAN - ..."
        import re as _re
        m = _re.search(r'pkt_fwd:\s*(.*)', line)
        if m:
            line = m.group(1)
        # Skip periodic status lines (they start with '#' or contain percentages)
        if line.startswith('#') or '%' in line:
            return  # Not actual LBT events
        ts = time.time()

        # ---- SPECTRAL SCAN ----
        # Format: "SPECTRAL SCAN - 863000000 Hz: 0 0 0 0 ... 36 0 0 0"
        m = re.match(r'SPECTRAL SCAN\s*-\s*(\d+)\s*Hz:\s*(.+)', line)
        if m:
            freq_hz = int(m.group(1))
            bin_str = m.group(2).strip()
            try:
                bins = [int(x) for x in bin_str.split()]
                avg_rssi = histogram_to_rssi(bins)
                peak_rssi = histogram_to_peak_rssi(bins)
                # Store the peak RSSI (more useful for visualization)
                rssi = peak_rssi if peak_rssi is not None else -140.0
                self._store_spectrum(ts, freq_hz / 1e6, rssi)
            except (ValueError, IndexError) as e:
                logger.debug(f'Failed to parse spectral scan bins: {e}')
            return

        # ---- LBT Events ----
        # "LBT: channel 869462500 clear" or "LBT: channel busy"
        m = re.search(r'LBT.*?channel\s+(\d+).*?(clear|busy|free|blocked)', line, re.IGNORECASE)
        if m:
            freq = int(m.group(1))
            clear = m.group(2).lower() in ('clear', 'free')
            rssi_m = re.search(r'rssi\s*[=:]?\s*(-?[\d.]+)', line, re.IGNORECASE)
            rssi = float(rssi_m.group(1)) if rssi_m else None
            self._store_lbt(ts, freq, rssi, clear)
            return

        # "WARNING: TX rejected (LBT)" or "TX failed: LBT CHANNEL_FREE"
        if 'LBT' in line.upper():
            if 'reject' in line.lower() or 'busy' in line.lower() or 'fail' in line.lower():
                self._store_lbt(ts, 0, None, False)
                return
            if 'clear' in line.lower() or 'free' in line.lower() or 'ok' in line.lower():
                self._store_lbt(ts, 0, None, True)
                return

        # ---- TX errors (could be LBT related) ----
        if 'TX rejected' in line or 'tx_status=FAIL' in line:
            self._store_lbt(ts, 0, None, False)
            return

        # ---- CAD detection ----
        m = re.search(r'CAD.*?(detected|not detected|activity|no activity)', line, re.IGNORECASE)
        if m:
            detected = 'not' not in m.group(1).lower() and 'no' not in m.group(1).lower()
            rssi_m = re.search(r'rssi\s*[=:]?\s*(-?[\d.]+)', line, re.IGNORECASE)
            rssi = float(rssi_m.group(1)) if rssi_m else None
            freq_m = re.search(r'(\d{9})', line)
            freq = int(freq_m.group(1)) if freq_m else None
            self._store_cad(ts, freq, detected, rssi)
            return

    def _store_spectrum(self, ts, freq_mhz, rssi_dbm):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute('INSERT INTO spectrum_scans(timestamp,freq_mhz,rssi_dbm) VALUES(?,?,?)',
                        (ts, freq_mhz, rssi_dbm))
            conn.execute('DELETE FROM spectrum_scans WHERE timestamp < ?', (ts - 604800,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f'Store spectrum error: {e}')

    def _store_lbt(self, ts, freq_hz, rssi, clear):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute('INSERT INTO lbt_events(timestamp,channel_freq_hz,rssi_dbm,channel_clear,tx_allowed) VALUES(?,?,?,?,?)',
                        (ts, freq_hz, rssi, int(clear), int(clear)))
            conn.execute('DELETE FROM lbt_events WHERE timestamp < ?', (ts - 604800,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f'Store LBT error: {e}')

    def _store_cad(self, ts, freq_hz, detected, rssi):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute('INSERT INTO cad_events(timestamp,freq_hz,cad_detected,rssi_dbm) VALUES(?,?,?,?)',
                        (ts, freq_hz, int(detected), rssi))
            conn.execute('DELETE FROM cad_events WHERE timestamp < ?', (ts - 604800,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f'Store CAD error: {e}')

    def get_spectrum_history(self, hours=24):
        cutoff = time.time() - (hours * 3600)
        try:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                'SELECT timestamp, freq_mhz, rssi_dbm FROM spectrum_scans WHERE timestamp >= ? ORDER BY timestamp',
                (cutoff,)
            ).fetchall()
            conn.close()
            return [{'timestamp': r[0], 'freq_mhz': r[1], 'rssi_dbm': r[2]} for r in rows]
        except Exception as e:
            logger.error(f'Get spectrum history error: {e}')
            return []

    def get_lbt_history(self, hours=24):
        cutoff = time.time() - (hours * 3600)
        try:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                'SELECT timestamp, channel_freq_hz, rssi_dbm, channel_clear, tx_allowed FROM lbt_events WHERE timestamp >= ? ORDER BY timestamp',
                (cutoff,)
            ).fetchall()
            conn.close()
            return [{'timestamp': r[0], 'channel_freq_hz': r[1], 'rssi_dbm': r[2], 'channel_clear': bool(r[3]), 'tx_allowed': bool(r[4])} for r in rows]
        except Exception as e:
            logger.error(f'Get LBT history error: {e}')
            return []

    def get_cad_history(self, hours=24):
        cutoff = time.time() - (hours * 3600)
        try:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                'SELECT timestamp, freq_hz, cad_detected, rssi_dbm FROM cad_events WHERE timestamp >= ? ORDER BY timestamp',
                (cutoff,)
            ).fetchall()
            conn.close()
            return [{'timestamp': r[0], 'freq_hz': r[1], 'cad_detected': bool(r[2]), 'rssi_dbm': r[3]} for r in rows]
        except Exception as e:
            logger.error(f'Get CAD history error: {e}')
            return []


# Singleton
_collector = None
def get_collector():
    global _collector
    if _collector is None:
        _collector = SpectrumCollector()
        _collector.start()
    return _collector
