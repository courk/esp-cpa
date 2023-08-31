#include "usb.h"

#include <fx2lib.h>
#include <fx2regs.h>
#include <fx2usb.h>
#include <usbcdc.h>
#include <fx2delay.h>

usb_desc_device_c usb_device = {
    .bLength = sizeof(struct usb_desc_device),
    .bDescriptorType = USB_DESC_DEVICE,
    .bcdUSB = 0x0200,
    .bDeviceClass = USB_DEV_CLASS_PER_INTERFACE,
    .bDeviceSubClass = USB_DEV_SUBCLASS_PER_INTERFACE,
    .bDeviceProtocol = USB_DEV_PROTOCOL_PER_INTERFACE,
    .bMaxPacketSize0 = 64,
    .idVendor = 0x04b4,
    .idProduct = 0x8613,
    .bcdDevice = 0x0000,
    .iManufacturer = 1,
    .iProduct = 2,
    .iSerialNumber = 0,
    .bNumConfigurations = 1,
};

usb_desc_interface_c usb_iface_cic = {
    .bLength = sizeof(struct usb_desc_interface),
    .bDescriptorType = USB_DESC_INTERFACE,
    .bInterfaceNumber = 0,
    .bAlternateSetting = 0,
    .bNumEndpoints = 1,
    .bInterfaceClass = USB_IFACE_CLASS_CIC,
    .bInterfaceSubClass = USB_IFACE_SUBCLASS_CDC_CIC_ACM,
    .bInterfaceProtocol = USB_IFACE_PROTOCOL_CDC_CIC_NONE,
    .iInterface = 0,
};

usb_cdc_desc_functional_header_c usb_func_cic_header = {
    .bLength = sizeof(struct usb_cdc_desc_functional_header),
    .bDescriptorType = USB_DESC_CS_INTERFACE,
    .bDescriptorSubType = USB_DESC_CDC_FUNCTIONAL_SUBTYPE_HEADER,
    .bcdCDC = 0x0120,
};

usb_cdc_desc_functional_acm_c usb_func_cic_acm = {
    .bLength = sizeof(struct usb_cdc_desc_functional_acm),
    .bDescriptorType = USB_DESC_CS_INTERFACE,
    .bDescriptorSubType = USB_DESC_CDC_FUNCTIONAL_SUBTYPE_ACM,
    .bmCapabilities = 0,
};

usb_cdc_desc_functional_union_c usb_func_cic_union = {
    .bLength = sizeof(struct usb_cdc_desc_functional_union) +
               sizeof(uint8_t) * 1,
    .bDescriptorType = USB_DESC_CS_INTERFACE,
    .bDescriptorSubType = USB_DESC_CDC_FUNCTIONAL_SUBTYPE_UNION,
    .bControlInterface = 0,
    .bSubordinateInterface = {1},
};

usb_desc_interface_c usb_iface_dic = {
    .bLength = sizeof(struct usb_desc_interface),
    .bDescriptorType = USB_DESC_INTERFACE,
    .bInterfaceNumber = 1,
    .bAlternateSetting = 0,
    .bNumEndpoints = 2,
    .bInterfaceClass = USB_IFACE_CLASS_DIC,
    .bInterfaceSubClass = USB_IFACE_SUBCLASS_CDC_DIC,
    .bInterfaceProtocol = USB_IFACE_PROTOCOL_CDC_DIC_NONE,
    .iInterface = 0,
};

// CDC-ACM OUT
usb_desc_endpoint_c usb_endpoint_ep6_out = {
    .bLength = sizeof(struct usb_desc_endpoint),
    .bDescriptorType = USB_DESC_ENDPOINT,
    .bEndpointAddress = 6,
    .bmAttributes = USB_XFER_BULK,
    .wMaxPacketSize = 512,
    .bInterval = 0,
};

// CDC-ACM IN
usb_desc_endpoint_c usb_endpoint_ep8_in = {
    .bLength = sizeof(struct usb_desc_endpoint),
    .bDescriptorType = USB_DESC_ENDPOINT,
    .bEndpointAddress = 8 | USB_DIR_IN,
    .bmAttributes = USB_XFER_BULK,
    .wMaxPacketSize = 512,
    .bInterval = 0,
};

// CDC-ACM INT
usb_desc_endpoint_c usb_endpoint_ep_fake_in = {
    .bLength = sizeof(struct usb_desc_endpoint),
    .bDescriptorType = USB_DESC_ENDPOINT,
    .bEndpointAddress = 9 | USB_DIR_IN,
    .bmAttributes = USB_XFER_INTERRUPT,
    .wMaxPacketSize = 8,
    .bInterval = 10,
};

