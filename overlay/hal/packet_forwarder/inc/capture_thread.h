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
