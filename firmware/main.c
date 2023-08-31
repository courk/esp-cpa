#include <fx2lib.h>
#include <fx2regs.h>
#include <fx2delay.h>
#include <fx2ints.h>
#include <fx2usb.h>
#include <usbcdc.h>
#include <ctype.h>
#include <stdio.h>

#include "usb.h"
#include "board.h"
#include "debug_serial.h"
#include "target_serial.h"
#include "cmd.h"
#include "gain_control.h"
#include "fpga_control.h"

/**
 * @brief TIMER0 IRQ handler
 *
 */
void isr_TF0() __interrupt(_INT_TF0)
{
    static int i;
    if (i++ % 64 == 0)
    {
        LED_OUT = !LED_OUT; // Toggle the LED
    }
}

/**
 * @brief Start the timer-based LED blinking system
 *
 */
static void start_blinky()
{
    // Configure LED pin
    LED_OUT = 1;
    OEC |= (1 << LED_PIN);

    // Configure TIMER0
    TCON = _M0_0; // use 16-bit counter mode
    ET0 = 1;      // generate an interrupt
    TR0 = 1;      // run
}

/**
 * @brief Called when EP0 is accessed, used to handle CDC-ACM out-of-band requests
 *
 * @param req
 */
void handle_usb_setup(__xdata struct usb_req_setup *req)
{
    if (req->bmRequestType == (USB_RECIP_IFACE | USB_TYPE_CLASS | USB_DIR_OUT) &&
        req->bRequest == USB_CDC_PSTN_REQ_SET_CONTROL_LINE_STATE &&
        req->wLength == 0)
    {
        bool rts = req->wValue & 1;
        bool dtr = (req->wValue >> 1) & 1;

        // Stay compatible with esp-tools defaults
        bool en;
        bool boot;

        if (dtr & !rts)
        {
            en = false;
        }
        else
        {
            en = true;
        }

        if (!dtr & rts)
        {
            boot = false;
        }
        else
        {
            boot = true;
        }

        if (fpga_control_set_dut_boot(boot) < 0)
        {
            STALL_EP0();
            return;
        }

        if (fpga_control_set_dut_en(en) < 0)
        {
            STALL_EP0();
            return;
        }
        ACK_EP0();
        return;
    }

    if (req->bmRequestType == (USB_RECIP_IFACE | USB_TYPE_CLASS | USB_DIR_IN) &&
        req->bRequest == USB_CDC_PSTN_REQ_GET_LINE_CODING &&
        req->wLength == 7)
    {
        __xdata struct usb_cdc_req_line_coding *line_coding =
            (__xdata struct usb_cdc_req_line_coding *)EP0BUF;
        line_coding->dwDTERate = 115200;
        line_coding->bCharFormat = USB_CDC_REQ_LINE_CODING_STOP_BITS_1;
        line_coding->bParityType = USB_CDC_REQ_LINE_CODING_PARITY_NONE;
        line_coding->bDataBits = 8;
        SETUP_EP0_BUF(sizeof(struct usb_cdc_req_line_coding));
        return;
    }

    if (req->bmRequestType == (USB_RECIP_IFACE | USB_TYPE_CLASS | USB_DIR_OUT) &&
        req->bRequest == USB_CDC_PSTN_REQ_SET_LINE_CODING &&
        req->wLength == 7)
    {
        SETUP_EP0_BUF(0);
        return;
    }

    STALL_EP0();
}

volatile bool pending_ep1_in = false;
volatile bool pending_ep8_in = false;

/**
 * @brief IBN IRQ handler
 *
 */
void isr_IBN() __interrupt
{
    uint32_t mask = 0;
    uint8_t ibnie = IBNIE;
    IBNIE = 0;
    CLEAR_USB_IRQ();

    if (IBNIRQ & _IBNI_EP1)
    {
        pending_ep1_in = true;
        mask |= _IBNI_EP1;
    }
    if (IBNIRQ & _IBNI_EP8)
    {
        pending_ep8_in = true;
        mask |= _IBNI_EP8;
    }

    IBNIRQ = mask;
    NAKIRQ = _IBN;

    IBNIE = ibnie;
}

static uint32_t uart_delay_counter = 0;
extern volatile uint8_t uart_buffer_offset;

int main()
{
    // Run core at 48 MHz fCLK and enable clkout.
    CPUCS = _CLKSPD1 | _CLKOE;

    // Use newest chip features.
    REVCTL = _ENH_PKT | _DYN_OUT;
    SYNCDELAY;

    // Disable FPGA for now
    FPGA_RESET_PORT &= ~(1 << FPGA_RESET_PIN);
    OEE |= (1 << FPGA_RESET_PIN);

#if USB_ACM_MODE
    usb_set_descriptors(/*sampling =*/false);
    target_serial_init(/*slow_baudrate=*/false);
    usb_configure_cdc_acm();
#else
    usb_set_descriptors(/*sampling =*/true);
    usb_configure_sampling();
#endif

    start_blinky();

    debug_serial_init();

    // Enable interrupts
    EA |= 1;

    // Re-enumerate, to make sure our descriptors are picked up correctly.
    usb_init(true);

    printf("Started\n");

    if (gain_control_init() < 0)
    {
        printf("gain ctrl err\n");
        for (;;)
            ;
    }

    uint16_t length = 0;
    while (1)
    {
        // Process incoming commands
        if (!(EP1OUTCS & _BUSY))
        {
            process_cmd_buffer(EP1OUTBUF, EP1OUTBC);
            EP1OUTBC = 0;
        }

        // Forward data to target serial
        if (!(EP6CS & _EMPTY))
        {
            length = (EP6BCH << 8) | EP6BCL;
            for (int i = 0; i < length; i++)
            {
                target_serial_write(EP6FIFOBUF[i]);
            }
            EP6BCL = 0;
        }

        // Forward data received from target serial
        if (pending_ep8_in)
        {
            if ((uart_buffer_offset > 200) || (uart_delay_counter > 1000))
            {
                IE &= ~_ES0;
                EP8BCH = 0;
                SYNCDELAY;
                EP8BCL = uart_buffer_offset;
                uart_buffer_offset = 0;
                IE |= _ES0;

                uart_delay_counter = 0;
                pending_ep8_in = false;
            }
            else
            {
                if (uart_buffer_offset)
                {
                    uart_delay_counter++;
                }
            }
        }

        if (cmd_reply_available() && pending_ep1_in)
        {
            uint16_t reply = cmd_reply_get();
            EP1INBUF[0] = reply & 0xff;
            EP1INBUF[1] = (reply >> 8) & 0xff;
            EP1INBC = 2;
            pending_ep1_in = false;
        }
    }
}
