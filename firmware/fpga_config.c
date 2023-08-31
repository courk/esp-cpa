#include "fpga_config.h"

#include <stdint.h>

#include <fx2lib.h>
#include <fx2regs.h>
#include <fx2delay.h>

#include "board.h"

/**
 * @brief Write a single SPI byte (mode 3)
 *
 * @param byte The byte to write
 */
static void spi_write_byte(uint8_t byte)
{
    for (int i = 7; i >= 0; i--)
    {
        SPI_CK = 0;
        SPI_DO = byte & (1 << i) ? 1 : 0;
        SPI_CK = 1;
    }
}

/**
 * @brief Write SPI data (mode 3)
 *
 * @param data The data to wrute
 * @param len The size of the data
 */
static void spi_write(const __xdata uint8_t *data, uint16_t len)
{
    for (uint16_t i = 0; i < len; i++)
    {
        spi_write_byte(data[i]);
    }
}

/**
 * @brief Begin the FPGA configuration
 *
 */
void fpga_config_start()
{
    // Configure input pins
    OEA &= ~((1 << FPGA_CDONE_PIN) | (1 << SPI_DI_PIN));

    // Configure output pins
    SPI_DO = 0;
    SPI_CK = 1;
    SPI_FPGA_CS = 0;
    OEA |= (1 << SPI_DO_PIN) | (1 << SPI_CK_PIN) | (1 << SPI_FPGA_CS_PIN);

    FPGA_RESET_PORT &= ~(1 << FPGA_RESET_PIN);
    OEE |= (1 << FPGA_RESET_PIN);

    // Enter SPI slave mode
    delay_us(800);
    FPGA_RESET_PORT |= (1 << FPGA_RESET_PIN);

    // ice40 clears internal configuration memory
    delay_us(1500);
}

/**
 * @brief Send a bitstream chunk to the FPGA
 *
 * @param data The bitstream chunk
 * @param len The size of the chunk
 */
void fpga_config_send(const __xdata uint8_t *data, uint16_t len)
{
    spi_write(data, len);
}

/**
 * @brief End the FPGA configuration process
 *
 * @return int 0 in case of success, -1 otherwise
 */
int fpga_config_terminate()
{
    __xdata uint8_t dummy[] = "\x00";
    for (int i = 0; i < 14; i++)
    {
        spi_write(dummy, 1);
    }

    return FPGA_CDONE ? 0 : -1;
}