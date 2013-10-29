#!/bin/sh
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

testfile=/tmp/testfile.$$
resultfile=/tmp/result.$$
failed=0
export FAKEGUDEV_DEVICES

echo "TEST: /dev/fake does not appear in test program output"
cat > ${testfile} <<EOF
Path '/dev/fake'

EOF
./gudev-exercise /dev/fake > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: /dev/fake does not appear in test program output \
with library preloaded"
LD_PRELOAD=./libfakegudev.so ./gudev-exercise /dev/fake > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: /dev/null does appear in test program output"
cat > ${testfile} <<EOF
Path '/dev/null'
 Name:        null
 Device file: /dev/null
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   mem
 Sysfs path:  /sys/devices/virtual/mem/null
  Property UDEV_LOG: 3
  Property DEVPATH: /devices/virtual/mem/null
  Property MAJOR: 1
  Property MINOR: 3
  Property DEVNAME: /dev/null
  Property DEVMODE: 0666
  Property SUBSYSTEM: mem
  Property DEVLINKS: /dev/char/1:3

EOF
./gudev-exercise /dev/null > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi

echo "TEST: =mem,null finds /dev/null "
cat > ${testfile} <<EOF
Subsystem 'mem', Name 'null'
 Name:        null
 Device file: /dev/null
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   mem
 Sysfs path:  /sys/devices/virtual/mem/null
  Property UDEV_LOG: 3
  Property DEVPATH: /devices/virtual/mem/null
  Property MAJOR: 1
  Property MINOR: 3
  Property DEVNAME: /dev/null
  Property DEVMODE: 0666
  Property SUBSYSTEM: mem
  Property DEVLINKS: /dev/char/1:3

EOF
./gudev-exercise =mem,null > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi

echo "TEST: /sys/devices/virtual/mem/null does appear in test program output"
cat > ${testfile} <<EOF
Sysfs path '/sys/devices/virtual/mem/null'
 Name:        null
 Device file: /dev/null
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   mem
 Sysfs path:  /sys/devices/virtual/mem/null
  Property UDEV_LOG: 3
  Property DEVPATH: /devices/virtual/mem/null
  Property MAJOR: 1
  Property MINOR: 3
  Property DEVNAME: /dev/null
  Property DEVMODE: 0666
  Property SUBSYSTEM: mem
  Property DEVLINKS: /dev/char/1:3

EOF
./gudev-exercise /sys/devices/virtual/mem/null > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: /dev/null does appear in test program output with library preloaded"
cat > ${testfile} <<EOF
Path '/dev/null'
 Name:        null
 Device file: /dev/null
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   mem
 Sysfs path:  /sys/devices/virtual/mem/null
  Property UDEV_LOG: 3
  Property DEVPATH: /devices/virtual/mem/null
  Property MAJOR: 1
  Property MINOR: 3
  Property DEVNAME: /dev/null
  Property DEVMODE: 0666
  Property SUBSYSTEM: mem
  Property DEVLINKS: /dev/char/1:3

EOF
LD_PRELOAD=./libfakegudev.so ./gudev-exercise /dev/null > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: /sys/devices/virtual/mem/null appears with library loaded"
cat > ${testfile} <<EOF
Sysfs path '/sys/devices/virtual/mem/null'
 Name:        null
 Device file: /dev/null
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   mem
 Sysfs path:  /sys/devices/virtual/mem/null
  Property UDEV_LOG: 3
  Property DEVPATH: /devices/virtual/mem/null
  Property MAJOR: 1
  Property MINOR: 3
  Property DEVNAME: /dev/null
  Property DEVMODE: 0666
  Property SUBSYSTEM: mem
  Property DEVLINKS: /dev/char/1:3

EOF
LD_PRELOAD=./libfakegudev.so \
  ./gudev-exercise /sys/devices/virtual/mem/null > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: =mem,null finds /dev/null with library preloaded"
cat > ${testfile} <<EOF
Subsystem 'mem', Name 'null'
 Name:        null
 Device file: /dev/null
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   mem
 Sysfs path:  /sys/devices/virtual/mem/null
  Property UDEV_LOG: 3
  Property DEVPATH: /devices/virtual/mem/null
  Property MAJOR: 1
  Property MINOR: 3
  Property DEVNAME: /dev/null
  Property DEVMODE: 0666
  Property SUBSYSTEM: mem
  Property DEVLINKS: /dev/char/1:3

