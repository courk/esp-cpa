#include <fx2usb.h>

void handle_usb_setup(__xdata struct usb_req_setup *request) {
  request;
  STALL_EP0();
}
