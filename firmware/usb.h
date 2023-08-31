#ifndef _USB_H
#define _USB_H

#include <stdbool.h>

void usb_configure_cdc_acm();
void usb_configure_sampling();
void usb_set_descriptors(bool sampling_mode);

#endif