EOF
LD_PRELOAD=./libfakegudev.so ./gudev-exercise =mem,null > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: /dev/fake does appear when specified in FAKEGUDEV_DEVICES"
FAKEGUDEV_DEVICES=device_file=/dev/fake
cat > ${testfile} <<EOF
Path '/dev/fake'
 Name:        (null)
 Device file: /dev/fake
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   (null)
 Sysfs path:  (null)

EOF
LD_PRELOAD=./libfakegudev.so ./gudev-exercise /dev/fake > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: /dev/null appears when /dev/fake is specified in FAKEGUDEV_DEVICES"
FAKEGUDEV_DEVICES=device_file=/dev/fake
cat > ${testfile} <<EOF
Path '/dev/null'
 Name:        null
 Device file: /dev/null
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   mem
 Sysfs path:  /sys/devices/virtual/mem/null
  Property UDEV_LOG: 3
  Property DEVPATH: /devices/virtual/mem/null
  Property MAJOR: 1
  Property MINOR: 3
  Property DEVNAME: /dev/null
  Property DEVMODE: 0666
  Property SUBSYSTEM: mem
  Property DEVLINKS: /dev/char/1:3

EOF
LD_PRELOAD=./libfakegudev.so ./gudev-exercise /dev/null > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: Device name appears"
FAKEGUDEV_DEVICES=device_file=/dev/fake:name=fakedevice
cat > ${testfile} <<EOF
Path '/dev/fake'
 Name:        fakedevice
 Device file: /dev/fake
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   (null)
 Sysfs path:  (null)

EOF
LD_PRELOAD=./libfakegudev.so ./gudev-exercise /dev/fake > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: Devtype appears"
FAKEGUDEV_DEVICES=device_file=/dev/fake:devtype=faketype
cat > ${testfile} <<EOF
Path '/dev/fake'
 Name:        (null)
 Device file: /dev/fake
 Devtype:     faketype
 Driver:      (null)
 Subsystem:   (null)
 Sysfs path:  (null)

EOF
LD_PRELOAD=./libfakegudev.so ./gudev-exercise /dev/fake > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: Driver appears"
FAKEGUDEV_DEVICES=device_file=/dev/fake:driver=fakedriver
cat > ${testfile} <<EOF
Path '/dev/fake'
 Name:        (null)
 Device file: /dev/fake
 Devtype:     (null)
 Driver:      fakedriver
 Subsystem:   (null)
 Sysfs path:  (null)

EOF
LD_PRELOAD=./libfakegudev.so ./gudev-exercise /dev/fake > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: Subsystem appears"
FAKEGUDEV_DEVICES=device_file=/dev/fake:subsystem=fakesub
cat > ${testfile} <<EOF
Path '/dev/fake'
 Name:        (null)
 Device file: /dev/fake
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   fakesub
 Sysfs path:  (null)

EOF
LD_PRELOAD=./libfakegudev.so ./gudev-exercise /dev/fake > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: Search for fake device by subsystem and name works"
FAKEGUDEV_DEVICES=device_file=/dev/fake:subsystem=fakesub:name=fakedevice
cat > ${testfile} <<EOF
Subsystem 'fakesub', Name 'fakedevice'
 Name:        fakedevice
 Device file: /dev/fake
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   fakesub
 Sysfs path:  (null)

EOF
LD_PRELOAD=./libfakegudev.so \
  ./gudev-exercise =fakesub,fakedevice > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: Sysfs path appears"
FAKEGUDEV_DEVICES=device_file=/dev/fake:sysfs_path=/sys/devices/virtual/fake
cat > ${testfile} <<EOF
Path '/dev/fake'
 Name:        (null)
 Device file: /dev/fake
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   (null)
 Sysfs path:  /sys/devices/virtual/fake

EOF
LD_PRELOAD=./libfakegudev.so ./gudev-exercise /dev/fake > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: Property appears"
FAKEGUDEV_DEVICES=device_file=/dev/fake:property_FOO=BAR
cat > ${testfile} <<EOF
Path '/dev/fake'
 Name:        (null)
 Device file: /dev/fake
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   (null)
 Sysfs path:  (null)
  Property FOO: BAR

