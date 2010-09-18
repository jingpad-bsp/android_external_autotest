#!/bin/sh
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This script can be called to switch from kernel slot A / sda3
# to kernel slot B / sda5 and vice versa.

ROOT_DEV=$(rootdev -s)
OTHER_ROOT_DEV=$(echo $ROOT_DEV | tr '35' '53')

if [ "${ROOT_DEV}" = "${OTHER_ROOT_DEV}" ]
then
  echo "Not a normal rootfs partition (3 or 5): ${ROOT_DEV}"
  exit 1
fi

DEV=${ROOT_DEV%[0-9]}
# Note: this works only for single digit partition numbers.
ROOT_PART=$(echo "${ROOT_DEV}" | sed -e 's/^.*\([0-9]\)$/\1/')
OTHER_ROOT_PART=$(echo "${OTHER_ROOT_DEV}" | sed -e 's/^.*\([0-9]\)$/\1/')

# Successfully being able to mount the other partition
# and run postinst guarantees that there is a real partition there.
echo "Running postinst on $OTHER_ROOT_DEV"
MOUNTPOINT=$(mktemp -d)
mkdir -p "$MOUNTPOINT"
mount -o ro  "$OTHER_ROOT_DEV" "$MOUNTPOINT"
"$MOUNTPOINT"/postinst --noupdate_firmware "$OTHER_ROOT_DEV"
POSTINST_RETURN_CODE=$?
umount "$MOUNTPOINT"
rmdir "$MOUNTPOINT"

# Destroy this root partition if we've successfully switched.
if [ "${POSTINST_RETURN_CODE}" = "0" ]; then
  cgpt add -i "$((${ROOT_PART} - 1))" -P 0 -S 0 -T 0 "${DEV}"
  if [ "$?" != "0" ]; then
    echo "Failed to run cgpt"
    return 1
  fi
  cgpt add -i "$((${OTHER_ROOT_PART} - 1))" -P 3 -S 1 -T 0 "${DEV}"
  if [ "$?" != "0" ]; then
    echo "Failed to run cgpt"
    return 1
  fi
fi

exit $POSTINST_RETURN_CODE
