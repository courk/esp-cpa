TARGET = firmware
LIBRARIES = fx2 fx2usb fx2isrs
MODEL = medium

SOURCES = main fpga_config debug_serial target_serial cmd gpif gain_control fpga_control temperature_sensor usb

CFLAGS = -DUSB_ACM_MODE=$(USB_ACM_MODE)

LIBFX2 = ./lib/libfx2/firmware/library
include $(LIBFX2)/fx2rules.mk