EOF
LD_PRELOAD=./libfakegudev.so ./gudev-exercise /dev/fake > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi

# Warning: This test depends on property order, which isn't guaranteed
# either by gudev or by the override library
echo "TEST: Several properties appear"
FAKEGUDEV_DEVICES=device_file=/dev/fake:\
property_FOO=BAR:property_BAR=BAZ:property_BAZ=QUUX
cat > ${testfile} <<EOF
Path '/dev/fake'
 Name:        (null)
 Device file: /dev/fake
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   (null)
 Sysfs path:  (null)
  Property BAZ: QUUX
  Property BAR: BAZ
  Property FOO: BAR

EOF
LD_PRELOAD=./libfakegudev.so ./gudev-exercise /dev/fake > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: Property appears when queried repeatedly (test caching)"
FAKEGUDEV_DEVICES=device_file=/dev/fake:property_FOO=BAR
cat > ${testfile} <<EOF
Path '/dev/fake'
 Name:        (null)
 Device file: /dev/fake
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   (null)
 Sysfs path:  (null)
  Property FOO: BAR

Path '/dev/fake'
 Name:        (null)
 Device file: /dev/fake
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   (null)
 Sysfs path:  (null)
  Property FOO: BAR

Path '/dev/fake'
 Name:        (null)
 Device file: /dev/fake
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   (null)
 Sysfs path:  (null)
  Property FOO: BAR

EOF
LD_PRELOAD=./libfakegudev.so \
./gudev-exercise /dev/fake /dev/fake /dev/fake > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: /dev/fake2 does not appear when only /dev/fake is specified"
FAKEGUDEV_DEVICES=device_file=/dev/fake
cat > ${testfile} <<EOF
Path '/dev/fake'
 Name:        (null)
 Device file: /dev/fake
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   (null)
 Sysfs path:  (null)

Path '/dev/fake2'

EOF
LD_PRELOAD=./libfakegudev.so \
./gudev-exercise /dev/fake /dev/fake2 > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: /dev/fake2 and /dev/fake both appear when specified"
FAKEGUDEV_DEVICES=device_file=/dev/fake:device_file=/dev/fake2
cat > ${testfile} <<EOF
Path '/dev/fake'
 Name:        (null)
 Device file: /dev/fake
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   (null)
 Sysfs path:  (null)

Path '/dev/fake2'
 Name:        (null)
 Device file: /dev/fake2
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   (null)
 Sysfs path:  (null)

EOF
LD_PRELOAD=./libfakegudev.so \
./gudev-exercise /dev/fake /dev/fake2 > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi

echo "TEST: /dev/fake appears as parent of /dev/fake2"
FAKEGUDEV_DEVICES=device_file=/dev/fake:device_file=/dev/fake2:parent=/dev/fake
cat > ${testfile} <<EOF
Path '/dev/fake2'
 Name:        (null)
 Device file: /dev/fake2
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   (null)
 Sysfs path:  (null)
Parent device:
 Name:        (null)
 Device file: /dev/fake
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   (null)
 Sysfs path:  (null)

EOF
LD_PRELOAD=./libfakegudev.so ./gudev-exercise /dev/fake2 > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: Real device /dev/null appears as parent of /dev/fake"
FAKEGUDEV_DEVICES=device_file=/dev/fake:parent=/dev/null
cat > ${testfile} <<EOF
Path '/dev/fake'
 Name:        (null)
 Device file: /dev/fake
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   (null)
 Sysfs path:  (null)
Parent device:
 Name:        null
 Device file: /dev/null
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   mem
 Sysfs path:  /sys/devices/virtual/mem/null
  Property UDEV_LOG: 3
  Property DEVPATH: /devices/virtual/mem/null
  Property MAJOR: 1
  Property MINOR: 3
  Property DEVNAME: /dev/null
  Property DEVMODE: 0666
  Property SUBSYSTEM: mem
  Property DEVLINKS: /dev/char/1:3

EOF
LD_PRELOAD=./libfakegudev.so ./gudev-exercise /dev/fake > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: /sys/devices/fake does not appear when not specified"
cat > ${testfile} <<EOF
Sysfs path '/sys/devices/fake'

