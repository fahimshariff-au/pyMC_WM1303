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


/*
 * ----------------------------------------------------------------------
 * pyMC_WM1303 — WM1303 Repeater adaptations
 * ----------------------------------------------------------------------
 * Copyright (c) 2026 HansvanMeer  (GitHub: @HansvanMeer)
 *
 * Licensed under the PolyForm Noncommercial License 1.0.0.
 * See LICENSE and COMMERCIAL.md in the pyMC_WM1303 repository:
 *   https://github.com/HansvanMeer/pyMC_WM1303
 *
 * Any portions of this file derived from Semtech's sx1302_hal remain
 * under Semtech's Revised BSD License (where applicable, see header
 * above). Modifications and original additions in this file are
 * licensed under PolyForm Noncommercial 1.0.0.
 *
 * Commercial use is NOT permitted without a separate written agreement.
 * See COMMERCIAL.md for commercial licensing inquiries.
 * ----------------------------------------------------------------------
 */

#ifndef _LORAGW_LBT_H
#define _LORAGW_LBT_H

/* -------------------------------------------------------------------------- */
/* --- DEPENDANCIES --------------------------------------------------------- */

#include <stdint.h>     /* C99 types */
#include <stdbool.h>    /* bool type */

#include "loragw_hal.h"

#include "config.h"     /* library configuration options (dynamically generated) */

/* -------------------------------------------------------------------------- */
/* --- PUBLIC MACROS -------------------------------------------------------- */

/* -------------------------------------------------------------------------- */
/* --- PUBLIC CONSTANTS ----------------------------------------------------- */

/* -------------------------------------------------------------------------- */
/* --- PUBLIC TYPES --------------------------------------------------------- */

/* -------------------------------------------------------------------------- */
/* --- PUBLIC FUNCTIONS PROTOTYPES ------------------------------------------ */

/**
@brief Configure the SX1261 and start LBT channel scanning
@param sx1261_context the sx1261 radio parameters to take into account for scanning
@param pkt description of the packet to be transmitted
@return 0 for success, -1 for failure
*/
int lgw_lbt_start(const struct lgw_conf_sx1261_s * sx1261_context, const struct lgw_pkt_tx_s * pkt);

/**
@brief Stop LBT scanning
@return 0 for success, -1 for failure
*/
int lgw_lbt_stop(void);

/**
@brief Check if packet was allowed to be transmitted or not
@param rf_chain the TX path on which TX was requested
@param tx_ok pointer to return if the packet was allowed to be transmitted or not.
@return 0 for success, -1 for failure
*/
/**
@brief Perform a real-time SX1261 RSSI check before TX (custom LBT).
       This bypasses the broken AGC-based HAL LBT mechanism.
@param freq_hz       TX frequency in Hz
@param bandwidth     TX bandwidth (BW_125KHZ, BW_250KHZ, BW_62K5HZ)
@param rssi_target   RSSI threshold in dBm. TX allowed if RSSI < threshold.
@param rssi_offset   SX1261 RSSI offset from calibration
@param rssi_measured pointer to store measured RSSI value (can be NULL)
@param tx_ok         pointer to return whether TX is allowed
@return 0 for success, -1 for failure
*/
int lgw_lbt_rssi_check(uint32_t freq_hz, uint8_t bandwidth, int8_t rssi_target,
                       int8_t rssi_offset, int16_t *rssi_measured, bool *tx_ok);

int lgw_lbt_tx_status(uint8_t rf_chain, bool * tx_ok);

#endif

/* --- EOF ------------------------------------------------------------------ */
