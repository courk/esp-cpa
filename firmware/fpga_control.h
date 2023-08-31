#ifndef FPGA_CONTROL_H
#define FPGA_CONTROL_H

#include <stdint.h>
#include <stdbool.h>

int fpga_control_init();
int fpga_control_set_dut_power(bool pwr);
int fpga_control_set_dut_en(bool en);
int fpga_control_set_dut_boot_en(bool boot, bool en);
int fpga_control_set_dut_boot(bool boot);
int fpga_control_set_dut_clk_en(bool en);
int fpga_control_set_flash_payload(const uint8_t *data);
int fpga_control_set_n_adc_samples(uint8_t n_samples);
int fpga_control_set_n_measurement_cycles(uint8_t cycle_shift);
int fpga_control_start_measurement();
int fpga_set_heater_pwm(uint8_t value);

#endif
