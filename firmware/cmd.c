#include "cmd.h"

#include <stdio.h>

#include <fx2usb.h>

#include "usb.h"
#include "gpif.h"
#include "gain_control.h"
#include "fpga_config.h"
#include "fpga_control.h"
#include "temperature_sensor.h"

enum cmd_opcode
{
    OPCODE_FPGA_CONFIG = 0,
    OPCODE_START_MEASUREMENT,
    OPCODE_STOP_MEASUREMENT,
    OPCODE_SET_DAC,
    OPCODE_SET_DUT_POWER,
    OPCODE_SET_DUT_CLK_EN,
    OPCODE_SET_FLASH_PAYLOAD,
    OPCODE_GET_TEMPERATURE,
    OPCODE_SET_HEATER_PWM
};

enum fsm_state
{
    READ_CMD_OPCODE = 0,
    READ_CMD_ARG,
    READ_FPGA_BITSTREAM,
    READ_FLASH_PAYLOAD,
};

struct cmd_header
{
    uint8_t opcode;
    uint32_t arg;
};

static enum fsm_state fsm_state = READ_CMD_OPCODE;

static struct cmd_header cmd_header;
static uint8_t cmd_header_arg_offset = 0;

static uint32_t fpga_configured_length = 0;
static uint8_t flash_payload[16];
static uint8_t payload_read_length = 0;

static bool reply_available = false;
static uint16_t reply_code = 0;

/**
 * @brief Set the 16-bit response code to send back to the host
 *
 * @param c The 16-bit response code
 */
static void send_cmd_reply(uint16_t c)
{
    reply_code = c;
    reply_available = true;
}

/**
 * @brief Check if a reply to send back to the host is available
 *
 * @return true A reply is available
 * @return false Not reply is available
 */
bool cmd_reply_available()
{
    return reply_available;
}

/**
 * @brief Read the 16-bit reply code to send back to the host
 *
 * @return uint16_t The reply code
 */
uint16_t cmd_reply_get()
{
    reply_available = false;
    return reply_code;
}

/**
 * @brief Process an incoming command buffer
 *
 * @param buffer The buffer to process
 * @param buffer_size The sizez of the buffer
 */
void process_cmd_buffer(const __xdata uint8_t *buffer, uint16_t buffer_size)
{
    uint16_t buffer_offset = 0;

    while (buffer_offset < buffer_size)
    {
        switch (fsm_state)
        {
        case READ_CMD_OPCODE:
        {
            cmd_header.opcode = buffer[buffer_offset++];
            cmd_header.arg = 0;
            cmd_header_arg_offset = 0;
            fsm_state = READ_CMD_ARG;
            break;
        }
        case READ_CMD_ARG:
        {
            if (cmd_header_arg_offset != 4)
            {
                cmd_header.arg |= (uint32_t)(buffer[buffer_offset]) << (8 * cmd_header_arg_offset);
                buffer_offset++;
                cmd_header_arg_offset++;
            }

            if (cmd_header_arg_offset == 4)
            {
                switch (cmd_header.opcode)
                {
                case OPCODE_FPGA_CONFIG:
                {
                    fpga_configured_length = 0;
                    fpga_config_start();
                    fsm_state = READ_FPGA_BITSTREAM;
                    break;
                }
                case OPCODE_START_MEASUREMENT:
                {
                    printf("MEAS start\n");
                    gpif_start_sampling();
                    fpga_control_start_measurement();
                    fsm_state = READ_CMD_OPCODE;
                    break;
                }
                case OPCODE_STOP_MEASUREMENT:
                {
                    printf("MEAS stop\n");
                    gpif_stop_sampling();
                    fsm_state = READ_CMD_OPCODE;
                    break;
                }
                case OPCODE_SET_DAC:
                {
                    if (set_gain(cmd_header.arg) < 0)
                    {
                        send_cmd_reply('F');
                    }
                    else
                    {
                        send_cmd_reply('O');
                    }
                    fsm_state = READ_CMD_OPCODE;
                    break;
                }
                case OPCODE_SET_DUT_POWER:
                {
                    if (fpga_control_set_dut_power(cmd_header.arg) < 0)
                    {
                        send_cmd_reply('F');
                    }
                    else
                    {
                        send_cmd_reply('O');
                    }
                    fsm_state = READ_CMD_OPCODE;
                    break;
                }
                case OPCODE_SET_DUT_CLK_EN:
                {
                    if (fpga_control_set_dut_clk_en(cmd_header.arg) < 0)
                    {
                        send_cmd_reply('F');
                    }
                    else
                    {
                        send_cmd_reply('O');
                    }
                    fsm_state = READ_CMD_OPCODE;
                    break;
                }
                case OPCODE_SET_FLASH_PAYLOAD:
                {
                    payload_read_length = 0;
                    fsm_state = READ_FLASH_PAYLOAD;
                    break;
                }
                case OPCODE_GET_TEMPERATURE:
                {
                    uint16_t temp_code;
                    if (get_temperature(&temp_code) < 0)
                    {
                        send_cmd_reply('F');
                    }
                    else
                    {
                        send_cmd_reply(temp_code);
                    }
                    fsm_state = READ_CMD_OPCODE;
                    break;
                }
                case OPCODE_SET_HEATER_PWM:
                {
                    if (fpga_set_heater_pwm(cmd_header.arg) < 0)
                    {
                        send_cmd_reply('F');
                    }
                    else
                    {
                        send_cmd_reply('O');
                    }
                    fsm_state = READ_CMD_OPCODE;
                    break;
                }
                default:
                    printf("Unknown CMD: 0x%02x\n",
                           cmd_header.opcode);
                    fsm_state = READ_CMD_OPCODE;
                    break;
                }
            }
            break;
        }
        case READ_FPGA_BITSTREAM:
        {
            uint16_t chunk_size = buffer_size - buffer_offset;

            if (fpga_configured_length + chunk_size > cmd_header.arg)
            {
                chunk_size = cmd_header.arg - fpga_configured_length;
            }

            fpga_config_send(buffer + buffer_offset, chunk_size);
            buffer_offset += chunk_size;
            fpga_configured_length += chunk_size;

            if (fpga_configured_length == cmd_header.arg)
            {
                if (fpga_config_terminate() < 0)
                {
                    send_cmd_reply('F');
                }
                else
                {
                    int ret = fpga_control_init();
                    if (ret < 0)
                    {
                        send_cmd_reply('F');
                    }
                    else
                    {
                        send_cmd_reply('O');
                    }
                }
                fsm_state = READ_CMD_OPCODE;
            }

            break;
        }

        case READ_FLASH_PAYLOAD:
        {
            flash_payload[payload_read_length++] = buffer[buffer_offset++];
            if (payload_read_length == 16)
            {
                if (fpga_control_set_flash_payload(flash_payload) < 0)
                {
                    send_cmd_reply('F');
                }
                else
                {
                    send_cmd_reply('O');
                }
                fsm_state = READ_CMD_OPCODE;
            }
            break;
        }

        default:
            break;
        }
    }
}