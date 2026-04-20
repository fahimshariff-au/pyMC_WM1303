/*
 / _____)             _              | |
( (____  _____ ____ _| |_ _____  ____| |__
 \____ \| ___ |    (_   _) ___ |/ ___)  _ \
 _____) ) ____| | | || |_| ____( (___| | | |
(______/|_____)_|_|_| \__)_____)\____)_| |_|
  (C)2020 Semtech

Description:
    LoRa concentrator Listen-Before-Talk functions

License: Revised BSD License, see LICENSE.TXT file include in the project
*/


/* -------------------------------------------------------------------------- */
/* --- DEPENDANCIES --------------------------------------------------------- */

/* fix an issue between POSIX and C99 */
#if __STDC_VERSION__ >= 199901L
    #define _XOPEN_SOURCE 600
#else
    #define _XOPEN_SOURCE 500
#endif

#include <stdio.h>      /* printf */
#include <stdlib.h>     /* llabs */

#include "loragw_aux.h"
#include "loragw_lbt.h"
#include "loragw_sx1261.h"
#include "loragw_sx1302.h"
#include "loragw_hal.h"

/* -------------------------------------------------------------------------- */
/* --- PRIVATE MACROS ------------------------------------------------------- */

#if DEBUG_LBT == 1
    #define DEBUG_MSG(str)                fprintf(stdout, str)
    #define DEBUG_PRINTF(fmt, args...)    fprintf(stdout,"%s:%d: "fmt, __FUNCTION__, __LINE__, args)
#else
    #define DEBUG_MSG(str)
    #define DEBUG_PRINTF(fmt, args...)
#endif

/* -------------------------------------------------------------------------- */
/* --- PRIVATE FUNCTIONS DEFINITION ----------------------------------------- */

/* As given frequencies have been converted from float to integer, some aliasing
issues can appear, so we can't simply check for equality, but have to take some
margin */
static bool is_equal_freq(uint32_t a, uint32_t b) {
    int64_t diff;
    int64_t a64 = (int64_t)a;
    int64_t b64 = (int64_t)b;

    /* Calculate the difference */
    diff = llabs(a64 - b64);

    /* Check for acceptable diff range */
    return ((diff <= 10000) ? true : false);
}

/* ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */

/* Check if TX bandwidth matches an LBT channel bandwidth.
   Exact match is preferred. Relaxed fallback: BW_62K5HZ TX can also match
   BW_125KHZ LBT channels (a wider scan still covers the narrower TX band).
   This fallback is kept as a safety net in case the LBT channel is configured
   with 125 kHz while the TX uses 62.5 kHz. */
static bool is_matching_bw(uint8_t tx_bw, uint8_t lbt_bw) {
    if (tx_bw == lbt_bw) {
        return true;
    }
    /* BW_62K5HZ (0x03) TX can use BW_125KHZ (0x04) LBT channel as fallback */
    if (tx_bw == BW_62K5HZ && lbt_bw == BW_125KHZ) {
        return true;
    }
    return false;
}

/* ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */

static int is_lbt_channel(const struct lgw_conf_lbt_s * lbt_context, uint32_t freq_hz, uint8_t bandwidth) {
    int i;
    int lbt_channel_match = -1;

    for (i = 0; i <  lbt_context->nb_channel; i++) {
        if ((is_equal_freq(freq_hz, lbt_context->channels[i].freq_hz) == true) && (is_matching_bw(bandwidth, lbt_context->channels[i].bandwidth) == true)) {
            DEBUG_PRINTF("LBT: select channel %d (freq:%u Hz, bw:0x%02X, tx_bw:0x%02X)\n", i, lbt_context->channels[i].freq_hz, lbt_context->channels[i].bandwidth, bandwidth);
            lbt_channel_match = i;
            break;
        }
    }

    /* Return the index of the LBT channel which matched */
    return lbt_channel_match;
}

/* -------------------------------------------------------------------------- */
/* --- PUBLIC FUNCTIONS DEFINITION ------------------------------------------ */

