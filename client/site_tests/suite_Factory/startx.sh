#!/bin/sh

# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

XAUTH=/usr/bin/xauth
XAUTH_FILE=/home/chronos/.Xauthority
SERVER_READY=
DISPLAY=":0"

user1_handler () {
  echo "X server ready..." 1>&2
  SERVER_READY=y
}

trap user1_handler USR1
MCOOKIE=$(head -c 8 /dev/urandom | openssl md5)
${XAUTH} -q -f ${XAUTH_FILE} add ${DISPLAY} . ${MCOOKIE}

/bin/sh -c "\
trap '' USR1 TTOU TTIN
exec /usr/bin/X -nolisten tcp vt01 -auth ${XAUTH_FILE} \
-r -s 0 -p 0 -dpms 2> /var/log/factory.X.log" &

while [ -z ${SERVER_READY} ]; do
  sleep .1
done

export DISPLAY=${DISPLAY}
export XAUTHORITY=${XAUTH_FILE}

/sbin/initctl emit factory-ui-started
cat /proc/uptime > /tmp/uptime-x-started

echo "export DISPLAY=${DISPLAY}"
echo "export XAUTHORITY=${XAUTH_FILE}"
