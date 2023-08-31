#include "target_serial.h"

#include <stdio.h>
#include <stdbool.h>

#include <fx2lib.h>
#include <fx2delay.h>
#include <fx2regs.h>
#include <fx2ints.h>

#define SLOW_COUNTER 0xfead // 115200/26

volatile uint8_t uart_buffer_offset = 0;
static volatile bool tx_done = false;
/**
 * @brief S0 ready IRQ handler
 *
 */
void isr_RI_TI_0() __interrupt(_INT_RI_TI_0)
{
    uint8_t flags = SCON0 & (_RI_0 | _TI_0);
    SCON0 &= ~flags;
    if (flags & _RI_0)
    {
        // Directly transfer the received data into
        // the EP8 buffer
        EP8FIFOBUF[uart_buffer_offset++] = SBUF0;
    }
    if (flags & _TI_0)
    {
        tx_done = true;
    }
}

/**
 * @brief Init the target serial (S0) in 8N1 mode
 *
 * @param slow_baudrate Use a baudrate compatible with a down-clocked DUT
 */
void target_serial_init(bool slow_baudrate)
{
    // RX enabled, Mode 8N1
    SCON0 = _REN_0 | _SM1_0 | _SM2_0;

    if (slow_baudrate)
    {
        target_serial_slow_baudrate();
    }
    else
    {
        target_serial_high_baudrate();
    }

    // Enable interrupt in high priority mode
    IE |= _ES0;
    IP |= _PS0;
}

/**
 * @brief Disable the target serial (S0)
 *
 */
void target_serial_deinit()
{
    SCON0 = 0;
    IE &= ~_ES0;
}

/**
 * @brief Write a byte of data to the target serial (S0)
 *
 * @param b The byte to write
 */
void target_serial_write(uint8_t b)
{
    tx_done = false;
    SBUF0 = b;
    while (!tx_done)
        ;
}

/**
 * @brief Configure target serial (S0) for a slow baudrate
 *        This baudrate is compatible with a downclocked DUT
 *
 */
void target_serial_slow_baudrate()
{
    // Disable high speed baud rate generator
    UART230 &= ~_230UART0;

    // Set baudrate, with timer 2
    RCAP2H |= (SLOW_COUNTER >> 8) & 0xff;
    RCAP2L |= SLOW_COUNTER & 0xff;
    T2CON |= _RCLK | _TCLK | _TR2;
}

/**
 * @brief Configure target serial (S0) for a normal baudrate
 *        This baudrate is compatible with a DUT clocked from a
 *        40MHz clock signal
 *
 */
void target_serial_high_baudrate()
{
    // Disable timer 2
    T2CON &= ~(_RCLK | _TCLK | _TR2);

    // Enable high speed baud rate generator
    UART230 |= _230UART0;
}