int lgw_lbt_start(const struct lgw_conf_sx1261_s * sx1261_context, const struct lgw_pkt_tx_s * pkt) {
    int err;
    int lbt_channel_selected;
    uint32_t toa_ms;
    /* performances variables */
    struct timeval tm;

    /* Record function start time */
    _meas_time_start(&tm);

    /* Check if we have a LBT channel for this transmit frequency */
    lbt_channel_selected = is_lbt_channel(&(sx1261_context->lbt_conf), pkt->freq_hz, pkt->bandwidth);
    if (lbt_channel_selected == -1) {
        printf("ERROR: Cannot start LBT - wrong channel\n");
        return -1;
    }

    /* Check if the packet Time On Air exceeds the maximum allowed transmit time on this channel */
    /* Channel sensing is checked 1.5ms before the packet departure time, so need to take this into account */
    if (sx1261_context->lbt_conf.channels[lbt_channel_selected].transmit_time_ms * 1000 <= 1500) {
        printf("ERROR: Cannot start LBT - channel transmit_time_ms must be > 1.5ms\n");
        return -1;
    }
    toa_ms = lgw_time_on_air(pkt);
    if ((toa_ms * 1000) > (uint32_t)(sx1261_context->lbt_conf.channels[lbt_channel_selected].transmit_time_ms * 1000 - 1500)) {
        printf("ERROR: Cannot start LBT - packet time on air exceeds allowed transmit time (toa:%ums, max:%ums)\n", toa_ms, sx1261_context->lbt_conf.channels[lbt_channel_selected].transmit_time_ms);
        return -1;
    }

    /* Set LBT scan frequency */
    err = sx1261_set_rx_params(pkt->freq_hz, pkt->bandwidth);
    if (err != 0) {
        printf("ERROR: Cannot start LBT - unable to set sx1261 RX parameters\n");
        return -1;
    }

    /* Start LBT */
    err = sx1261_lbt_start(sx1261_context->lbt_conf.channels[lbt_channel_selected].scan_time_us, sx1261_context->lbt_conf.rssi_target + sx1261_context->rssi_offset);
    if (err != 0) {
        printf("ERROR: Cannot start LBT - sx1261 LBT start\n");
        return -1;
    }

    _meas_time_stop(3, tm, __FUNCTION__);

    return 0;
}

/* ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */

int lgw_lbt_tx_status(uint8_t rf_chain, bool * tx_ok) {
    int err;
    uint8_t status;
    bool tx_timeout = false;
    struct timeval tm_start;
    /* performances variables */
    struct timeval tm;

    /* Record function start time */
    _meas_time_start(&tm);

    /* Wait for transmit to be initiated */
    /* Bit 0 in status: TX has been initiated on Radio A */
    /* Bit 1 in status: TX has been initiated on Radio B */
    timeout_start(&tm_start);
    do {
        /* handle timeout */
        if (timeout_check(tm_start, 500) != 0) {
            printf("ERROR: %s: TIMEOUT on TX start, not started\n", __FUNCTION__);
            tx_timeout = true;
            /* we'll still perform the AGC clear status and return an error to upper layer */
            break;
        }

        /* get tx status */
        err = sx1302_agc_status(&status);
        if (err != 0) {
            printf("ERROR: %s: failed to get AGC status\n", __FUNCTION__);
            return -1;
        }
        wait_ms(1);
    } while ((status & (1 << rf_chain)) == 0x00);

    if (tx_timeout == false) {
        /* Check if the packet has been transmitted or blocked by LBT */
        /* Bit 6 in status: Radio A is not allowed to transmit */
        /* Bit 7 in status: Radio B is not allowed to transmit */
        if (TAKE_N_BITS_FROM(status, ((rf_chain == 0) ? 6 : 7), 1) == 0) {
            *tx_ok = true;
        } else {
            *tx_ok = false;
        }
    }

    /* Clear AGC transmit status */
    sx1302_agc_mailbox_write(0, 0xFF);

    /* Wait for transmit status to be cleared */
    timeout_start(&tm_start);
    do {
        /* handle timeout */
        if (timeout_check(tm_start, 500) != 0) {
            printf("ERROR: %s: TIMEOUT on TX start (AGC clear status)\n", __FUNCTION__);
            tx_timeout = true;
            break;
        }

        /* get tx status */
        err = sx1302_agc_status(&status);
        if (err != 0) {
            printf("ERROR: %s: failed to get AGC status\n", __FUNCTION__);
            return -1;
        }
        wait_ms(1);
    } while (status != 0x00);

    /* Acknoledge */
    sx1302_agc_mailbox_write(0, 0x00);

    _meas_time_stop(3, tm, __FUNCTION__);

    if (tx_timeout == true) {
        return -1;
    } else {
        return 0;
    }
}

/* ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */

int lgw_lbt_stop(void) {
    int err;

    /* performances variables */
    struct timeval tm;

    /* Record function start time */
    _meas_time_start(&tm);

    err = sx1261_lbt_stop();
    if (err != 0) {
        printf("ERROR: Cannot stop LBT - failed\n");
        return -1;
    }

    _meas_time_stop(3, tm, __FUNCTION__);

    return 0;
}


/* ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */

/**
 * @brief Perform a real-time SX1261 RSSI check before TX (custom LBT).
 *
 * This is an alternative to the HAL's built-in LBT mechanism which relies on
 * AGC firmware handshake (broken on WM1303: lgw_lbt_tx_status() always times out).
 *
 * Instead, this function:
 * 1. Tunes SX1261 to the TX frequency (stops Channel E LoRa RX, starts GFSK RX)
 * 2. Waits for RSSI to settle (~5ms)
 * 3. Reads instantaneous RSSI via GetRssiInst command
 * 4. Stops GFSK RX and restarts Channel E LoRa RX
 * 5. Returns whether TX is allowed based on RSSI vs threshold
 *
 * Total Channel E RX pause: ~8-10ms per TX packet.
 *
 * @param freq_hz       TX frequency in Hz
 * @param bandwidth     TX bandwidth (BW_125KHZ, BW_250KHZ, BW_62K5HZ)
 * @param rssi_target   RSSI threshold in dBm (e.g., -80). TX allowed if RSSI < threshold.
 * @param rssi_offset   SX1261 RSSI offset from calibration
 * @param rssi_measured pointer to store the measured RSSI value (can be NULL)
 * @param tx_ok         pointer to store whether TX is allowed (true=clear, false=busy)
 * @return 0 on success, -1 on failure (hardware error)
 */
int lgw_lbt_rssi_check(uint32_t freq_hz, uint8_t bandwidth, int8_t rssi_target,
                       int8_t rssi_offset, int16_t *rssi_measured, bool *tx_ok) {
    int err;
    int16_t rssi_inst = 0;
    /* performances variables */
    struct timeval tm;

    /* Record function start time */
    _meas_time_start(&tm);

    /* Validate parameters */
    if (tx_ok == NULL) {
        printf("ERROR: %s: NULL tx_ok pointer\n", __FUNCTION__);
        return -1;
    }

    /* Default: allow TX (fail-open to avoid blocking all TX on errors) */
    *tx_ok = true;

    /* Step 1: Tune SX1261 to TX frequency and start GFSK RX for RSSI measurement.
     * This automatically stops Channel E LoRa RX if it was active. */
    err = sx1261_set_rx_params(freq_hz, bandwidth);
    if (err != 0) {
        printf("WARNING: [lbt_rssi] Failed to set SX1261 RX params for %u Hz, allowing TX\n", freq_hz);
        /* Fail-open: allow TX if we can't set up the measurement */
        _meas_time_stop(3, tm, __FUNCTION__);
        return 0;
    }

    /* Step 2: Wait for RSSI to settle.
     * The SX1261 needs a short time in GFSK RX mode for a stable RSSI reading.
     * 2ms is sufficient based on testing (reduced from 5ms). */
    wait_ms(2);

    /* Step 3: Read instantaneous RSSI */
    err = sx1261_get_rssi_inst(&rssi_inst);
    if (err != 0) {
        printf("WARNING: [lbt_rssi] Failed to read RSSI at %u Hz, allowing TX\n", freq_hz);
        /* Fail-open: allow TX if we can't read RSSI */
        sx1261_lbt_stop(); /* clean up: stop GFSK RX, restart Channel E LoRa RX */
        _meas_time_stop(3, tm, __FUNCTION__);
        return 0;
    }

    /* Apply RSSI offset from SX1261 calibration */
    rssi_inst += rssi_offset;

    /* Step 4: Stop GFSK RX and restart Channel E LoRa RX */
    err = sx1261_lbt_stop();
    if (err != 0) {
        printf("WARNING: [lbt_rssi] Failed to stop LBT/restart LoRa RX\n");
        /* Non-fatal: continue with the RSSI result we already have */
    }

    /* Step 5: Compare RSSI against threshold */
    if (rssi_inst >= rssi_target) {
        *tx_ok = false;
        printf("INFO: [lbt_rssi] Channel BUSY at %u Hz: RSSI=%d dBm >= threshold=%d dBm\n",
               freq_hz, rssi_inst, rssi_target);
    } else {
        *tx_ok = true;
        DEBUG_PRINTF("[lbt_rssi] Channel CLEAR at %u Hz: RSSI=%d dBm < threshold=%d dBm\n",
                     freq_hz, rssi_inst, rssi_target);
    }

    /* Return measured RSSI if requested */
    if (rssi_measured != NULL) {
        *rssi_measured = rssi_inst;
    }

    _meas_time_stop(3, tm, __FUNCTION__);

    return 0;
}

/* --- EOF ------------------------------------------------------------------ */