EOF
LD_PRELOAD=./libfakegudev.so ./gudev-exercise /sys/devices/fake > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: /sys/devices/fake does appear when specified"
FAKEGUDEV_DEVICES=device_file=/dev/fake:sysfs_path=/sys/devices/fake
cat > ${testfile} <<EOF
Sysfs path '/sys/devices/fake'
 Name:        (null)
 Device file: /dev/fake
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   (null)
 Sysfs path:  /sys/devices/fake

EOF
LD_PRELOAD=./libfakegudev.so ./gudev-exercise /sys/devices/fake > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


# Test sysfs attributes
echo "TEST: /sys/devices/fake fully fledged"
FAKEGUDEV_DEVICES=device_file=/dev/fake:name=fakedevice:devtype=faketype:\
driver=fakedriver:subsystem=fakesub:sysfs_path=/sys/devices/virtual/fake:\
property_FOO=BAR:property_BAR=BAZ:property_BAZ=QUUX:parent=/dev/null:
cat > ${testfile} <<EOF
Path '/dev/fake'
 Name:        fakedevice
 Device file: /dev/fake
 Devtype:     faketype
 Driver:      fakedriver
 Subsystem:   fakesub
 Sysfs path:  /sys/devices/virtual/fake
  Property BAZ: QUUX
  Property BAR: BAZ
  Property FOO: BAR
Parent device:
 Name:        null
 Device file: /dev/null
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   mem
 Sysfs path:  /sys/devices/virtual/mem/null
  Property UDEV_LOG: 3
  Property DEVPATH: /devices/virtual/mem/null
  Property MAJOR: 1
  Property MINOR: 3
  Property DEVNAME: /dev/null
  Property DEVMODE: 0666
  Property SUBSYSTEM: mem
  Property DEVLINKS: /dev/char/1:3

EOF
LD_PRELOAD=./libfakegudev.so ./gudev-exercise /dev/fake > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: Test sysfs attributes with : in properties in different positions"
FAKEGUDEV_DEVICES=device_file=/dev/fake:name=fakedevice:devtype=faketype:\
driver=fakedriver:subsystem=\\:fakesub\\::\
sysfs_path=/sys/devices/virtual/4\\:0.0/fake:property_FOO=BAR:property_BAR=BAZ:\
property_BAZ=QUUX:parent=/dev/null:
cat > ${testfile} <<EOF
Path '/dev/fake'
 Name:        fakedevice
 Device file: /dev/fake
 Devtype:     faketype
 Driver:      fakedriver
 Subsystem:   :fakesub:
 Sysfs path:  /sys/devices/virtual/4:0.0/fake
  Property BAZ: QUUX
  Property BAR: BAZ
  Property FOO: BAR
Parent device:
 Name:        null
 Device file: /dev/null
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   mem
 Sysfs path:  /sys/devices/virtual/mem/null
  Property UDEV_LOG: 3
  Property DEVPATH: /devices/virtual/mem/null
  Property MAJOR: 1
  Property MINOR: 3
  Property DEVNAME: /dev/null
  Property DEVMODE: 0666
  Property SUBSYSTEM: mem
  Property DEVLINKS: /dev/char/1:3

EOF
LD_PRELOAD=./libfakegudev.so ./gudev-exercise /dev/fake > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


echo "TEST: /sys/devices/fake /sys/devices/fake2"
FAKEGUDEV_DEVICES=device_file=/dev/fake:sysfs_path=/sys/devices/fake::\
device_file=/dev/fake2:sysfs_path=/sys/devices/fake2::
cat > ${testfile} <<EOF
Sysfs path '/sys/devices/fake'
 Name:        (null)
 Device file: /dev/fake
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   (null)
 Sysfs path:  /sys/devices/fake

EOF
LD_PRELOAD=./libfakegudev.so ./gudev-exercise /sys/devices/fake > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi

cat > ${testfile} <<EOF
Sysfs path '/sys/devices/fake2'
 Name:        (null)
 Device file: /dev/fake2
 Devtype:     (null)
 Driver:      (null)
 Subsystem:   (null)
 Sysfs path:  /sys/devices/fake2

EOF
LD_PRELOAD=./libfakegudev.so ./gudev-exercise /sys/devices/fake2 > ${resultfile}
diff -u ${testfile} ${resultfile}
if [ $? -ne 0 ]; then echo "FAILED"; failed=1; fi


exit ${failed}
