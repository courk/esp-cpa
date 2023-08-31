#ifndef TARGET_SERIAL_H
#define TARGET_SERIAL_H

#include <stdint.h>
#include <stdbool.h>

void target_serial_init(bool slow_baudrate);
void target_serial_deinit();
void target_serial_write(uint8_t b);
void target_serial_slow_baudrate();
void target_serial_high_baudrate();

#endif
