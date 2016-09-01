# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

import common
from autotest_lib.client.common_lib import hosts
from autotest_lib.server.hosts import repair


class _UpdateVerifier(hosts.Verifier):
    """
    Verifier to trigger a servo host update, if necessary.

    The operation doesn't wait for the update to complete and is
    considered a success whether or not the servo is currently
    up-to-date.
    """

    def verify(self, host):
        host.update_image(wait_for_update=False)

    @property
    def description(self):
        return 'servo host software is up-to-date'


class _BoardConfigVerifier(hosts.Verifier):
    """
    Verifier for the servo BOARD configuration.
    """

    CONFIG_FILE = '/var/lib/servod/config'

    @staticmethod
    def _get_board(host, config_file):
        """
        Get the board for `host` from `config_file`.

        @param host         Host to be checked for `config_file`.
        @param config_file  Path to the config file to be tested.
        @return The board name as set in the config file, or `None` if
                the file was absent.
        """
        getboard = ('CONFIG=%s ; [ -f $CONFIG ] && '
                    '. $CONFIG && echo $BOARD' % config_file)
        boardval = host.run(getboard, ignore_status=True).stdout
        return boardval.strip('\n') if boardval else None

    @staticmethod
    def _validate_board(host, boardval, config_file):
        """
        Check that the BOARD setting is valid for the host.

        This presupposes that a valid config file was found.  Raise an
        execption if:
          * There was no BOARD setting from the file (i.e. the setting
            is an empty string), or
          * The board setting is valid, the DUT's board is known,
            and the setting doesn't match the DUT.

        If there's a valid board setting, but the DUT's board is
        unknown, ignore it.

        @param host         Host to be checked for `config_file`.
        @param boardval     Board value to be tested.
        @param config_file  Path to the config file to be tested.
        """
        if not boardval:
            raise hosts.AutoservVerifyError(
                    'config file %s exists, but BOARD '
                    'is not set' % config_file)
        if (host.servo_board is not None and
                boardval != host.servo_board):
            raise hosts.AutoservVerifyError(
                    'servo board is %s; it should be %s' %
                    (boardval, host.servo_board))

    def verify(self, host):
        """
        Test whether the `host` has a `BOARD` setting configured.

        This tests the config file names used by the `servod` upstart
        job for a valid setting of the `BOARD` variable.  The following
        conditions raise errors:
          * A config file exists, but the content contains no setting
            for BOARD.
          * The BOARD setting doesn't match the DUT's entry in the AFE
            database.
          * There is no config file.
        """
        if not host.is_cros_host():
            return
        # TODO(jrbarnette):  Testing `CONFIG_FILE` without a port number
        # is a legacy.  Ideally, we would force all servos in the lab to
        # update, and then remove this case.
        config_list = ['%s_%d' % (self.CONFIG_FILE, host.servo_port)]
        if host.servo_port == host.DEFAULT_PORT:
            config_list.append(self.CONFIG_FILE)
        for config in config_list:
            boardval = self._get_board(host, config)
            if boardval is not None:
                self._validate_board(host, boardval, config)
                return
        msg = 'Servo board is unconfigured'
        if host.servo_board is not None:
            msg += '; should be %s' % host.servo_board
        raise hosts.AutoservVerifyError(msg)

    @property
    def description(self):
        return 'servo BOARD setting is correct'


class _ServodJobVerifier(hosts.Verifier):
    """
    Verifier to check that the `servod` upstart job is running.
    """

    def verify(self, host):
        if not host.is_cros_host():
            return
        status_cmd = 'status servod PORT=%d' % host.servo_port
        job_status = host.run(status_cmd, ignore_status=True).stdout
        if 'start/running' not in job_status:
            raise hosts.AutoservVerifyError(
                    'servod not running on %s port %d' %
                    (host.hostname, host.servo_port))

    @property
    def description(self):
        return 'servod upstart job is running'


class _ServodConnectionVerifier(hosts.Verifier):
    """
    Verifier to check that we can connect to `servod`.

    This tests the connection to the target servod service with a simple
    method call.  As a side-effect, all servo signals are initialized to
    default values.

    N.B. Initializing servo signals is necessary because the power
    button and lid switch verifiers both test against expected initial
    values.
    """

    def verify(self, host):
        host.connect_servo()

    @property
    def description(self):
        return 'servod service is taking calls'


