#include "gpif.h"

#include <stdio.h>

#include <fx2regs.h>
#include <fx2delay.h>

/**
 * @brief Configure the GPIF state machine
 *
 */
static void build_gpif_states()
{
    uint8_t s = 0;

    // S0 - Wait for RDY0 = 1
    WAVEDATA[s] = (1 << 3) | (0 << 0);                               // Branch to S1 if condition is true, stays to S0 otherwise
    WAVEDATA[s + 8] = (1 << 0);                                      // opcode, do nothing, DP = 1
    WAVEDATA[s + 16] = 0;                                            // Output, unused
    WAVEDATA[s + 24] = (0b00u << 6) | (0b000u << 3) | (0b000u << 0); // Logic function, check if RDY0 is set
    s++;

    // S1 - Sample data
    WAVEDATA[s] = (7 << 3) | (2 << 0);                             // Branch to IDLE if condition is true, got to S2 otherwise
    WAVEDATA[s + 8] = (1 << 1) | (1 << 0);                         // opcode, sample the FIFO and store data
    WAVEDATA[s + 16] = 0;                                          // Output, unused
    WAVEDATA[s + 24] = (0b00u << 6) | (0b110 << 3) | (0b110 << 0); // Logic function, check if FIFO is full
    s++;

    // S2 - Wait for RDY0 = 0
    WAVEDATA[s] = (0 << 3) | (2 << 0);                               // Branch to S0 if condition is true, stay to S2 otherwise
    WAVEDATA[s + 8] = (1 << 0);                                      // opcode, do nothing, DP = 1
    WAVEDATA[s + 16] = 0;                                            // Output, unused
    WAVEDATA[s + 24] = (0b11u << 6) | (0b000u << 3) | (0b111u << 0); // Logic function, check if RDY0 is unset
    s++;
}

/**
 * @brief Start the GPIF state machine
 *
 */
void gpif_start_sampling()
{
    gpif_stop_sampling();

    // Setup some GPIF registers
    GPIFREADYCFG = _INTRDY;
    GPIFCTLCFG = 0;
    GPIFIDLECS = 0,
    GPIFIDLECS = 0;
    GPIFWFSELECT = (0x3u << 6) | (0x2u << 4) | (0x1u << 2) | (0x0u << 0);
    EP2GPIFPFSTOP = 0;

    // Clear all flowstate registers, not used
    FLOWSTATE = 0;
    FLOWLOGIC = 0;
    FLOWEQ0CTL = 0;
    FLOWEQ1CTL = 0;
    FLOWHOLDOFF = 0;
    FLOWSTB = 0;
    FLOWSTBEDGE = 0;
    FLOWSTBPERIOD = 0;

    // Set GPIF flag to full
    EP2GPIFFLGSEL = (1 << 1) | (0 << 1);
    SYNCDELAY;

    // Interface is configured as:
    //  - Internally clocked
    //  - 48MHz
    //  - Async
    //  - GPIF
    IFCONFIG = _IFCLKSRC | _3048MHZ | _ASYNC | _IFCFG1;

    build_gpif_states();

    // Setup transaction count
    GPIFTCB1 = 0;
    SYNCDELAY;
    GPIFTCB0 = 1;

    // Reset EP2 FIFO
    FIFORESET = _NAKALL | 2;
    SYNCDELAY;
    FIFORESET = 0;

    // Start the GPIF system
    while (!(GPIFTRIG & _GPIFIDLE))
        ;
    GPIFTRIG = _RW | 0; // 0 = EP2
}

/**
 * @brief Stop the GPIF state machine
 *
 */
void gpif_stop_sampling()
{
    // Stop previously running GPIF
    GPIFABORT = 0xff;

    // Make sure the GPIF is idle
    while (!(GPIFTRIG & _GPIFIDLE))
        ;

    // Reset EP2 FIFO
    FIFORESET = _NAKALL | 2;
    SYNCDELAY;
    FIFORESET = 0;
}