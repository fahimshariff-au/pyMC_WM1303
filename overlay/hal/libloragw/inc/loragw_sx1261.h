/*
 / _____)             _              | |
( (____  _____ ____ _| |_ _____  ____| |__
 \____ \| ___ |    (_   _) ___ |/ ___)  _ \
 _____) ) ____| | | || |_| ____( (___| | | |
(______/|_____)_|_|_| \__)_____)\____)_| |_|
  (C)2019 Semtech

Description:
    Functions used to handle LoRa concentrator SX1261 radio used to handle LBT,
    Spectral Scan, CAD and LoRa RX (Channel E).

License: Revised BSD License, see LICENSE.TXT file include in the project
*/


#ifndef _LORAGW_SX1261_H
#define _LORAGW_SX1261_H

/* -------------------------------------------------------------------------- */
/* --- DEPENDANCIES --------------------------------------------------------- */

#include <stdint.h>     /* C99 types*/
#include <stdbool.h>    /* bool type */

#include "loragw_hal.h"
#include "sx1261_defs.h"

#include "config.h"     /* library configuration options (dynamically generated) */

/* -------------------------------------------------------------------------- */
/* --- PUBLIC MACROS -------------------------------------------------------- */

/* -------------------------------------------------------------------------- */
/* --- PUBLIC CONSTANTS ----------------------------------------------------- */

static const char sx1261_pram_version_string[] = "2D06";

/* -------------------------------------------------------------------------- */
/* --- PUBLIC TYPES --------------------------------------------------------- */

/* -------------------------------------------------------------------------- */
/* --- PUBLIC FUNCTIONS PROTOTYPES ------------------------------------------ */

int sx1261_connect(lgw_com_type_t com_type, const char *com_path);
int sx1261_disconnect(void);

int sx1261_reg_w(sx1261_op_code_t op_code, uint8_t *data, uint16_t size);
int sx1261_reg_r(sx1261_op_code_t op_code, uint8_t *data, uint16_t size);

int sx1261_load_pram(void);
int sx1261_calibrate(uint32_t freq_hz);
int sx1261_setup(void);
int sx1261_set_rx_params(uint32_t freq_hz, uint8_t bandwidth);

int sx1261_lbt_start(lgw_lbt_scan_time_t scan_time_us, int8_t threshold_dbm);
int sx1261_lbt_stop(void);

int sx1261_spectral_scan_start(uint16_t nb_scan);
int sx1261_spectral_scan_status(lgw_spectral_scan_status_t * status);
int sx1261_spectral_scan_get_results(int8_t rssi_offset, int16_t * levels_dbm, uint16_t * results);
int sx1261_spectral_scan_abort(void);

/* CAD (Channel Activity Detection) - hardware LoRa preamble detection */
typedef struct {
    bool     detected;       /* true if LoRa preamble was detected */
    int16_t  rssi_dbm;       /* instantaneous RSSI at time of CAD */
    uint8_t  status;         /* 0=ok, 1=timeout, 2=error */
} sx1261_cad_result_t;

int sx1261_cad_scan(uint32_t freq_hz, uint8_t sf, uint8_t bw, sx1261_cad_result_t *result);

/* LoRa RX (Channel E) - continuous LoRa reception on SX1261 */
int sx1261_lora_rx_configure(uint32_t freq_hz, uint8_t bw, uint8_t sf, uint8_t cr, bool boosted);
int sx1261_lora_rx_start(void);
/**
 * @brief Lightweight pause for TX blanking (STDBY_XOSC, <1ms)
 */
int sx1261_lora_rx_pause(void);

/**
 * @brief Lightweight resume after TX blanking (CLR_IRQ + SetRx, <1ms)
 */
int sx1261_lora_rx_resume(void);

int sx1261_lora_rx_stop(void);
int sx1261_lora_rx_fetch(struct lgw_pkt_rx_s *pkt_data, uint8_t max_pkt);
bool sx1261_lora_rx_active(void);

/**
 * @brief Read instantaneous RSSI from SX1261 (must be in RX mode)
 * @param rssi_dbm  pointer to store RSSI value in dBm
 * @return LGW_REG_SUCCESS on success, LGW_REG_ERROR on failure
 */
int sx1261_get_rssi_inst(int16_t *rssi_dbm);

int sx1261_lora_rx_restart_light(void);

#endif

/* --- EOF ------------------------------------------------------------------ */
