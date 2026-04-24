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

/*
 * capture_thread.h
 */
#ifndef _CAPTURE_THREAD_H
#define _CAPTURE_THREAD_H

#include <stdint.h>
#include <stdbool.h>
#include "parson.h"

typedef struct capture_conf_s {
    bool     enable;
    uint8_t  source;
    uint16_t period;
    int      udp_port;
} capture_conf_t;

extern capture_conf_t capture_conf;

void capture_conf_parse(JSON_Object *obj);
bool capture_conf_enabled(void);
void *thread_capture_ram(void *arg);
void capture_thread_stop(void);

#endif
