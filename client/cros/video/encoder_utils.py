# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import utils


def has_broken_flush():
    """ Determine whether VEA of the board has broken flush function."""
    blacklist = [
            # Exynos
            # TODO(crbug.com/829276): Fix flush implementation in s5p-mfc.
            'daisy', 'daisy_spring', 'daisy_skate', 'peach_pi', 'peach_pit',

            # MTK8173
            # TODO(crbug.com/830327): Fix flush implementation in
            # mtk-vcodec.
            'elm', 'hana',

            # Tegra K1
            # TODO(crbug.com/830329): Fix flush implementation for Tegra.
            'nyan_big', 'nyan_blaze' 'nyan_kitty',

            # RK3288
            # TODO(crbug.com/830330): Fix flush implementation in
            # rk3288-vpu.
            'veyron_fievel', 'veyron_jaq', 'veyron_jerry', 'veyron_mickey',
            'veyron_mighty', 'veyron_minnie', 'veyron_speedy',
            'veyron_tiger',

            # Kepler
            # TODO(crbug.com/830332): Fix flush implementation in go2001.
            'guado', 'rikku', 'buddy',
    ]
    return utils.get_current_board() in blacklist
