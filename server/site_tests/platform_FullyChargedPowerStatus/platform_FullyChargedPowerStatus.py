# copyright (c) 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time

from autotest_lib.server import autotest, test
from autotest_lib.client.common_lib import error

_LONG_TIMEOUT = 20
_WAIT_DELAY = 5
_CHROME_PATH = '/opt/google/chrome/chrome'

class platform_FullyChargedPowerStatus(test.test):
    version = 1

    def cleanup(self):
        """ Power on RPM and open lid on cleanup.

        """
        self.host.power_on()
        self.host.servo.lid_open()


    def get_power_supply_parameters(self):
        """ Retrieve power supply info

        @returns a list of power supply info paramenters

        """
        power_supply_info = self.host.get_power_supply_info()
        online = power_supply_info['Line Power']['online']
        state = power_supply_info['Battery']['state']
        percentage = power_supply_info['Battery']['display percentage']
        return (online, state,  int(float(percentage)))


    def check_power_charge_status(self, status):
        """ Check any power status strings are not returned as expected

        @param status: record power status set when fail

        """

        errors = list()
        online, state, percentage = self.get_power_supply_parameters()

        if state != 'Fully charged' and state != 'Charging':
            errors.append('Bad state %s at %s' % (state, status))

        if percentage < 95 :
            errors.append('Bad percentage %d at %s' % (percentage, status))

        if online != 'yes':
            errors.append('Bad online %s at %s' % (online, status))

        if errors:
            raise error.TestFail('; '.join(errors))


    def action_login(self):
        """Login i.e. runs running client test"""
        self.autotest_client.run_test('desktopui_SimpleLogin',
                                      exit_without_logout=True)


    def is_chrome_available(self):
        """check if _CHROME_PATH exists

        @return true if _CHROME_PATH no exists
        """
        return self.host.run('ls %s' % _CHROME_PATH,
                             ignore_status=True).exit_status == 0


    def wait_to_disconnect(self):
        """Wait for DUT to suspend.

        @exception TestFail  if fail to disconnect in time

        """
        if not self.host.ping_wait_down(timeout=_LONG_TIMEOUT):
            raise error.TestFail('The device did not suspend')


    def wait_to_come_up(self):
        """Wait for DUT to resume.

        @exception TestFail  if fail to come_up in time

        """
        if not self.host.wait_up(timeout=_LONG_TIMEOUT):
            raise error.TestFail('The device did not resume')


    def run_once(self, host, power_status_sets):
        self.host = host
        self.autotest_client = autotest.Autotest(self.host)

        # Check the servo object
        if self.host.servo is None:
            raise error.TestError('Invalid servo object found on the host.')

        if self.host.has_power():
            self.host.power_on()
        else:
            raise error.TestError('No RPM is setup to device')

        online, state, percentage = self.get_power_supply_parameters()
        if not ( online == 'yes' and percentage > 95 ):
            raise error.TestError('The DUT is not on AC or Battery charge is low ')

        if not self.is_chrome_available():
            raise error.TestError('Chrome does not reside on DUT')

        self.action_login()

        for power_status_set in power_status_sets:
            before_suspend, after_suspend, before_resume = power_status_set
            logging.info('Power status set: %s', str(power_status_set))

            # Set power before suspend
            if not before_suspend:
                self.host.power_off()
                time.sleep(_WAIT_DELAY)

            # Suspend DUT(closing lid)
            self.host.servo.lid_close()
            self.wait_to_disconnect()
            logging.info('DUT suspended')

            # Set power after suspend
            if after_suspend:
                self.host.power_on()
            else:
                self.host.power_off()
                time.sleep(_WAIT_DELAY)
            time.sleep(_WAIT_DELAY)

            # Set power before resume
            if before_resume:
                self.host.power_on()
            else:
                self.host.power_off()
                time.sleep(_WAIT_DELAY)
            time.sleep(_WAIT_DELAY)

            # Resume DUT(open lid)
            self.host.servo.lid_open()
            self.wait_to_come_up()
            logging.info('DUT resumed')

            # Set power to on after resume if needed
            if not before_resume:
                self.host.power_on()
                time.sleep(_WAIT_DELAY)

            self.check_power_charge_status(str(power_status_set))
