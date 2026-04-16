#!/usr/bin/env python3
"""Generate all 5 architecture diagrams for pyMC WM1303 documentation."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import os

# ============================================================
# SHARED STYLE CONSTANTS
# ============================================================
BG = '#0f172a'
CARD = '#1e293b'
BORDER = '#334155'
INNER = '#283548'
TP = '#f8fafc'
TS = '#94a3b8'
TM = '#64748b'
ACCENT = '#6366f1'
PURPLE = '#8b5cf6'
GREEN = '#22c55e'
PINK = '#f472b6'
ORANGE = '#fb923c'
INDIGO_L = '#818cf8'
TEAL = '#34d399'
YELLOW = '#f59e0b'
RED = '#ef4444'

LAYERS = {
    'hw':  {'fill': '#1a1a2e', 'brd': '#6366f1', 'lbl': '#818cf8'},
    'hal': {'fill': '#1a2332', 'brd': '#8b5cf6', 'lbl': '#a78bfa'},
    'be':  {'fill': '#1a2e1a', 'brd': '#22c55e', 'lbl': '#34d399'},
    'web': {'fill': '#2e1a2e', 'brd': '#f472b6', 'lbl': '#f472b6'},
}

SANS = 'DejaVu Sans'
MONO = 'DejaVu Sans Mono'
OUT = '/a0/usr/projects/pyMC_WM1303/docs/images'
os.makedirs(OUT, exist_ok=True)


def rgba(h, a=1.0):
    h = h.lstrip('#')
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


def mkfig(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.set_aspect('equal')
    ax.axis('off')
    return fig, ax


def rbox(ax, x, y, w, h, fc=CARD, ec=BORDER, a=1.0, lw=1.5, z=1, r=0.3):
    b = FancyBboxPatch((x, y), w, h, boxstyle=f'round,pad=0,rounding_size={r}',
                       facecolor=rgba(fc, a), edgecolor=ec, linewidth=lw, zorder=z)
    ax.add_patch(b)
    return b


def lbox(ax, x, y, w, h, lk, z=1):
    L = LAYERS[lk]
    rbox(ax, x, y, w, h, fc=L['fill'], ec=L['brd'], a=0.20, lw=2.0, z=z, r=0.4)


def cbox(ax, x, y, w, h, ec=BORDER, z=2):
    rbox(ax, x, y, w, h, fc=INNER, ec=ec, a=0.85, lw=1.0, z=z, r=0.2)


def txt(ax, x, y, s, fs=11, c=TP, w='normal', ha='center', va='center', mono=False, z=10):
    ax.text(x, y, s, fontsize=fs, color=c, weight=w, ha=ha, va=va,
            fontfamily=MONO if mono else SANS, zorder=z)


def arw(ax, x1, y1, x2, y2, c=ACCENT, lw=2.0, sty='->', cs='arc3,rad=0', z=5):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=sty, color=c,
                        linewidth=lw, connectionstyle=cs, zorder=z, mutation_scale=15)
    ax.add_patch(a)


# Channel colors used across diagrams
CHAN = ['Channel A', 'Channel B', 'Channel C', 'Channel D']
CC = [ACCENT, GREEN, YELLOW, PINK]




# ============================================================
# DIAGRAM 1: Architecture Overview (30x54, 150 DPI)
# — EXTREME spacing: huge canvas, small boxes, massive gaps
# ============================================================
def diagram1():
    W, H = 30, 54
    fig, ax = mkfig(W, H)

    txt(ax, W / 2, H - 1.0, 'pyMC WM1303 \u2014 System Architecture', fs=18, c=TP, w='bold')
    txt(ax, W / 2, H - 1.8, 'Layered architecture overview', fs=11, c=TS)

    ml = 2.0            # margin left/right (generous)
    lw = W - 2 * ml     # layer width = 26.0
    LAYER_GAP = 6.0     # MASSIVE inter-layer gap
    INNER_GAP = 3.0     # big gap between sub-sections inside backend
    COMP_GAP = 2.0      # horizontal gap between component boxes
    PAD = 2.0           # padding inside each layer boundary

    # ---- Compute layer positions (top to bottom) ----
    # Hardware layer
    hw_h = 8.0
    hw_y = H - 3.0 - hw_h  # 43.0

    # HAL layer — 6.0 gap below hardware
    hal_h = 6.0
    hal_y = hw_y - LAYER_GAP - hal_h  # 31.0

    # Backend layer — 6.0 gap below HAL
    be_h = 22.0
    be_y = hal_y - LAYER_GAP - be_h  # 3.0

    # Web layer — 6.0 gap below backend
    web_h = 6.0
    web_y = be_y - LAYER_GAP - web_h  # -9.0 ... need to adjust

    # Recalculate from bottom up to fit in canvas
    web_y = 1.0
    web_h = 6.0
    be_y = web_y + web_h + LAYER_GAP  # 13.0
    be_h = 22.0
    hal_y = be_y + be_h + LAYER_GAP   # 41.0
    hal_h = 6.0
    hw_y = hal_y + hal_h + LAYER_GAP  # 53.0 — too high

    # Adjust: place hw at top, calculate downward
    hw_y = H - 3.0 - 8.0   # top of hw at y=43, hw from 43 to 51
    hw_h = 8.0
    hal_y = hw_y - LAYER_GAP - 6.0  # 43 - 6 - 6 = 31
    hal_h = 6.0
    be_h = 20.0
    be_y = hal_y - LAYER_GAP - be_h  # 31 - 6 - 20 = 5
    web_h = 4.0
    web_y = 0.5  # pin to bottom
    # Gap between web top and be bottom = be_y - (web_y + web_h) = 5 - 4.5 = 0.5 — too small
    # Let me recalculate more carefully for the available 54 units
    # Title takes ~3 units at top
    # Available: 54 - 3 = 51 units
    # 4 layers + 3 gaps = hw_h + hal_h + be_h + web_h + 3*6.0
    # = 8 + 6 + 20 + 5 + 18 = 57 — too much
    # Reduce layer heights: hw=7, hal=5, be=16, web=4 = 32 + 18 = 50. Fits in 51.

    hw_h = 7.0
    hal_h = 5.5
    be_h = 17.0
    web_h = 4.5
    total_needed = hw_h + hal_h + be_h + web_h + 3 * LAYER_GAP  # 34 + 18 = 52
    bottom_margin = 0.8
    top_margin = 2.5  # for title

    # Place from top down
    hw_top = H - top_margin
    hw_y = hw_top - hw_h
    hal_y = hw_y - LAYER_GAP - hal_h
    be_y = hal_y - LAYER_GAP - be_h
    web_y = be_y - LAYER_GAP - web_h

    # ================================================================
    # HARDWARE LAYER
    # ================================================================
    lbox(ax, ml, hw_y, lw, hw_h, 'hw')
    txt(ax, ml + 0.6, hw_y + hw_h - 0.4, 'HARDWARE LAYER',
        fs=12, c=LAYERS['hw']['lbl'], w='bold', ha='left')

    # WM1303 Pi HAT Module box — small relative to layer
    hat_x = ml + PAD
    hat_w = lw - 2 * PAD  # 22.0
    hat_h = 2.8
    hat_y = hw_y + hw_h - 1.2 - hat_h
    rbox(ax, hat_x, hat_y, hat_w, hat_h,
         fc=CARD, ec=LAYERS['hw']['brd'], a=0.6, lw=1.2, z=2, r=0.25)
    txt(ax, hat_x + hat_w / 2, hat_y + hat_h - 0.3,
        'WM1303 Pi HAT Module', fs=11, c=TP, w='bold')

    # 4 chip boxes inside HAT — max 4.0 wide each, 2.0 gap between
    chips = [
        ('SX1302/03', 'Baseband Processor'),
        ('SX1250_0', 'RF0 Radio (TX+RX)'),
        ('SX1250_1', 'RF1 Radio (RX only)'),
        ('SX1261', 'Companion (Spectral/LBT)'),
    ]
    cw, ch = 4.0, 1.2
    cgap = 2.0
    tot_cw = len(chips) * cw + (len(chips) - 1) * cgap  # 22.0
    csx = hat_x + (hat_w - tot_cw) / 2
    chip_y = hat_y + 0.3
    chip_cx = []
    for i, (nm, desc) in enumerate(chips):
        cx = csx + i * (cw + cgap)
        cbox(ax, cx, chip_y, cw, ch, ec=LAYERS['hw']['brd'], z=3)
        txt(ax, cx + cw / 2, chip_y + ch - 0.30, nm, fs=9, c=TP, w='bold')
        txt(ax, cx + cw / 2, chip_y + ch - 0.60, desc, fs=7, c=TS)
        chip_cx.append(cx + cw / 2)

    # Raspberry Pi 4 box — at bottom of hardware layer
    pi_h = 1.0
    pi_y = hw_y + 0.4
    pi_x, pi_w = ml + PAD, lw - 2 * PAD
    rbox(ax, pi_x, pi_y, pi_w, pi_h,
         fc=CARD, ec=LAYERS['hw']['brd'], a=0.6, lw=1.2, z=2, r=0.2)
    txt(ax, pi_x + pi_w / 2, pi_y + 0.58,
        'Raspberry Pi 4 (SenseCAP M1)', fs=10, c=TP, w='bold')
    txt(ax, pi_x + pi_w / 2, pi_y + 0.22,
        'GPIO: BCM17, BCM18, BCM5, BCM13  \u00b7  offset 512',
        fs=7, c=TM, mono=True)

    # SPI bus zone (between HAT bottom and Pi top)
    spi_zone_top = hat_y
    spi_zone_bot = pi_y + pi_h
    spi_mid = (spi_zone_top + spi_zone_bot) / 2

    # ARROW 1: SX1302/SX1250_0/SX1250_1 -> shared SPI bus -> /dev/spidev0.0
    bus0_y = spi_mid + 0.3
    for i in range(3):
        ax.plot([chip_cx[i], chip_cx[i]], [spi_zone_top, bus0_y],
                color=LAYERS['hw']['brd'], lw=1.0, zorder=4, solid_capstyle='round')
    ax.plot([chip_cx[0], chip_cx[2]], [bus0_y, bus0_y],
            color=LAYERS['hw']['brd'], lw=1.5, zorder=4, solid_capstyle='round')
    spi0_mid_x = (chip_cx[0] + chip_cx[2]) / 2
    txt(ax, spi0_mid_x, bus0_y + 0.2, 'SPI bus', fs=7, c=TM, mono=True)
    dev0_y = spi_mid - 0.2
    arw(ax, spi0_mid_x, bus0_y - 0.02, spi0_mid_x, dev0_y + 0.08,
        c=LAYERS['hw']['brd'], lw=1.0, sty='->')
    txt(ax, spi0_mid_x, dev0_y - 0.18, '/dev/spidev0.0 (2 MHz)',
        fs=7, c=TM, mono=True)

    # ARROW 2: SX1261 -> separate SPI bus -> /dev/spidev0.1
    sx1261_x = chip_cx[3]
    ax.plot([sx1261_x, sx1261_x], [spi_zone_top, bus0_y],
            color=LAYERS['hw']['brd'], lw=1.0, zorder=4, solid_capstyle='round')
    txt(ax, sx1261_x, bus0_y + 0.2, 'SPI bus', fs=7, c=TM, mono=True)
    arw(ax, sx1261_x, bus0_y - 0.02, sx1261_x, dev0_y + 0.08,
        c=LAYERS['hw']['brd'], lw=1.0, sty='->')
    txt(ax, sx1261_x, dev0_y - 0.18, '/dev/spidev0.1 (2 MHz)',
        fs=7, c=TM, mono=True)

    # ARROW 3: SPI device paths -> Pi box
    arw(ax, spi0_mid_x, dev0_y - 0.38, spi0_mid_x, spi_zone_bot + 0.02,
        c=LAYERS['hw']['brd'], lw=1.0, sty='->')
    arw(ax, sx1261_x, dev0_y - 0.38, sx1261_x, spi_zone_bot + 0.02,
        c=LAYERS['hw']['brd'], lw=1.0, sty='->')

    # ARROW 4: Hardware -> HAL (inter-layer) — traverses 6.0 units of empty space!
    hw_bot = hw_y
    hal_top = hal_y + hal_h
    arw(ax, W / 2, hw_bot - 0.05, W / 2, hal_top + 0.05,
        c=LAYERS['hw']['brd'], lw=2.5, sty='->')
    txt(ax, W / 2 + 0.8, (hw_bot + hal_top) / 2, 'SPI',
        fs=12, c=TM, ha='left', mono=True)

    # ================================================================
    # HAL & FORWARDER LAYER
    # ================================================================
    lbox(ax, ml, hal_y, lw, hal_h, 'hal')
    txt(ax, ml + 0.6, hal_y + hal_h - 0.4, 'HAL & FORWARDER LAYER',
        fs=12, c=LAYERS['hal']['lbl'], w='bold', ha='left')

    # libloragw.a (left) — 10 wide x 4 tall
    lib_x = ml + PAD
    lib_w, lib_h = 10.0, 4.0
    lib_y = hal_y + (hal_h - lib_h) / 2 - 0.2
    cbox(ax, lib_x, lib_y, lib_w, lib_h, ec=LAYERS['hal']['brd'], z=2)
    txt(ax, lib_x + lib_w / 2, lib_y + lib_h - 0.30,
        'libloragw.a (SX1302 HAL)', fs=10, c=TP, w='bold')
    for j, item in enumerate([
        'Board / RF / IF chain config', 'SX1250 radio control',
        'TX / RX packet handling', 'AGC management (debounced)',
        'FEM / LNA register control', 'SX1261 spectral scan',
        'Calibration routines',
    ]):
        txt(ax, lib_x + 0.4, lib_y + lib_h - 0.70 - j * 0.38,
            f'\u00b7  {item}', fs=8, c=TS, ha='left')

    # lora_pkt_fwd (right) — 10 wide x 4 tall, 2.0 gap from libloragw
    pkt_x = lib_x + lib_w + 2.0
    pkt_w, pkt_h = 10.0, 4.0
    pkt_y = lib_y
    cbox(ax, pkt_x, pkt_y, pkt_w, pkt_h, ec=LAYERS['hal']['brd'], z=2)
    txt(ax, pkt_x + pkt_w / 2, pkt_y + pkt_h - 0.30,
        'lora_pkt_fwd (Packet Forwarder)', fs=10, c=TP, w='bold')
    for j, item in enumerate([
        'UDP server (:1730)', 'PUSH_DATA (RX \u2192 UDP)',
        'PULL_RESP (UDP \u2192 TX)', 'TX_ACK feedback',
        'Spectral scan thread', 'JSON config loading',
    ]):
        txt(ax, pkt_x + 0.4, pkt_y + pkt_h - 0.70 - j * 0.38,
            f'\u00b7  {item}', fs=8, c=TS, ha='left')

    # ARROW 5: lora_pkt_fwd -> Backend (inter-layer) — 6.0 units of empty space!
    pkt_cx = pkt_x + pkt_w / 2
    hal_bot = hal_y
    be_top = be_y + be_h
    arw(ax, pkt_cx, hal_bot - 0.05, pkt_cx, be_top + 0.05,
        c=LAYERS['hal']['brd'], lw=2.5, sty='->')
    txt(ax, pkt_cx + 0.8, (hal_bot + be_top) / 2, 'UDP :1730',
        fs=12, c=TM, ha='left', mono=True)

    # ================================================================
    # BACKEND LAYER
    # ================================================================
    lbox(ax, ml, be_y, lw, be_h, 'be')
    txt(ax, ml + 0.6, be_y + be_h - 0.4, 'BACKEND LAYER',
        fs=12, c=LAYERS['be']['lbl'], w='bold', ha='left')

    ip = PAD  # inner padding = 2.0
    iw = lw - 2 * ip  # inner width = 22.0

    # WM1303 Backend sub-box (top section of backend)
    wb_h = 4.0
    wb_y = be_y + be_h - 1.2 - wb_h
    wb_x = ml + ip
    rbox(ax, wb_x, wb_y, iw, wb_h,
         fc=CARD, ec=LAYERS['be']['brd'], a=0.5, lw=1.2, z=2, r=0.25)
    txt(ax, wb_x + iw / 2, wb_y + wb_h - 0.30,
        'WM1303 Backend', fs=11, c=TP, w='bold')

    # 3 component boxes inside WM1303 Backend — max 4.0 wide, 2.5 tall, 2.0 gap
    comp_data = [
        ('UDP Handler', ['_handle_udp()', 'Retry TX-free']),
        ('NoiseFloor Monitor', ['30s cycle', 'PUSH_DATA stats',
                                'Spectral harvest', 'Rolling buffer']),
        ('RX Watchdog', ['3 detect modes', 'RSSI spike detect',
                         'RX timeout (180s)']),
    ]
    comp_w = 4.0
    comp_h = 2.5
    num_comp = len(comp_data)
    total_comp_w = num_comp * comp_w + (num_comp - 1) * COMP_GAP  # 16.0
    comp_start_x = wb_x + (iw - total_comp_w) / 2
    comp_y = wb_y + 0.3
    comp_cx_list = []
    for i, (nm, items) in enumerate(comp_data):
        cx = comp_start_x + i * (comp_w + COMP_GAP)
        cbox(ax, cx, comp_y, comp_w, comp_h, ec=LAYERS['be']['brd'], z=3)
        txt(ax, cx + comp_w / 2, comp_y + comp_h - 0.28, nm,
            fs=9, c=TP, w='bold')
        for j, it in enumerate(items):
            txt(ax, cx + comp_w / 2, comp_y + comp_h - 0.65 - j * 0.32,
                it, fs=7.5, c=TS)
        comp_cx_list.append(cx + comp_w / 2)

    # VirtualLoRaRadio bar — 3.0 gap below WM1303 Backend
    vlr_h = 1.2
    vlr_y = wb_y - INNER_GAP - vlr_h
    vlr_x, vlr_w = ml + ip, iw
    rbox(ax, vlr_x, vlr_y, vlr_w, vlr_h,
         fc=CARD, ec=PINK, a=0.5, lw=1.2, z=2, r=0.2)
    txt(ax, vlr_x + 1.5, vlr_y + vlr_h / 2,
        'VirtualLoRaRadio:', fs=10, c=TP, w='bold', ha='left')
    for i, (cn, co) in enumerate(zip(CHAN, CC)):
        bx = vlr_x + 6.0 + i * 3.8
        rbox(ax, bx, vlr_y + 0.12, 3.2, vlr_h - 0.24,
             fc=co, ec=co, a=0.15, lw=1, z=3, r=0.15)
        txt(ax, bx + 1.6, vlr_y + vlr_h / 2, cn, fs=8.5, c=co, w='bold')

    # ARROW 6: UDP Handler -> VirtualLoRaRadio
    arw(ax, comp_cx_list[0], comp_y - 0.05,
        comp_cx_list[0], vlr_y + vlr_h + 0.05,
        c=LAYERS['be']['brd'], lw=1.5, sty='->')

    # ARROW 7: NoiseFloor Monitor -> VirtualLoRaRadio
    arw(ax, comp_cx_list[1], comp_y - 0.05,
        comp_cx_list[1], vlr_y + vlr_h + 0.05,
        c=LAYERS['be']['brd'], lw=1.5, sty='->')

    # Bridge Engine box — 3.0 gap below VirtualLoRaRadio
    br_h = 2.2
    br_y = vlr_y - INNER_GAP - br_h
    br_x = ml + ip
    rbox(ax, br_x, br_y, iw, br_h,
         fc=CARD, ec=LAYERS['be']['brd'], a=0.5, lw=1.2, z=2, r=0.25)
    txt(ax, br_x + iw / 2, br_y + br_h - 0.30,
        'Bridge Engine', fs=11, c=TP, w='bold')
    txt(ax, br_x + iw / 2, br_y + br_h - 0.70,
        '1. RX packet on channel_x  \u2192  2. Dedup check  \u2192  '
        '3. Bridge rules evaluation  \u2192  4. Repeater handler (hop +1)',
        fs=7.5, c=TS)
    txt(ax, br_x + iw / 2, br_y + br_h - 1.05,
        '5. Packet-type filtering  \u2192  6. TX batch window (2s)  \u2192  '
        '7. Fire sends to target TX queues',
        fs=7.5, c=TS)

    # ARROW 8: VirtualLoRaRadio -> Bridge Engine
    vlr_cx = vlr_x + vlr_w / 2
    arw(ax, vlr_cx, vlr_y - 0.05, vlr_cx, br_y + br_h + 0.05,
        c=PINK, lw=1.5, sty='->')

    # TX Queue boxes — 4 per channel, 4.0 wide, 1.5 tall, 1.5 gap — 3.0 below Bridge
    tq_h = 1.5
    tq_y = br_y - INNER_GAP - tq_h
    tq_w = 4.0
    tq_gap = 1.5
    tot_tq = 4 * tq_w + 3 * tq_gap  # 20.5
    tq_start_x = ml + ip + (iw - tot_tq) / 2
    tq_cx_list = []
    for i, (cn, co) in enumerate(zip(CHAN, CC)):
        tx = tq_start_x + i * (tq_w + tq_gap)
        rbox(ax, tx, tq_y, tq_w, tq_h,
             fc=co, ec=co, a=0.12, lw=1, z=2, r=0.15)
        txt(ax, tx + tq_w / 2, tq_y + tq_h - 0.28,
            'TX Queue', fs=9, c=co, w='bold')
        txt(ax, tx + tq_w / 2, tq_y + tq_h - 0.58, cn, fs=8, c=TS)
        txt(ax, tx + tq_w / 2, tq_y + 0.22,
            'LBT\u00b7CAD\u00b7TTL\u00b7Overflow\u00b7FIFO\u00b7Hold', fs=5.5, c=TM)
        tq_cx_list.append(tx + tq_w / 2)

    # ARROW 9: Bridge Engine -> fans out to TX Queues
    br_cx = br_x + iw / 2
    for tqcx in tq_cx_list:
        arw(ax, br_cx + (tqcx - br_cx) * 0.3, br_y - 0.05,
            tqcx, tq_y + tq_h + 0.05,
            c=LAYERS['be']['brd'], lw=1.0, sty='->')

    # ARROW 10: TX Queues merge -> down -> label
    merge_y = tq_y - 0.5
    for tqcx in tq_cx_list:
        ax.plot([tqcx, tqcx], [tq_y, merge_y],
                color=LAYERS['be']['brd'], lw=1.0, zorder=4)
    ax.plot([tq_cx_list[0], tq_cx_list[-1]], [merge_y, merge_y],
            color=LAYERS['be']['brd'], lw=1.5, zorder=4)
    merge_cx = (tq_cx_list[0] + tq_cx_list[-1]) / 2
    txt(ax, merge_cx, merge_y - 0.35,
        'PULL_RESP (UDP) \u2192 Packet Forwarder \u2192 Radio TX',
        fs=7.5, c=TM, mono=True)

    # ARROW 11: Backend -> Web/API (inter-layer) — 6.0 units of empty space!
    be_bot = be_y
    web_top = web_y + web_h
    arw(ax, W / 2, be_bot - 0.05, W / 2, web_top + 0.05,
        c=LAYERS['be']['brd'], lw=2.5, sty='->')
    txt(ax, W / 2 + 0.8, (be_bot + web_top) / 2,
        'HTTP / WebSocket', fs=12, c=TM, ha='left')

    # ================================================================
    # WEB / API LAYER
    # ================================================================
    lbox(ax, ml, web_y, lw, web_h, 'web')
    txt(ax, ml + 0.6, web_y + web_h - 0.4, 'WEB / API LAYER',
        fs=12, c=LAYERS['web']['lbl'], w='bold', ha='left')

    # Top row: HTTP Server, REST API, WebSocket — small boxes
    wc = [
        ('HTTP Server', 'Port 8000\nStatic files'),
        ('REST API', '/api/wm1303/*\nJWT auth'),
        ('WebSocket', 'Real-time updates\nStats push'),
    ]
    wc_gap = 2.0
    wc_w = (iw - 2 * wc_gap) / 3  # ~6.0 each
    wcx = ml + ip
    wcy = web_y + web_h - 0.7 - 1.2
    wch = 1.2
    for nm, desc in wc:
        cbox(ax, wcx, wcy, wc_w, wch, ec=LAYERS['web']['brd'], z=2)
        txt(ax, wcx + wc_w / 2, wcy + wch - 0.28, nm, fs=9, c=TP, w='bold')
        for j, ln in enumerate(desc.split('\n')):
            txt(ax, wcx + wc_w / 2, wcy + wch - 0.58 - j * 0.26,
                ln, fs=7.5, c=TS)
        wcx += wc_w + wc_gap

    # Bottom row: WM1303 Manager UI + pyMC Console
    ui_gap = 2.0
    ui1_w = iw * 0.55 - ui_gap / 2
    ui2_w = iw * 0.45 - ui_gap / 2
    ui_h = 1.4
    ui_y = web_y + 0.3

    cbox(ax, ml + ip, ui_y, ui1_w, ui_h, ec=LAYERS['web']['brd'], z=2)
    txt(ax, ml + ip + ui1_w / 2, ui_y + ui_h - 0.28,
        'WM1303 Manager UI', fs=9, c=TP, w='bold')
    txt(ax, ml + ip + ui1_w / 2, ui_y + ui_h - 0.58,
        'Tabs: Status | Channels | Bridge | Spectrum | Adv. Config',
        fs=7.5, c=TS)
    txt(ax, ml + ip + ui1_w / 2, ui_y + 0.20,
        'Charts: Signal Quality, LBT, CAD, Dedup, Spectrum  '
        '\u00b7  WebSocket-driven', fs=7, c=TS)

    ui2_x = ml + ip + ui1_w + ui_gap
    cbox(ax, ui2_x, ui_y, ui2_w, ui_h, ec=LAYERS['web']['brd'], z=2)
    txt(ax, ui2_x + ui2_w / 2, ui_y + ui_h - 0.28,
        'pyMC Console (Vue.js)', fs=9, c=TP, w='bold')
    txt(ax, ui2_x + ui2_w / 2, ui_y + ui_h / 2 - 0.05,
        'MeshCore functionality:', fs=7.5, c=TS)
    txt(ax, ui2_x + ui2_w / 2, ui_y + ui_h / 2 - 0.30,
        'nodes, mesh, messaging', fs=7.5, c=TS)

    out1 = os.path.join(OUT, 'architecture-overview.png')
    fig.savefig(out1, dpi=150, bbox_inches='tight', facecolor=BG, pad_inches=0.5)
    plt.close(fig)
    print(f'\u2705 Saved: {out1}')


# ============================================================
# DIAGRAM 2: Component Dependencies (28x36, 150 DPI)
# — EXTREME spacing: huge canvas, small nodes, massive gaps
# ============================================================
def diagram2():
    W, H = 18, 52
    fig, ax = mkfig(W, H)

    txt(ax, W / 2, H - 1.0, 'Component Dependency Graph', fs=18, c=TP, w='bold')
    txt(ax, W / 2, H - 2.2,
        'How components relate and depend on each other', fs=11, c=TS)

    # Tier Y positions (bottom to top) with 6.5 vertical gap between EVERY tier
    GAP = 6.5
    t1 = 2.0
    t2 = t1 + GAP      # 8.5
    t3 = t2 + GAP      # 15.0
    t4 = t3 + GAP      # 21.5
    t5 = t4 + GAP      # 28.0
    t6 = t5 + GAP      # 34.5
    t7 = t6 + GAP      # 41.0
    t8 = t7 + GAP      # 47.5

    # Node dimensions
    nw = 6.0   # all nodes same width
    nh = 1.8   # all nodes same height

    # Horizontal positions
    center_x = W / 2   # 9.0
    left_x = center_x - nw / 2 - 1.5   # 9 - 3 - 1.5 = 4.5
    right_x = center_x + nw / 2 + 1.5  # 9 + 3 + 1.5 = 13.5

    nodes = {
        'sx1302':    (left_x,    t1, 'SX1302 / SX1250',
                      LAYERS['hw']['brd']),
        'sx1261':    (right_x,   t1, 'SX1261',
                      LAYERS['hw']['brd']),
        'libloragw': (center_x,  t2, 'libloragw.a\n(SX1302 HAL)',
                      LAYERS['hal']['brd']),
        'pkt_fwd':   (center_x,  t3, 'lora_pkt_fwd\n(Packet Forwarder)',
                      LAYERS['hal']['brd']),
        'backend':   (center_x,  t4, 'WM1303 Backend',
                      LAYERS['be']['brd']),
        'pymc_core': (left_x,    t5, 'pymc_core\n(library)',
                      PURPLE),
        'pymc_rep':  (right_x,   t5, 'pymc_repeater\n(application)',
                      PURPLE),
        'vlr':       (left_x,    t6, 'VirtualLoRaRadio\nTXQueue / SX1261Driver',
                      TEAL),
        'bridge':    (right_x,   t6, 'Bridge Engine\nConfig Mgr / Packet Router',
                      GREEN),
        'api':       (center_x,  t7, 'WM1303 API\nHTTP Server / WebSocket',
                      PINK),
        'ui_wm':     (left_x,    t8, 'WM1303\nManager UI',
                      PINK),
        'ui_pymc':   (right_x,   t8, 'pyMC Repeater\nRepeater UI',
                      PINK),
    }

    for key, (nx, ny, label, color) in nodes.items():
        rbox(ax, nx - nw / 2, ny - nh / 2, nw, nh,
             fc=INNER, ec=color, a=0.85, lw=1.5, z=2, r=0.15)
        lines = label.split('\n')
        if len(lines) == 1:
            txt(ax, nx, ny, lines[0], fs=12, c=TP, w='bold')
        elif len(lines) == 2:
            txt(ax, nx, ny + 0.28, lines[0], fs=12, c=TP, w='bold')
            txt(ax, nx, ny - 0.28, lines[1], fs=9, c=TS)
        else:
            txt(ax, nx, ny + 0.35, lines[0], fs=12, c=TP, w='bold')
            for j, ln in enumerate(lines[1:]):
                txt(ax, nx, ny + 0.35 - 0.30 * (j + 1), ln, fs=9, c=TS)
    edges = [
        ('pkt_fwd',   'libloragw', 'C Library',        LAYERS['hal']['brd']),
        ('backend',   'pkt_fwd',   'UDP :1730',        LAYERS['be']['brd']),
        ('libloragw', 'sx1302',    'SPI',              LAYERS['hw']['brd']),
        ('libloragw', 'sx1261',    'SPI',              LAYERS['hw']['brd']),
        ('backend',   'pymc_core', 'Python Import',    LAYERS['be']['brd']),
        ('backend',   'pymc_rep',  'Python Import',    LAYERS['be']['brd']),
        ('pymc_core', 'vlr',       'Python API',       PURPLE),
        ('pymc_rep',  'bridge',    'Python API',       PURPLE),
        ('vlr',       'api',       'Internal API',     TEAL),
        ('bridge',    'api',       'Internal API',     GREEN),
        ('api',       'ui_wm',     'HTTP / WebSocket', PINK),
        ('api',       'ui_pymc',   'HTTP / WebSocket', PINK),
    ]

    for fr, to, label, color in edges:
        fx, fy = nodes[fr][0], nodes[fr][1]
        tx, ty = nodes[to][0], nodes[to][1]
        if fy > ty:
            y1 = fy - nh / 2
            y2 = ty + nh / 2
        else:
            y1 = fy + nh / 2
            y2 = ty - nh / 2
        # Perfectly straight arrows using annotate (no bezier curves)
        ax.annotate('', xy=(tx, y2), xytext=(fx, y1),
                    arrowprops=dict(arrowstyle='->', color=color, lw=1.5,
                                    mutation_scale=15),
                    zorder=5)
        if label:
            # Position label near the SOURCE node (15% along arrow)
            mx = fx + (tx - fx) * 0.15
            my = y1 + (y2 - y1) * 0.15
            # Offset label away from the arrow line
            if fx < tx:
                mx += 0.8
                ha = 'left'
            elif fx > tx:
                mx -= 0.8
                ha = 'right'
            else:
                mx += 0.8
                ha = 'left'
            ax.text(mx, my, label, fontsize=11, color=TP, ha=ha, va='center',
                    fontfamily='monospace', fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.2', fc=BG, ec='none', alpha=0.85),
                    zorder=10)

    # Tier labels on right margin
    tier_labels = [
        (t1, 'Hardware',       LAYERS['hw']['lbl']),
        (t2, 'HAL',            LAYERS['hal']['lbl']),
        (t3, 'Forwarder',      LAYERS['hal']['lbl']),
        (t4, 'Backend',        LAYERS['be']['lbl']),
        (t5, 'Libraries',      PURPLE),
        (t6, 'Components',     TEAL),
        (t7, 'API',            PINK),
        (t8, 'User Interface', PINK),
    ]
    for ty, lbl, col in tier_labels:
        txt(ax, W - 0.3, ty, lbl, fs=10, c=col, ha='right')

    out2 = os.path.join(OUT, 'component-dependencies.png')
    fig.savefig(out2, dpi=150, bbox_inches='tight', facecolor=BG, pad_inches=0.5)
    plt.close(fig)
    print(f'\u2705 Saved: {out2}')







# ============================================================
# DIAGRAM 3: RX Data Flow (16x6)
# ============================================================
def diagram3():
    W, H = 16, 6
    fig, ax = mkfig(W, H)

    txt(ax, W / 2, H - 0.4, 'RX Data Flow Path', fs=15, c=TP, w='bold')
    txt(ax, W / 2, H - 0.8, 'Radio → User Interface', fs=10, c=TS)

    # Flow steps in two rows
    steps_row1 = [
        ('RF Signal\n→ Antenna', LAYERS['hw']['brd']),
        ('SX1250\nRadio', LAYERS['hw']['brd']),
        ('SX1302\nBaseband', LAYERS['hw']['brd']),
        ('HAL\nlgw_receive()', LAYERS['hal']['brd']),
        ('Packet\nForwarder', LAYERS['hal']['brd']),
        ('PUSH_DATA\nUDP :1730', LAYERS['hal']['brd']),
    ]
    steps_row2 = [
        ('WM1303 Backend\n_handle_udp()', LAYERS['be']['brd']),
        ('Freq→Channel\nMapping', LAYERS['be']['brd']),
        ('VirtualLoRa\nRadio', PINK),
        ('Bridge Engine\nDedup + Rules', LAYERS['be']['brd']),
        ('SQLite\nLogging', TEAL),
        ('WebSocket\n→ UI Update', LAYERS['web']['brd']),
    ]

    bw, bh = 2.1, 1.1
    gap = 0.35
    row1_y = 3.3
    row2_y = 1.2

    # Row 1
    total_w = len(steps_row1) * bw + (len(steps_row1) - 1) * gap
    sx = (W - total_w) / 2
    total_w2 = len(steps_row2) * bw + (len(steps_row2) - 1) * gap
    sx2 = (W - total_w2) / 2

    for i, (label, color) in enumerate(steps_row1):
        bx = sx + i * (bw + gap)
        rbox(ax, bx, row1_y, bw, bh, fc=INNER, ec=color, a=0.85, lw=1.2, z=2, r=0.18)
        lines = label.split('\n')
        txt(ax, bx + bw / 2, row1_y + bh / 2 + 0.15, lines[0], fs=8.5, c=TP, w='bold')
        if len(lines) > 1:
            txt(ax, bx + bw / 2, row1_y + bh / 2 - 0.15, lines[1], fs=7.5, c=TS)
        if i < len(steps_row1) - 1:
            arw(ax, bx + bw + 0.02, row1_y + bh / 2, bx + bw + gap - 0.02, row1_y + bh / 2,
                c=INDIGO_L, lw=1.5, sty='->')

    # Arrow from last box of row1 down to first box of row2 (L-shaped)
    r1_last_x = sx + (len(steps_row1) - 1) * (bw + gap) + bw / 2
    r2_first_x = sx2 + bw / 2
    mid_y = (row1_y + row2_y + bh) / 2
    ax.plot([r1_last_x, r1_last_x], [row1_y - 0.02, mid_y], color=INDIGO_L,
            linewidth=1.5, zorder=5, solid_capstyle='round')
    ax.plot([r1_last_x, r2_first_x], [mid_y, mid_y], color=INDIGO_L,
            linewidth=1.5, zorder=5, solid_capstyle='round')
    arw(ax, r2_first_x, mid_y, r2_first_x, row2_y + bh + 0.02, c=INDIGO_L, lw=1.5, sty='->')

    # Row 2
    for i, (label, color) in enumerate(steps_row2):
        bx = sx2 + i * (bw + gap)
        rbox(ax, bx, row2_y, bw, bh, fc=INNER, ec=color, a=0.85, lw=1.2, z=2, r=0.18)
        lines = label.split('\n')
        txt(ax, bx + bw / 2, row2_y + bh / 2 + 0.15, lines[0], fs=8.5, c=TP, w='bold')
        if len(lines) > 1:
            txt(ax, bx + bw / 2, row2_y + bh / 2 - 0.15, lines[1], fs=7.5, c=TS)
        if i < len(steps_row2) - 1:
            arw(ax, bx + bw + 0.02, row2_y + bh / 2, bx + bw + gap - 0.02, row2_y + bh / 2,
                c=INDIGO_L, lw=1.5, sty='->')

    # Step number annotations
    for i in range(len(steps_row1)):
        bx = sx + i * (bw + gap)
        txt(ax, bx + bw / 2, row1_y + bh + 0.15, str(i + 1), fs=7, c=TM)
    for i in range(len(steps_row2)):
        bx = sx2 + i * (bw + gap)
        txt(ax, bx + bw / 2, row2_y - 0.2, str(i + 7), fs=7, c=TM)

    out3 = os.path.join(OUT, 'data-flow-rx.png')
    fig.savefig(out3, dpi=200, bbox_inches='tight', facecolor=BG, pad_inches=0.3)
    plt.close(fig)
    print(f'✅ Saved: {out3}')


# ============================================================
# DIAGRAM 4: TX Data Flow (16x6)
# ============================================================
def diagram4():
    W, H = 16, 6
    fig, ax = mkfig(W, H)

    txt(ax, W / 2, H - 0.4, 'TX Data Flow Path', fs=15, c=TP, w='bold')
    txt(ax, W / 2, H - 0.8, 'Bridge Decision → Radio Transmission', fs=10, c=TS)

    steps_row1 = [
        ('Bridge Engine\nDecision', LAYERS['be']['brd']),
        ('Repeater\nHandler', LAYERS['be']['brd']),
        ('TX Batch\nWindow (2s)', LAYERS['be']['brd']),
        ('Per-Channel\nTX Queue', PINK),
        ('Round-Robin\nScheduler', LAYERS['be']['brd']),
        ('TTL Check\n(5s max)', YELLOW),
    ]
    steps_row2 = [
        ('Queue Overflow\nCheck (15 max)', YELLOW),
        ('LBT Check\n(per-channel)', TEAL),
        ('CAD Check\n(HW/SW)', TEAL),
        ('PULL_RESP\nUDP :1730', LAYERS['hal']['brd']),
        ('HAL\nlgw_send()', LAYERS['hal']['brd']),
        ('SX1250 Radio\n→ RF TX', LAYERS['hw']['brd']),
    ]

    bw, bh = 2.1, 1.1
    gap = 0.35
    row1_y = 3.3
    row2_y = 1.2

    total_w = len(steps_row1) * bw + (len(steps_row1) - 1) * gap
    sx = (W - total_w) / 2
    total_w2 = len(steps_row2) * bw + (len(steps_row2) - 1) * gap
    sx2 = (W - total_w2) / 2

    for i, (label, color) in enumerate(steps_row1):
        bx = sx + i * (bw + gap)
        rbox(ax, bx, row1_y, bw, bh, fc=INNER, ec=color, a=0.85, lw=1.2, z=2, r=0.18)
        lines = label.split('\n')
        txt(ax, bx + bw / 2, row1_y + bh / 2 + 0.15, lines[0], fs=8.5, c=TP, w='bold')
        if len(lines) > 1:
            txt(ax, bx + bw / 2, row1_y + bh / 2 - 0.15, lines[1], fs=7.5, c=TS)
        if i < len(steps_row1) - 1:
            arw(ax, bx + bw + 0.02, row1_y + bh / 2, bx + bw + gap - 0.02, row1_y + bh / 2,
                c=TEAL, lw=1.5, sty='->')

    # Arrow from last box of row1 down to first box of row2 (L-shaped)
    r1_last_x = sx + (len(steps_row1) - 1) * (bw + gap) + bw / 2
    r2_first_x = sx2 + bw / 2
    mid_y = (row1_y + row2_y + bh) / 2
    ax.plot([r1_last_x, r1_last_x], [row1_y - 0.02, mid_y], color=TEAL,
            linewidth=1.5, zorder=5, solid_capstyle='round')
    ax.plot([r1_last_x, r2_first_x], [mid_y, mid_y], color=TEAL,
            linewidth=1.5, zorder=5, solid_capstyle='round')
    arw(ax, r2_first_x, mid_y, r2_first_x, row2_y + bh + 0.02, c=TEAL, lw=1.5, sty='->')

    for i, (label, color) in enumerate(steps_row2):
        bx = sx2 + i * (bw + gap)
        rbox(ax, bx, row2_y, bw, bh, fc=INNER, ec=color, a=0.85, lw=1.2, z=2, r=0.18)
        lines = label.split('\n')
        txt(ax, bx + bw / 2, row2_y + bh / 2 + 0.15, lines[0], fs=8.5, c=TP, w='bold')
        if len(lines) > 1:
            txt(ax, bx + bw / 2, row2_y + bh / 2 - 0.15, lines[1], fs=7.5, c=TS)
        if i < len(steps_row2) - 1:
            arw(ax, bx + bw + 0.02, row2_y + bh / 2, bx + bw + gap - 0.02, row2_y + bh / 2,
                c=TEAL, lw=1.5, sty='->')

    # TX_ACK feedback annotation
    last_bx2 = sx2 + (len(steps_row2) - 1) * (bw + gap)
    txt(ax, last_bx2 + bw / 2, row2_y - 0.25, 'TX_ACK feedback → Statistics update', fs=7, c=TM)

    # Step number annotations
    for i in range(len(steps_row1)):
        bx = sx + i * (bw + gap)
        txt(ax, bx + bw / 2, row1_y + bh + 0.15, str(i + 1), fs=7, c=TM)
    for i in range(len(steps_row2)):
        bx = sx2 + i * (bw + gap)
        txt(ax, bx + bw / 2, row2_y - 0.2, str(i + 7), fs=7, c=TM)

    out4 = os.path.join(OUT, 'data-flow-tx.png')
    fig.savefig(out4, dpi=200, bbox_inches='tight', facecolor=BG, pad_inches=0.3)
    plt.close(fig)
    print(f'✅ Saved: {out4}')


# ============================================================
# DIAGRAM 5: Spectral Scan Flow (16x6)
# ============================================================
def diagram5():
    W, H = 16, 5.5
    fig, ax = mkfig(W, H)

    txt(ax, W / 2, H - 0.4, 'Spectral Scan Flow', fs=15, c=TP, w='bold')
    txt(ax, W / 2, H - 0.8, 'NoiseFloor monitoring and spectral analysis path', fs=10, c=TS)

    steps_row1 = [
        ('NoiseFloor\nMonitor (30s)', ORANGE),
        ('Wait TX-free\nWindow', LAYERS['be']['brd']),
        ('SX1261 Spectral\nScan (spidev0.1)', LAYERS['hw']['brd']),
        ('Results →\n/tmp JSON', LAYERS['hal']['brd']),
    ]
    steps_row2 = [
        ('Per-Channel\nFreq Matching', PINK),
        ('RSSI Values →\nRolling Buffer', TEAL),
        ('Mutex Released\n(RX preserved)', LAYERS['be']['brd']),
        ('WebSocket →\nSpectrum Chart', LAYERS['web']['brd']),
    ]

    bw, bh = 3.0, 1.1
    gap = 0.5
    row1_y = 3.0
    row2_y = 1.0

    total_w = len(steps_row1) * bw + (len(steps_row1) - 1) * gap
    sx = (W - total_w) / 2
    total_w2 = len(steps_row2) * bw + (len(steps_row2) - 1) * gap
    sx2 = (W - total_w2) / 2

    for i, (label, color) in enumerate(steps_row1):
        bx = sx + i * (bw + gap)
        rbox(ax, bx, row1_y, bw, bh, fc=INNER, ec=color, a=0.85, lw=1.2, z=2, r=0.18)
        lines = label.split('\n')
        txt(ax, bx + bw / 2, row1_y + bh / 2 + 0.15, lines[0], fs=9, c=TP, w='bold')
        if len(lines) > 1:
            txt(ax, bx + bw / 2, row1_y + bh / 2 - 0.15, lines[1], fs=8, c=TS)
        if i < len(steps_row1) - 1:
            arw(ax, bx + bw + 0.02, row1_y + bh / 2, bx + bw + gap - 0.02, row1_y + bh / 2,
                c=ORANGE, lw=1.5, sty='->')

    # Arrow from last box of row1 down to first box of row2 (L-shaped)
    r1_last_x = sx + (len(steps_row1) - 1) * (bw + gap) + bw / 2
    r2_first_x = sx2 + bw / 2
    mid_y = (row1_y + row2_y + bh) / 2
    ax.plot([r1_last_x, r1_last_x], [row1_y - 0.02, mid_y], color=ORANGE,
            linewidth=1.5, zorder=5, solid_capstyle='round')
    ax.plot([r1_last_x, r2_first_x], [mid_y, mid_y], color=ORANGE,
            linewidth=1.5, zorder=5, solid_capstyle='round')
    arw(ax, r2_first_x, mid_y, r2_first_x, row2_y + bh + 0.02, c=ORANGE, lw=1.5, sty='->')

    for i, (label, color) in enumerate(steps_row2):
        bx = sx2 + i * (bw + gap)
        rbox(ax, bx, row2_y, bw, bh, fc=INNER, ec=color, a=0.85, lw=1.2, z=2, r=0.18)
        lines = label.split('\n')
        txt(ax, bx + bw / 2, row2_y + bh / 2 + 0.15, lines[0], fs=9, c=TP, w='bold')
        if len(lines) > 1:
            txt(ax, bx + bw / 2, row2_y + bh / 2 - 0.15, lines[1], fs=8, c=TS)
        if i < len(steps_row2) - 1:
            arw(ax, bx + bw + 0.02, row2_y + bh / 2, bx + bw + gap - 0.02, row2_y + bh / 2,
                c=ORANGE, lw=1.5, sty='->')

    # Annotations
    txt(ax, W / 2, row2_y - 0.3, 'Dynamic range based on RF chain center frequency  ·  20-sample rolling buffer per TX queue',
        fs=7, c=TM)

    for i in range(len(steps_row1)):
        bx = sx + i * (bw + gap)
        txt(ax, bx + bw / 2, row1_y + bh + 0.15, str(i + 1), fs=7, c=TM)
    for i in range(len(steps_row2)):
        bx = sx2 + i * (bw + gap)
        txt(ax, bx + bw / 2, row2_y - 0.15, str(i + 5), fs=7, c=TM)

    out5 = os.path.join(OUT, 'spectral-scan-flow.png')
    fig.savefig(out5, dpi=200, bbox_inches='tight', facecolor=BG, pad_inches=0.3)
    plt.close(fig)
    print(f'✅ Saved: {out5}')


# ============================================================
# GENERATE ALL DIAGRAMS
# ============================================================
if __name__ == '__main__':
    print('Generating all 5 diagrams...')
    print()
    diagram1()
    diagram2()
    diagram3()
    diagram4()
    diagram5()
    print()
    print('✅ All 5 diagrams generated successfully!')
