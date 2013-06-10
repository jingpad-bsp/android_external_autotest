# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Constants used in attenuator scripts.

These constants are specific to the following development platform:
  hardware: BeagleBone board (revision A3)
  operating system: Angstrom Linux v2011.11-core (Core edition)
  image version:
      Angstrom-Cloud9-IDE-eglibc-ipk-v2011.11-core-beaglebone-2011.11.16
"""

import collections


PINMUX_PATH = '/sys/kernel/debug/omap_mux/'
SYS_GPIO_PATH = '/sys/class/gpio/'
EXPORT_FILE = 'export'
UNEXPORT_FILE = 'unexport'
DIRECTION_FILE = 'direction'
GPIO = 'gpio'
MODE_OUT = 'out'
VALUE_FILE = 'value'

# NB: GPIO pin has pin mux mode of 'OMAP_MUX_MODE7', see docstring of
#     get_pin_muxing_modes() in attenuator_init.py
OMAP_MUX_GPIO_MODE = 'OMAP_MUX_MODE7'
CONF_GPIO_MODE   = '7'

# Index of GPIO banks. Each GPIO bank is 32-bit long.
GPIO0 = 0
GPIO1 = 1
GPIO2 = 2
GPIO_BANK_LEN = 32

# GPIO pin specification:
#     bank: an integer, GPIO bank number ([0, 3])
#     bit: an integer, bit number within the bank ([0, 7])
#     pinmux_file: a string, pin muxing file name.
#     pin_name: a string, GPIO pin name.
GpioPin = collections.namedtuple('GpioPin',
                                 ['bank', 'bit', 'pinmux_file', 'pin_name'])

# NB: we use pins across GPIOs b/c they are physically adjacent on the board

# Variable attenuator 0, bits 0 through 7 (ascending order)
VA0 = [
    GpioPin(GPIO1, 31, 'gpmc_csn2', 'GPIO1_31'),
    GpioPin(GPIO1, 30, 'gpmc_csn1', 'GPIO1_30'),
    GpioPin(GPIO1, 5,  'gpmc_ad5',  'GPIO1_5'),
    GpioPin(GPIO1, 4,  'gpmc_ad4',  'GPIO1_4'),
    GpioPin(GPIO1, 1,  'gpmc_ad1',  'GPIO1_1'),
    GpioPin(GPIO1, 0,  'gpmc_ad0',  'GPIO1_0'),
    GpioPin(GPIO1, 29, 'gpmc_csn0', 'GPIO1_29'),
    GpioPin(GPIO2, 22, 'lcd_vsync', 'GPIO2_22'),
    ]

# Variable attenuator 1, bits 0 through 7 (ascending order)
VA1 = [
    GpioPin(GPIO1, 6,  'gpmc_ad6',      'GPIO1_6'),
    GpioPin(GPIO1, 2,  'gpmc_ad2',      'GPIO1_2'),
    GpioPin(GPIO1, 3,  'gpmc_ad3',      'GPIO1_3'),
    GpioPin(GPIO2, 2,  'gpmc_advn_ale', 'TIMER4'),
    GpioPin(GPIO2, 3,  'gpmc_oen_ren',  'TIMER7'),
    GpioPin(GPIO2, 5,  'gpmc_ben0_cle', 'TIMER5'),
    GpioPin(GPIO2, 4,  'gpmc_wen',      'TIMER6'),
    GpioPin(GPIO1, 13, 'gpmc_ad13',     'GPIO1_13'),
    ]

# Variable attenuator 2, bits 0 through 7 (ascending order)
VA2 = [
    GpioPin(GPIO1, 12, 'gpmc_ad12',  'GPIO1_12'),
    GpioPin(GPIO0, 23, 'gpmc_ad9',   'EHRPWM2B'),
    GpioPin(GPIO0, 26, 'gpmc_ad10',  'GPIO0_26'),
    GpioPin(GPIO1, 15, 'gpmc_ad15',  'GPIO1_15'),
    GpioPin(GPIO1, 14, 'gpmc_ad14',  'GPIO1_14'),
    GpioPin(GPIO0, 27, 'gpmc_ad11',  'GPIO0_27'),
    GpioPin(GPIO2, 1,  'mcasp0_fsr', 'GPIO2_1'),
    GpioPin(GPIO0, 22, 'gpmc_ad11',  'EHRPWM2A'),
    ]

# Variable attenuator 3, bits 0 through 7 (ascending order)
VA3 = [
    GpioPin(GPIO2, 24, 'lcd_pclk',       'GPIO2_24'),
    GpioPin(GPIO2, 23, 'lcd_hsync',      'GPIO2_23'),
    GpioPin(GPIO2, 25, 'lcd_ac_bias_en', 'GPIO2_25'),
    GpioPin(GPIO0, 10, 'lcd_data14',     'UART5_CTSN'),
    GpioPin(GPIO0, 11, 'lcd_data15',     'UART5_RTSN'),
    GpioPin(GPIO0, 9,  'lcd_data13',     'UART4_RTSN'),
    GpioPin(GPIO2, 17, 'lcd_data11',     'UART3_RTSN'),
    GpioPin(GPIO0, 8,  'lcd_data12',     'UART4_CTSN'),
    ]

# pin muxing map
PINS_FOR_PORT = [VA0, VA1, VA2, VA3]

VALID_PORTS = range(0, 4)

# By design attenuator supports variable attenuation from 0dB to roughly 95dB
# on each variable attenuator (stored as a 7-bit integer, MSB is always 0).
MAX_VARIABLE_ATTENUATION = 95

VALID_BIT_VALUE = ['0', '1']


class AttenuatorError(Exception):
  """Base exception for this module."""
  pass
