"""Configuration file for ESP32C6 data acquisition."""

target_name = "esp32c6"

averaging = 16
n_samples = 1024
n_measurements = 600_000

# 16-bytes block of flash data to target
# for the attack
block_target = [1]

# Gain of the main amplifier
amplifier_gain = 50  # %

# Regulated temperature target
dut_temperature = 35  # °C

clk40 = False  # Downclock the system
usb_acm_mode = False  # Don't use firmware in ACM mode
