#include "fpga_control.h"

#include <string.h>

#include <fx2lib.h>
#include <fx2i2c.h>

// 7-bit address
#define FPGA_ADR 0x42u

struct io_levels
{
    bool dut_boot;
    bool dut_en;
    bool dut_pwr;
    bool dut_clk_en;
};

enum cmd_opcode
{
    OPCODE_SET_IO_LEVELS = 0,
    OPCODE_SET_FLASH_PAYLOAD,
    OPCODE_START_MEASUREMENT,
    OPCODE_SET_HEAT_CTRL_PWM,
};

static struct io_levels io_levels;

/**
 * @brief Set the FPGA status
 *
 * @param status The status to set
 * @return int 0 in case of success, -1 otherwise
 */
static int fpga_set_status(struct io_levels *status)
{
    bool ret;

    uint8_t val;

    ret = i2c_start(FPGA_ADR << 1);
    if (!ret)
    {
        return -1;
    }

    val = OPCODE_SET_IO_LEVELS;
    ret = i2c_write(&val, 1);
    if (!ret)
    {
        return -1;
    }

    val = status->dut_boot;
    val |= status->dut_en << 1;
    val |= status->dut_pwr << 2;
    val |= status->dut_clk_en << 3;
    ret = i2c_write(&val, 1);
    if (!ret)
    {
        return -1;
    }

    memcpy(&io_levels, status, sizeof(struct io_levels));

    return 0;
}

/**
 * @brief Init the FPGA control
 *
 * @return int 0 in case of success, -1 otherwise
 */
int fpga_control_init()
{
    memset(&io_levels, 0, sizeof(struct io_levels));
    return fpga_set_status(&io_levels);
}

/**
 * @brief Set the DUT_POWER level
 *
 * @param pwr The level
 * @return int 0 in case of success, -1 otherwise
 */
int fpga_control_set_dut_power(bool pwr)
{
    struct io_levels new_fpga_status;
    memcpy(&new_fpga_status, &io_levels, sizeof(struct io_levels));
    new_fpga_status.dut_pwr = pwr;
    return fpga_set_status(&new_fpga_status);
}

/**
 * @brief Set the DUT_EN level
 *
 * @param en The level
 * @return int 0 in case of success, -1 otherwise
 */
int fpga_control_set_dut_en(bool en)
{
    struct io_levels new_fpga_status;
    memcpy(&new_fpga_status, &io_levels, sizeof(struct io_levels));
    new_fpga_status.dut_en = en;
    return fpga_set_status(&new_fpga_status);
}

/**
 * @brief Set the DUT_EN and DUT_BOOT level
 *
 * @param boot The boot level
 * @param en The en level
 * @return int 0 in case of success, -1 otherwise
 */
int fpga_control_set_dut_boot_en(bool boot, bool en)
{
    struct io_levels new_fpga_status;
    memcpy(&new_fpga_status, &io_levels, sizeof(struct io_levels));
    new_fpga_status.dut_boot = boot;
    new_fpga_status.dut_en = en;
    return fpga_set_status(&new_fpga_status);
}

/**
 * @brief Set the DUT_BOOT level
 *
 * @param boot The level
 * @return int 0 in case of success, -1 otherwise
 */
int fpga_control_set_dut_boot(bool boot)
{
    struct io_levels new_fpga_status;
    memcpy(&new_fpga_status, &io_levels, sizeof(struct io_levels));
    new_fpga_status.dut_boot = boot;
    return fpga_set_status(&new_fpga_status);
}

/**
 * @brief Set the DUT clk enable signal
 *
 * @param en The clock enable signal
 * @return int 0 in case of success, -1 otherwise
 */
int fpga_control_set_dut_clk_en(bool en)
{
    struct io_levels new_fpga_status;
    memcpy(&new_fpga_status, &io_levels, sizeof(struct io_levels));
    new_fpga_status.dut_clk_en = en;
    return fpga_set_status(&new_fpga_status);
}

/**
 * @brief Set the flash payload
 *
 * @param data The data, expected to be a 16-byte array
 * @return int 0 in case of success, -1 otherwise
 */
int fpga_control_set_flash_payload(const uint8_t *data)
{
    int ret;

    ret = i2c_start(FPGA_ADR << 1);
    if (!ret)
    {
        return -1;
    }

    uint8_t val = OPCODE_SET_FLASH_PAYLOAD;
    ret = i2c_write(&val, 1);
    if (!ret)
    {
        return -1;
    }

    ret = i2c_write(data, 16);
    if (!ret)
    {
        return -1;
    }

    return 0;
}

/**
 * @brief Start the measurement process
 *
 * @return int 0 in case of success, -1 otherwise
 */
int fpga_control_start_measurement()
{
    int ret;

    ret = i2c_start(FPGA_ADR << 1);
    if (!ret)
    {
        return -1;
    }

    uint8_t val = OPCODE_START_MEASUREMENT;
    ret = i2c_write(&val, 1);
    if (!ret)
    {
        return -1;
    }

    return 0;
}

/**
 * @brief Set the cardtrige heater PWM value
 *
 * @param data The PWM value (0-255)
 * @return int 0 in case of success, -1 otherwise
 */
int fpga_set_heater_pwm(uint8_t value)
{
    int ret;

    ret = i2c_start(FPGA_ADR << 1);
    if (!ret)
    {
        return -1;
    }

    uint8_t val = OPCODE_SET_HEAT_CTRL_PWM;
    ret = i2c_write(&val, 1);
    if (!ret)
    {
        return -1;
    }

    ret = i2c_write(&value, 1);
    if (!ret)
    {
        return -1;
    }

    return 0;
}