usb_desc_interface_c usb_iface_vendor_ctrl_acm = {
    .bLength = sizeof(struct usb_desc_interface),
    .bDescriptorType = USB_DESC_INTERFACE,
    .bInterfaceNumber = 2,
    .bAlternateSetting = 0,
    .bNumEndpoints = 2,
    .bInterfaceClass = USB_IFACE_CLASS_VENDOR,
    .bInterfaceSubClass = USB_IFACE_SUBCLASS_VENDOR,
    .bInterfaceProtocol = USB_IFACE_PROTOCOL_VENDOR,
    .iInterface = 0,
};

// Vendor control OUT
usb_desc_endpoint_c usb_endpoint_ep1_out = {
    .bLength = sizeof(struct usb_desc_endpoint),
    .bDescriptorType = USB_DESC_ENDPOINT,
    .bEndpointAddress = 1,
    .bmAttributes = USB_XFER_BULK,
    .wMaxPacketSize = 512, // Warning: actually 64
    .bInterval = 0,
};

// Vendor control IN
usb_desc_endpoint_c usb_endpoint_ep1_in = {
    .bLength = sizeof(struct usb_desc_endpoint),
    .bDescriptorType = USB_DESC_ENDPOINT,
    .bEndpointAddress = 1 | USB_DIR_IN,
    .bmAttributes = USB_XFER_BULK,
    .wMaxPacketSize = 512, // Warning: actually 64
    .bInterval = 0,
};

usb_configuration_c usb_acm_config = {
    {
        .bLength = sizeof(struct usb_desc_configuration),
        .bDescriptorType = USB_DESC_CONFIGURATION,
        .bNumInterfaces = 3,
        .bConfigurationValue = 1,
        .iConfiguration = 0,
        .bmAttributes = USB_ATTR_RESERVED_1,
        .bMaxPower = 250,
    },
    {{.interface = &usb_iface_cic},
     {.generic = (struct usb_desc_generic *)&usb_func_cic_header},
     {.generic = (struct usb_desc_generic *)&usb_func_cic_acm},
     {.generic = (struct usb_desc_generic *)&usb_func_cic_union},
     {.endpoint = &usb_endpoint_ep_fake_in},
     {.interface = &usb_iface_dic},
     {.endpoint = &usb_endpoint_ep6_out},
     {.endpoint = &usb_endpoint_ep8_in},
     {.interface = &usb_iface_vendor_ctrl_acm},
     {.endpoint = &usb_endpoint_ep1_out},
     {.endpoint = &usb_endpoint_ep1_in},
     {0}}};

usb_configuration_set_c usb_acm_configs[] = {
    &usb_acm_config,
};

usb_ascii_string_c usb_acm_strings[] = {
    [0] = "courk@courk.cc",
    [1] = "ESP-CPA-Board in ACM mode",
};

usb_desc_interface_c usb_iface_sampling = {
    .bLength = sizeof(struct usb_desc_interface),
    .bDescriptorType = USB_DESC_INTERFACE,
    .bInterfaceNumber = 0,
    .bAlternateSetting = 0,
    .bNumEndpoints = 1,
    .bInterfaceClass = USB_IFACE_CLASS_VENDOR,
    .bInterfaceSubClass = USB_IFACE_SUBCLASS_VENDOR,
    .bInterfaceProtocol = USB_IFACE_PROTOCOL_VENDOR,
    .iInterface = 0,
};

// Sampling IN
usb_desc_endpoint_c usb_endpoint_ep2_in = {
    .bLength = sizeof(struct usb_desc_endpoint),
    .bDescriptorType = USB_DESC_ENDPOINT,
    .bEndpointAddress = 2 | USB_DIR_IN,
    .bmAttributes = USB_XFER_BULK,
    .wMaxPacketSize = 512,
    .bInterval = 0,
};

usb_desc_interface_c usb_iface_vendor_ctrl_sampling = {
    .bLength = sizeof(struct usb_desc_interface),
    .bDescriptorType = USB_DESC_INTERFACE,
    .bInterfaceNumber = 1,
    .bAlternateSetting = 0,
    .bNumEndpoints = 2,
    .bInterfaceClass = USB_IFACE_CLASS_VENDOR,
    .bInterfaceSubClass = USB_IFACE_SUBCLASS_VENDOR,
    .bInterfaceProtocol = USB_IFACE_PROTOCOL_VENDOR,
    .iInterface = 0,
};

usb_configuration_c usb_sampling_config = {
    {
        .bLength = sizeof(struct usb_desc_configuration),
        .bDescriptorType = USB_DESC_CONFIGURATION,
        .bNumInterfaces = 2,
        .bConfigurationValue = 1,
        .iConfiguration = 0,
        .bmAttributes = USB_ATTR_RESERVED_1,
        .bMaxPower = 250,
    },
    {{.interface = &usb_iface_sampling},
     {.endpoint = &usb_endpoint_ep2_in},
     {.interface = &usb_iface_vendor_ctrl_sampling},
     {.endpoint = &usb_endpoint_ep1_out},
     {.endpoint = &usb_endpoint_ep1_in},
     {0}}};

