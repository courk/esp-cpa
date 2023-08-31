#include "temperature_sensor.h"

#include <fx2lib.h>
#include <fx2delay.h>
#include <fx2i2c.h>

// 7-bit address
#define SENSOR_ADR 0x4Au

// Clock stretching disabled, high repeatability
static const uint8_t get_temp_cmd[] = {0x24, 0x00};

/**
 * @brief Read the temperature from the cartridge sensor
 *
 * @param temp The temperature code
 * @return int 0 in case of success, -1 otherwise
 */
int get_temperature(uint16_t *temp)
{
    bool ret;
    uint8_t timeout = 0;

    ret = i2c_start(SENSOR_ADR << 1);
    if (!ret)
    {
        return -1;
    }

    ret = i2c_write(get_temp_cmd, sizeof(get_temp_cmd));
    if (!ret)
    {
        return -1;
    }

    // Pool the sensor until the temperature is available
    for (;;)
    {
        ret = i2c_start((SENSOR_ADR << 1) | 1);
        if (!ret)
        {
            delay_ms(1);
            timeout++;
        }
        else
        {
            break;
        }

        if (timeout > 10)
        {
            return -1;
        }
    }

    ret = i2c_read(temp, 2);
    if (!ret)
    {
        return -1;
    }

    return 0;
}