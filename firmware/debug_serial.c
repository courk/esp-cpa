#include "debug_serial.h"

#include <fx2regs.h>

/**
 * @brief Init the debug serial (S1) in 8N1 mode at 115200 bauds
 *
 */
void debug_serial_init()
{
    // RX disabled, Mode 8N1
    SCON1 = _SM1_1;

    // Set baudrate, with high speed baud rate generator
    UART230 |= _230UART1;
}

int putchar(int c)
{
    SBUF1 = c;
    while (!(SCON1 & _TI_1))
        ;
    SCON1 &= ~_TI_1;

    return c;
}
