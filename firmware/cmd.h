#ifndef CMD_H
#define CMD_H

#include <fx2lib.h>
#include <stdint.h>
#include <stdbool.h>

bool cmd_reply_available();
uint16_t cmd_reply_get();
void process_cmd_buffer(const __xdata uint8_t *buffer, uint16_t buffer_size);

#endif
