#!/bin/sh

# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

XAUTH=/usr/bin/xauth
SERVER_READY=

export XAUTH_FILE="/var/run/factory_test.auth"

user1_handler () {
  echo "X server ready..."
  SERVER_READY=y
}

trap user1_handler USR1
MCOOKIE=$(head -c 8 /dev/urandom | openssl md5)
${XAUTH} -q -f ${XAUTH_FILE} add :0 . ${MCOOKIE}

/sbin/xstart.sh ${XAUTH_FILE} &

while [ -z ${SERVER_READY} ]; do
  sleep .1
done

export SHELL=/bin/bash
export DISPLAY=:0.0
export PATH=/bin:/usr/bin:/usr/local/bin:/usr/bin/X11
export XAUTHORITY=${XAUTH_FILE}

/usr/bin/python TouchpadTest.py $*
STATUS=$?

/usr/bin/pkill X
exit $STATUS
