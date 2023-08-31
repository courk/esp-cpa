# ESP CPA

This repository contains the firmware, gateware, and host software of the _ESP CPA Board_.

![The ESP CPA Board](img/esp_cpa_board.png)

This board aimed at exploring side-channels attacks on _Espressif_'s chips. More details are available from [here](https://courk.cc/breaking-flash-encyption-of-espressif-parts).

# Installation

The [sdcc](https://sdcc.sourceforge.net/) compiler is required to compile the firmware of the [FX2LP](https://www.infineon.com/cms/en/product/universal-serial-bus/usb-2.0-peripheral-controllers/ez-usb-fx2lp-fx2g2-usb-2.0-peripheral-controller/) microcontroller of the board.

_Python_ dependencies can be installed by running `poetry install`.

Finally, this project relies on a custom _Rust_ library for computationally intensive tasks. A valid `rustc` compiler installation is expected. The library can be compiled with:

```
RUSTFLAGS='-C target-cpu=native' poetry run maturin develop -r
```

# Host Software Overview

## Board Configuration

The _ESP CPA Board_ needs to be configured with the `poetry run ctrl configure-board` command.

This command flashes the firmware of the `FX2LP` microcontroller and configures the _FPGA_.

More options are available from the output of the `poetry run ctrl --help` command.

## Power Traces Measurement

The `poetry run measure` commands are used to capture power traces.

Example:

```
poetry run measure config/capture/esp32c3.py test.zarr
```

More options are available from the output of the `poetry run measure --help` command.

## Traces Analysis

_Correlation Power Analysis_ methods can be applied with the `poetry run analyze` tool. All subcommands are available from the `poetry run analyze --help` output.

Results can be plotted thanks to the `poetry run plot` commands.

## Miscellaneous

The `poetry run key-tools` utils is useful to compute various key-related values. This is useful when evaluating the _XTS_ mode of encryption. See [this](https://courk.cc/breaking-flash-encyption-of-espressif-parts#encryption-method-overview_1) for theoretical details.
