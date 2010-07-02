#!/usr/bin/env bash
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

mydir="$(dirname "$0")"
custom_script="$mydir/select_bios_flashrom_custom.sh"

if [ -x "$custom_script" ]; then
  exec "$custom_script"
elif [ -r "$custom_script" ]; then
  exec /bin/sh "$custom_script"
  # never return here
fi

mmio_write32 0xfed1f410 `mmio_read32 0xfed1f410 |head -c 6`0460
mmio_read32 0xfed1f410
pci_read32 0 31 0 0xd0