usb_configuration_set_c usb_sampling_configs[] = {
    &usb_sampling_config,
};

usb_ascii_string_c usb_sampling_strings[] = {
    [0] = "courk@courk.cc",
    [1] = "ESP-CPA-Board in sampling mode",
};

__xdata struct usb_descriptor_set usb_descriptor_set = {
    .device = &usb_device,
    .config_count = ARRAYSIZE(usb_acm_configs),
    .configs = usb_acm_configs,
    .string_count = ARRAYSIZE(usb_acm_strings),
    .strings = usb_acm_strings,
};

/**
 * @brief Configure the descriptors for the given mode.
 *
 * @param sampling_mode true for sampling mode, false for cdc-acm mode
 */
void usb_set_descriptors(bool sampling_mode)
{
    if (sampling_mode)
    {
        usb_descriptor_set.config_count = ARRAYSIZE(usb_sampling_configs);
        usb_descriptor_set.configs = usb_sampling_configs;
        usb_descriptor_set.string_count = ARRAYSIZE(usb_sampling_strings);
        usb_descriptor_set.strings = usb_sampling_strings;
    }
    else
    {
        usb_descriptor_set.config_count = ARRAYSIZE(usb_acm_configs);
        usb_descriptor_set.configs = usb_acm_configs;
        usb_descriptor_set.string_count = ARRAYSIZE(usb_acm_strings);
        usb_descriptor_set.strings = usb_acm_strings;
    }
}

/**
 * @brief Configure the endpoints for CDC-ACM mode
 *
 */
void usb_configure_cdc_acm()
{
    // NAK all transfers.
    FIFORESET = _NAKALL;
    SYNCDELAY;

    // EP1 (vendor control) is configured as 64-byte BULK IN/OUT
    EP1INCFG = _VALID | _TYPE1;
    EP1OUTCFG = _VALID | _TYPE1;

    // EP6 (CDC-ACM) is configured as 512-byte double buffed BULK OUT
    EP6CFG = _VALID | _TYPE1 | _BUF1;
    EP6CS = 0;

    // EP8 (CDC-ACM) is configured as 512-byte double buffed BULK IN
    EP8CFG = _VALID | _DIR | _TYPE1 | _BUF1;
    EP8CS = 0;

    // Other endpoints are not used
    EP2CFG &= ~_VALID;
    EP4CFG &= ~_VALID;

    // Enable IN-BULK-NAK interrupt for EP8 and EPI1
    IBNIE = _IBNI_EP8 | _IBNI_EP1;
    NAKIE = _IBN;

    // Reset and prime EP6. Reset EP8.
    SYNCDELAY;
    FIFORESET = _NAKALL | 6;
    SYNCDELAY;
    OUTPKTEND = _SKIP | 6;
    SYNCDELAY;
    OUTPKTEND = _SKIP | 6;
    SYNCDELAY;
    FIFORESET = _NAKALL | 8;
    SYNCDELAY;
    FIFORESET = 0;

    // Empty EP1OUT
    EP1OUTBC = 0;
}

/**
 * @brief Configure the endpoints for sampling mode
 *
 */
void usb_configure_sampling()
{
    // NAK all transfers.
    FIFORESET = _NAKALL;
    SYNCDELAY;

    // EP1 (vendor control) is configured as 64-byte BULK IN/OUT
    EP1INCFG = _VALID | _TYPE1;
    EP1OUTCFG = _VALID | _TYPE1;

    // EP2 (sampling) is configured as 512-byte quad buffed BULK IN
    EP2CFG = _VALID | _DIR | _TYPE1 | _SIZE;
    EP2CS = 0;

    // Other endpoints are not used
    EP4CFG &= ~_VALID;
    EP6CFG &= ~_VALID;
    EP8CFG &= ~_VALID;

    // Enable IN-BULK-NAK interrupt for EPI1
    IBNIE = _IBNI_EP1;
    NAKIE = _IBN;

    // Reset EP2
    FIFORESET = _NAKALL | 2;
    SYNCDELAY;
    FIFORESET = 0;

    // Configure the EP2 FIFO
    EP2FIFOCFG = _AUTOIN | _WORDWIDE;
    SYNCDELAY;

    // Configure EP2 to auto-commit 512 bytes packets
    EP2AUTOINLENH = 0x02;
    SYNCDELAY;
    EP2AUTOINLENL = 0x00;
    SYNCDELAY;

    // Empty EP1OUT
    EP1OUTBC = 0;
}