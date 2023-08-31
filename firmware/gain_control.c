#include "gain_control.h"

#include <fx2lib.h>
#include <fx2i2c.h>

// 7-bit address
#define DAC_ADR 0x48u

#define STATUS_REG_ADR 0xD0
#define GENERAL_CONFIG_REG_ADR 0xD1
#define CONFIG2_REG_ADR 0xD2
#define TRIGGER_REG_ADR 0xD3
#define DAC_DATA_REG_ADR 0x21
#define DAC_MARGIN_HIGH_REG_ADR 0x25
#define DAC_MARGIN_LOW_REG_ADR 0x26
#define PMBUS_OPERATION_REG_ADR 0x01
#define PMBUS_STATUS_BYTE_REG_ADR 0x78
#define PMBUS_VERSION_REG_ADR 0x98

/**
 * @brief Read a DAC register
 *
 * @param reg_adr The register address
 * @param reg_val The register value
 * @return int 0 in case of success, -1 otherwise
 */
static int read_reg(uint8_t reg_adr, uint16_t *reg_val)
{
    bool ret;

    ret = i2c_start(DAC_ADR << 1);
    if (!ret)
    {
        return -1;
    }

    ret = i2c_write(&reg_adr, 1);
    if (!ret)
    {
        return -1;
    }

    ret = i2c_start((DAC_ADR << 1) | 1);
    if (!ret)
    {
        return -1;
    }

    ret = i2c_read(reg_val, 2);
    if (!ret)
    {
        return -1;
    }

    *reg_val = bswap16(*reg_val);

    return 0;
}

/**
 * @brief Write a DAC register
 *
 * @param reg_adr The register address
 * @param reg_val The register value
 * @return int 0 in case of success, -1 otherwise
 */
static int write_reg(uint8_t reg_adr, uint16_t reg_val)
{
    bool ret;
    uint16_t val = bswap16(reg_val);

    ret = i2c_start(DAC_ADR << 1);
    if (!ret)
    {
        return -1;
    }

    ret = i2c_write(&reg_adr, 1);
    if (!ret)
    {
        return -1;
    }

    ret = i2c_write(&val, 2);
    if (!ret)
    {
        return -1;
    }

    return 0;
}

/**
 * @brief Init the gain control DAC
 *
 * @return int 0 in case of success, -1 oterhwise
 */
int gain_control_init()
{
    uint16_t val;
    int ret = read_reg(STATUS_REG_ADR, &val);
    if (ret < 0)
    {
        return -1;
    }

    if (val & 0b111111 != 0xC)
    {
        return -1;
    }

    val = (1 << 2) | 0b00;
    if (write_reg(GENERAL_CONFIG_REG_ADR, val) < 0)
    {
        return -1;
    }

    return 0;
}

/**
 * @brief Set the gain value
 *
 * @param gain gain, expressedd in LSB
 * @return int 0 in case of success, -1 otherwise
 */
int set_gain(uint16_t gain)
{
    uint16_t val = gain << 2;

    if (write_reg(DAC_DATA_REG_ADR, val) < 0)
    {
        return -1;
    }

    return 0;
}