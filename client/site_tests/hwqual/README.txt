Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.


This document describes the steps to go through in order to run hardware
qualification on a Chrome OS device under test (DUT).


================================================================================
Test Setup
================================================================================


* Setup a Linux machine to serve as the Autotest server. The Autotest
  server requires Python, Ethernet access to the DUT and basic Linux
  shell utilities. The setup has been tested on Ubuntu 9.10 available
  for download at http://www.ubuntu.com/getubuntu/download/.


* Create an installation directory on the Autotest server for the
  Chrome OS hardware qualification package. The rest of the
  instructions assume that you're installing the package in the
  current user home directory ($HOME/).


* Contact your Google technical support person and download the Chrome
  OS hardware qualification package chromeos-hwqual-TAG.tar.bz2 for
  your device in $HOME/.


* Install the package on the server:

  $ cd $HOME/ && tar xjf chromeos-hwqual-TAG.tar.bz2


* Install the Chrome OS test image on the DUT. The USB test image is
  available in:

  $HOME/chromeos-hwqual-TAG/chromeos-hwqual-usb.img

  Here are sample steps to install the test image.

  - Plug a USB storage device into the Autotest server. Note that all
    data on your USB stick will be destroyed.

  - Unmount any mounts on the USB device:

    $ sudo umount /dev/sdx

    where /dev/sdx is your USB device.

  - Copy the USB image to a USB storage device by executing:

    $ sudo dd if=$HOME/chromeos-hwqual-TAG/chromeos-hwqual-usb.img \
              of=/dev/sdx

  - Plug the USB device into the DUT and boot from it.

  - Install Chrome OS on the DUT: switch to VT2 by pressing
    Ctrl-Alt-F2, login as "chronos", password "test0000", and run

    $ /usr/sbin/chromeos-install


* Cold boot the DUT -- turn the DUT off and then back on. This ensures
  a consistent starting point for the qualification tests and allows
  the system to collect cold boot performance metrics. Make sure you
  don't boot from USB.


* Connect the DUT to the network and note its IP address <DUT_IP>. One
  way to find the IP is to switch to VT2 by pressing Ctrl-Alt-F2,
  login as "root", password "test0000". Run:

  $ ip -f inet addr

  Switch back to VT1 by pressing Ctrl-Alt-F1.


* Add the DUT root private key to ssh-agent on the Autotest server:

  $ ssh-add $HOME/chromeos-hwqual-TAG/testing_rsa

  If ssh-agent is not running already, start it and then add the key:

  $ eval `ssh-agent -s`

  This allows the Autotest server to connect and login as root on the
  DUT.


* Make sure you can ssh as root to the DUT from the Autotest
  server. The command below should print 0.

  $ ssh root@<DUT_IP> true; echo $?


================================================================================
Automated and Semi-Automated Test Runs
================================================================================


* Unless otherwise noted, all tests can be performed on an AC-powered DUT.


* The autotest tests generate progress and performance data in a
  <results> folder specified through the '-r' autoserv option. After a
  test run is complete, look for failures:

  $ egrep '(FAIL|BAD|ERROR)' <results>/*/status

  Full performance data is stored in keyval files:

  $ cat <results>/*/results/keyval

  Debug information is stored in <results>/*/debug/.


* Go to the Autotest server folder:

  $ cd $HOME/chromeos-hwqual-TAG/autotest/


* Before running the tests, cleanup previous test results:

  $ rm -rf results.*


* Run the fully automated client-side tests:

  $ ./server/autoserv -r results.auto -m <DUT_IP> \
                      -c client/site_tests/hwqual/control.auto


* (TODO: Spec the USB/SD cards.) Plug storage devices in all USB and
  SD Card slots and run the external storage test:

  $ ./server/autoserv -r results.external_devices -m <DUT_IP> \
                      -c client/site_tests/hwqual/control.external_devices


* Run the system suspend/resume stability test:

  $ ./server/autoserv -r results.suspend_resume -m <DUT_IP> \
                      -c client/site_tests/hwqual/control.suspend_resume


* Run the device on AC. Plug a power draw USB dongle in each USB port.
  Run the max power draw test:

  $ ./server/autoserv -r results.max_power_draw.ac -m <DUT_IP> \
                      -c client/site_tests/hwqual/control.max_power_draw


* Run the device on battery. Plug a power draw USB dongle in each USB
  port. Run the max power draw test:

  $ ./server/autoserv -r results.max_power_draw.batt -m <DUT_IP> \
                      -c client/site_tests/hwqual/control.max_power_draw


* Make sure the remaining battery charge is less than 5%. Run the DUT
  on AC. Run the battery charge test:

  $ ./server/autoserv -r results.battery_charge_time -m <DUT_IP> \
                      -c client/site_tests/hwqual/control.battery_charge_time

  Note that the test will check and fail quickly if the initial
  battery charge is more than 5%.

                      
* Make sure that there are no test failures. Once all tests pass,
  package the result folders:

  $ tar cjf chromeos-hwqual-TAG-DATE.tar.bz2 results.*

  Send the tarball to your Google technical support contact for
  review.


================================================================================
Manual and Semi-Automated Test Runs
================================================================================


* (TODO: Refer to the manual testing document.) Perform the manual
  tests specified in...
