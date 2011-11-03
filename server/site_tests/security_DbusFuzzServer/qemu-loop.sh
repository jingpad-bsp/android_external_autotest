#!/bin/bash
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Runs a chromiumos qemu vm in a loop. Every time the vm halts, snap
# back to clean and start a fresh one.

if [ $# -ne 1 ]; then
    echo "Usage: $0 qemu-image.bin"
    exit 1
fi

baseimg=$1
while sleep 2;do :
    cowimg=$(mktemp ./cow-XXXXXX)
    qemu-img create -f qcow2 -b "$baseimg" "$cowimg" && \
    kvm -m 1024 -vga std -pidfile kvm.pid -net nic,model=e1000  \
      -net user,hostfwd=tcp::9022-:22 \
      -hda "$cowimg" -serial stdio -vnc 127.0.0.1:1
    rm -f "$cowimg"
done