class _PowerButtonVerifier(hosts.Verifier):
    """
    Verifier to check sanity of the `pwr_button` signal.

    Tests that the `pwr_button` signal shows the power button has been
    released.  When `pwr_button` is stuck at `press`, it commonly
    indicates that the ribbon cable is disconnected.
    """

    def verify(self, host):
        button = host.get_servo().get('pwr_button')
        if button != 'release':
            raise hosts.AutoservVerifyError(
                    'Check ribbon cable: \'pwr_button\' is stuck')

    @property
    def description(self):
        return 'pwr_button control is normal'


class _LidVerifier(hosts.Verifier):
    """
    Verifier to check sanity of the `lid_open` signal.
    """

    def verify(self, host):
        lid_open = host.get_servo().get('lid_open')
        if lid_open != 'yes' and lid_open != 'not_applicable':
            raise hosts.AutoservVerifyError(
                    'Check lid switch: lid_open is %s' % lid_open)

    @property
    def description(self):
        return 'lid_open control is normal'


class _RestartServod(hosts.RepairAction):
    """Restart `servod` with the proper BOARD setting."""

    def repair(self, host):
        if not host.is_cros_host():
            raise hosts.AutoservRepairError(
                    'Can\'t restart servod: not running '
                    'embedded Chrome OS.')
        host.run('stop servod || true')
        if host.servo_board:
            host.run('start servod BOARD=%s PORT=%d' %
                     (host.servo_board, host.servo_port))
        else:
            # TODO(jrbarnette):  It remains to be seen whether
            # this action is the right thing to do...
            logging.warning('Board for DUT is unknown; starting '
                            'servod assuming a pre-configured '
                            'board.')
            host.run('start servod PORT=%d' % host.servo_port)
        # There's a lag between when `start servod` completes and when
        # the _ServodConnectionVerifier trigger can actually succeed.
        # The call to time.sleep() below gives time to make sure that
        # the trigger won't fail after we return.
        #
        # The delay selection was based on empirical testing against
        # servo V3 on a desktop:
        #   + 10 seconds was usually too slow; 11 seconds was
        #     usually fast enough.
        #   + So, the 20 second delay is about double what we
        #     expect to need.
        time.sleep(20)


    @property
    def description(self):
        return 'Start servod with the proper BOARD setting.'


class _ServoRebootRepair(repair.RebootRepair):
    """
    Reboot repair action that also waits for an update.

    This is the same as the standard `RebootRepair`, but for
    a servo host, if there's a pending update, we wait for that
    to complete before rebooting.  This should ensure that the
    servo is up-to-date after reboot.
    """

    def repair(self, host):
        if host.is_localhost() or not host.is_cros_host():
            raise hosts.AutoservRepairError(
                'Target servo is not a test lab servo')
        host.update_image(wait_for_update=True)
        super(_ServoRebootRepair, self).repair(host)

    @property
    def description(self):
        return 'Wait for update, then reboot servo host.'


def create_servo_repair_strategy():
    """
    Return a `RepairStrategy` for a `ServoHost`.
    """
    verify_dag = [
        (repair.SshVerifier,         'ssh',         []),
        (_UpdateVerifier,            'update',      ['ssh']),
        (_BoardConfigVerifier,       'config',      ['ssh']),
        (_ServodJobVerifier,         'job',         ['config']),
        (_ServodConnectionVerifier,  'servod',      ['job']),
        (_PowerButtonVerifier,       'pwr_button',  ['servod']),
        (_LidVerifier,               'lid_open',    ['servod']),
        # TODO(jrbarnette):  We want a verifier for whether there's
        # a working USB stick plugged into the servo.  However,
        # although we always want to log USB stick problems, we don't
        # want to fail the servo because we don't want a missing USB
        # stick to prevent, say, power cycling the DUT.
        #
        # So, it may be that the right fix is to put diagnosis into
        # ServoInstallRepair rather than add a verifier.
    ]

    servod_deps = ['job', 'servod', 'pwr_button', 'lid_open']
    repair_actions = [
        (repair.RPMCycleRepair, 'rpm', [], ['ssh']),
        (_RestartServod, 'restart', ['ssh'], ['config'] + servod_deps),
        (_ServoRebootRepair, 'reboot', ['ssh'], servod_deps),
    ]
    return hosts.RepairStrategy(verify_dag, repair_actions)
