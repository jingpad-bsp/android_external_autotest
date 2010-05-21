#!/bin/sh
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This script can be called to switch from kernel slot A / sda3
# to kernel slot B / sda5 and vice versa.

ROOT_DEV=$(rootdev)
OTHER_ROOT_DEV=$(echo $ROOT_DEV | tr '35' '53')

if [ "${ROOT_DEV}" = "${OTHER_ROOT_DEV}" ]
then
  echo "Not a normal rootfs partition (3 or 5): ${ROOT_DEV}"
  exit 1
fi

# Successfully being able to mount the other partition
# and run postinst guarantees that there is a real partition there.
echo "Running postinst on $OTHER_ROOT_DEV"
MOUNTPOINT=/tmp/newpart
mkdir -p "$MOUNTPOINT"
mount "$OTHER_ROOT_DEV" "$MOUNTPOINT"
"$MOUNTPOINT"/postinst "$OTHER_ROOT_DEV"
POSTINST_RETURN_CODE=$?
umount "$MOUNTPOINT"
rmdir "$MOUNTPOINT"

exit $POSTINST_RETURN_CODE
