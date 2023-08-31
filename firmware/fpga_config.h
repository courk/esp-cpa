#ifndef FPGA_CONFIG_H
#define FPGA_CONFIG_H

#include <stdint.h>
#include <fx2lib.h>

void fpga_config_start();
void fpga_config_send(const __xdata uint8_t *data, uint16_t len);
int fpga_config_terminate();

#endif
