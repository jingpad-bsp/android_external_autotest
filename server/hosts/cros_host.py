# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import functools
import httplib
import logging
import os
import re
import socket
import subprocess
import time
import xmlrpclib

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.cros import autoupdater
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.client.common_lib.cros import retry
from autotest_lib.client.cros import constants
from autotest_lib.server import autoserv_parser
from autotest_lib.server import autotest
from autotest_lib.server import utils as server_utils
from autotest_lib.server.cros.dynamic_suite import constants as ds_constants
from autotest_lib.server.cros.dynamic_suite import tools, frontend_wrappers
from autotest_lib.server.hosts import abstract_ssh
from autotest_lib.server.hosts import chameleon_host
from autotest_lib.server.hosts import servo_host
from autotest_lib.site_utils.graphite import stats
from autotest_lib.site_utils.rpm_control_system import rpm_client


try:
    import jsonrpclib
except ImportError:
    jsonrpclib = None


class FactoryImageCheckerException(error.AutoservError):
    """Exception raised when an image is a factory image."""
    pass


def add_label_detector(label_function_list, label_list=None, label=None):
    """Decorator used to group functions together into the provided list.
    @param label_function_list: List of label detecting functions to add
                                decorated function to.
    @param label_list: List of detectable labels to add detectable labels to.
                       (Default: None)
    @param label: Label string that is detectable by this detection function
                  (Default: None)
    """
    def add_func(func):
        """
        @param func: The function to be added as a detector.
        """
        label_function_list.append(func)
        if label and label_list is not None:
            label_list.append(label)
        return func
    return add_func


class CrosHost(abstract_ssh.AbstractSSHHost):
    """Chromium OS specific subclass of Host."""

    _parser = autoserv_parser.autoserv_parser
    _AFE = frontend_wrappers.RetryingAFE(timeout_min=5, delay_sec=10)

    # Timeout values (in seconds) associated with various Chrome OS
    # state changes.
    #
    # In general, a good rule of thumb is that the timeout can be up
    # to twice the typical measured value on the slowest platform.
    # The times here have not necessarily been empirically tested to
    # meet this criterion.
    #
    # SLEEP_TIMEOUT:  Time to allow for suspend to memory.
    # RESUME_TIMEOUT: Time to allow for resume after suspend, plus
    #   time to restart the netwowrk.
    # BOOT_TIMEOUT: Time to allow for boot from power off.  Among
    #   other things, this must account for the 30 second dev-mode
    #   screen delay and time to start the network.
    # USB_BOOT_TIMEOUT: Time to allow for boot from a USB device,
    #   including the 30 second dev-mode delay and time to start the
    #   network.
    # SHUTDOWN_TIMEOUT: Time to allow for shut down.
    # REBOOT_TIMEOUT: How long to wait for a reboot.
    # INSTALL_TIMEOUT: Time to allow for chromeos-install.

    SLEEP_TIMEOUT = 2
    RESUME_TIMEOUT = 10
    SHUTDOWN_TIMEOUT = 5
    BOOT_TIMEOUT = 60
    USB_BOOT_TIMEOUT = 150
    POWERWASH_BOOT_TIMEOUT = 60

    # We have a long timeout to ensure we don't flakily fail due to other
    # issues. Shorter timeouts are vetted in platform_RebootAfterUpdate.
    # TODO(sbasi - crbug.com/276094) Restore to 5 mins once the 'host did not
    # return from reboot' bug is solved.
    REBOOT_TIMEOUT = 480

    INSTALL_TIMEOUT = 240

    # _USB_POWER_TIMEOUT: Time to allow for USB to power toggle ON and OFF.
    # _POWER_CYCLE_TIMEOUT: Time to allow for manual power cycle.
    _USB_POWER_TIMEOUT = 5
    _POWER_CYCLE_TIMEOUT = 10

    _RPC_PROXY_URL = 'http://localhost:%d'
    _RPC_SHUTDOWN_POLLING_PERIOD_SECONDS = 2
    _RPC_SHUTDOWN_TIMEOUT_SECONDS = 20

    _RPM_RECOVERY_BOARDS = global_config.global_config.get_config_value('CROS',
            'rpm_recovery_boards', type=str).split(',')

    _MAX_POWER_CYCLE_ATTEMPTS = 6
    _LAB_MACHINE_FILE = '/mnt/stateful_partition/.labmachine'
    _RPM_HOSTNAME_REGEX = ('chromeos[0-9]+(-row[0-9]+)?-rack[0-9]+[a-z]*-'
                           'host[0-9]+')
    _LIGHTSENSOR_FILES = ['in_illuminance0_input',
                          'in_illuminance0_raw',
                          'illuminance0_input']
    _LIGHTSENSOR_SEARCH_DIR = '/sys/bus/iio/devices'
    _LABEL_FUNCTIONS = []
    _DETECTABLE_LABELS = []
    label_decorator = functools.partial(add_label_detector, _LABEL_FUNCTIONS,
                                        _DETECTABLE_LABELS)

    # Constants used in ping_wait_up() and ping_wait_down().
    #
    # _PING_WAIT_COUNT is the approximate number of polling
    # cycles to use when waiting for a host state change.
    #
    # _PING_STATUS_DOWN and _PING_STATUS_UP are names used
    # for arguments to the internal _ping_wait_for_status()
    # method.
    _PING_WAIT_COUNT = 40
    _PING_STATUS_DOWN = False
    _PING_STATUS_UP = True

    # Allowed values for the power_method argument.

    # POWER_CONTROL_RPM: Passed as default arg for power_off/on/cycle() methods.
    # POWER_CONTROL_SERVO: Used in set_power() and power_cycle() methods.
    # POWER_CONTROL_MANUAL: Used in set_power() and power_cycle() methods.
    POWER_CONTROL_RPM = 'RPM'
    POWER_CONTROL_SERVO = 'servoj10'
    POWER_CONTROL_MANUAL = 'manual'

    POWER_CONTROL_VALID_ARGS = (POWER_CONTROL_RPM,
                                POWER_CONTROL_SERVO,
                                POWER_CONTROL_MANUAL)

    _RPM_OUTLET_CHANGED = 'outlet_changed'


    @staticmethod
    def check_host(host, timeout=10):
        """
        Check if the given host is a chrome-os host.

        @param host: An ssh host representing a device.
        @param timeout: The timeout for the run command.

        @return: True if the host device is chromeos.

        """
        try:
            result = host.run('grep -q CHROMEOS /etc/lsb-release',
                              ignore_status=True, timeout=timeout)
        except (error.AutoservRunError, error.AutoservSSHTimeout):
            return False
        return result.exit_status == 0


    @staticmethod
    def _extract_arguments(args_dict, key_subset):
        """Extract options from `args_dict` and return a subset result.

        Take the provided dictionary of argument options and return
        a subset that represent standard arguments needed to construct
        a test-assistant object (chameleon or servo) for a host. The
        intent is to provide standard argument processing from
        run_remote_tests for tests that require a test-assistant board
        to operate.

        @param args_dict Dictionary from which to extract the arguments.
        @param key_subset Tuple of keys to extract from the args_dict, e.g.
          ('servo_host', 'servo_port').
        """
        result = {}
        for arg in key_subset:
            if arg in args_dict:
                result[arg] = args_dict[arg]
        return result


    @staticmethod
    def get_chameleon_arguments(args_dict):
        """Extract chameleon options from `args_dict` and return the result.

        Recommended usage:
        ~~~~~~~~
            args_dict = utils.args_to_dict(args)
            chameleon_args = hosts.CrosHost.get_chameleon_arguments(args_dict)
            host = hosts.create_host(machine, chameleon_args=chameleon_args)
        ~~~~~~~~

        @param args_dict Dictionary from which to extract the chameleon
          arguments.
        """
        return CrosHost._extract_arguments(
                args_dict, ('chameleon_host', 'chameleon_port'))


    @staticmethod
    def get_servo_arguments(args_dict):
        """Extract servo options from `args_dict` and return the result.

        Recommended usage:
        ~~~~~~~~
            args_dict = utils.args_to_dict(args)
            servo_args = hosts.CrosHost.get_servo_arguments(args_dict)
            host = hosts.create_host(machine, servo_args=servo_args)
        ~~~~~~~~

        @param args_dict Dictionary from which to extract the servo
          arguments.
        """
        return CrosHost._extract_arguments(
                args_dict, ('servo_host', 'servo_port'))


    def _initialize(self, hostname, chameleon_args=None, servo_args=None,
                    ssh_verbosity_flag='', ssh_options='',
                    *args, **dargs):
        """Initialize superclasses, |self.chameleon|, and |self.servo|.

        This method checks whether a chameleon/servo (aka
        test-assistant objects) is required by checking whether
        chameleon_args/servo_args is None. This method will only
        attempt to create the test-assistant object when it is
        required by the test.

        For creating the test-assistant object, there are three
        possibilities: First, if the host is a lab system known to have
        a test-assistant board, we connect to that board unconditionally.
        Second, if we're called from a control file that requires
        test-assistant features for testing, it will pass settings from
        the arguments, like `servo_host`, `servo_port`. If neither of
        these cases apply, the test-assistant object will be `None`.

        """
        super(CrosHost, self)._initialize(hostname=hostname,
                                          *args, **dargs)
        # self.env is a dictionary of environment variable settings
        # to be exported for commands run on the host.
        # LIBC_FATAL_STDERR_ can be useful for diagnosing certain
        # errors that might happen.
        self.env['LIBC_FATAL_STDERR_'] = '1'
        self._rpc_proxy_map = {}
        self._ssh_verbosity_flag = ssh_verbosity_flag
        self._ssh_options = ssh_options
        self.servo = None
        # TODO(fdeng): We need to simplify the
        # process of servo and servo_host initialization.
        # crbug.com/298432
        self._servo_host = self._create_servo_host(servo_args)
        # TODO(waihong): Do the simplication on Chameleon too.
        self._chameleon_host = self._create_chameleon_host(chameleon_args)
        # TODO(fdeng): 'servo_args is not None' is used to determine whether
        # a test needs a servo. Better solution is needed.
        # There are three possible cases here:
        # 1. servo_arg is None
        # 2. servo arg is an empty dictionary
        # 3. servo_arg is a dictionary that has entries of 'servo_host',
        #    'servo_port'(optional).
        # We assume that:
        # a. A test that requires a servo always calls get_servo_arguments
        # and passes in its return value as |servo_args|.
        # b. get_servo_arguments never returns None.
        # Based on the assumptions, we reason that only in case 2 and 3
        # a servo is required, i.e. when the servo_args is not None.
        if servo_args is not None:
            self.servo = self._servo_host.create_healthy_servo_object()
        if chameleon_args is not None:
            self.chameleon = self._chameleon_host.create_chameleon_board()


    def _create_chameleon_host(self, chameleon_args):
        """Create a ChameleonHost object.

        There three possible cases:
        1) If the DUT is in Cros Lab and has a chameleon board, then create
           a ChameleonHost object pointing to the board. chameleon_args
           is ignored.
        2) If not case 1) and chameleon_args is neither None nor empty, then
           create a ChameleonHost object using chameleon_args.
        3) If neither case 1) or 2) applies, return None.

        @param chameleon_args: A dictionary that contains args for creating
                           a ChameleonHost object,
                           e.g. {'chameleon_host': '172.11.11.112',
                                 'chameleon_port': 9992}.

        @returns: A ChameleonHost object or None.

        """
        hostname = chameleon_host.make_chameleon_hostname(self.hostname)
        if utils.host_is_in_lab_zone(hostname):
            return chameleon_host.ChameleonHost(chameleon_host=hostname)
        elif chameleon_args is not None:
            return chameleon_host.ChameleonHost(**chameleon_args)
        else:
            return None


    def _create_servo_host(self, servo_args):
        """Create a ServoHost object.

        There three possible cases:
        1) If the DUT is in Cros Lab and has a beaglebone and a servo, then
           create a ServoHost object pointing to the beaglebone. servo_args
           is ignored.
        2) If not case 1) and servo_args is neither None nor empty, then
           create a ServoHost object using servo_args.
        3) If neither case 1) or 2) applies, return None.

        @param servo_args: A dictionary that contains args for creating
                           a ServoHost object,
                           e.g. {'servo_host': '172.11.11.111',
                                 'servo_port': 9999}.
                           See comments above.

        @returns: A ServoHost object or None. See comments above.

        """
        hostname = servo_host.make_servo_hostname(self.hostname)
        if utils.host_is_in_lab_zone(hostname):
            return servo_host.ServoHost(servo_host=hostname)
        elif servo_args is not None:
            return servo_host.ServoHost(**servo_args)
        else:
            return None


    def get_repair_image_name(self):
        """Generate a image_name from variables in the global config.

        @returns a str of $board-version/$BUILD.

        """
        stable_version = global_config.global_config.get_config_value(
                'CROS', 'stable_cros_version')
        build_pattern = global_config.global_config.get_config_value(
                'CROS', 'stable_build_pattern')
        board = self._get_board_from_afe()
        if board is None:
            raise error.AutoservError('DUT has no board attribute, '
                                      'cannot be repaired.')
        return build_pattern % (board, stable_version)


    def _host_in_AFE(self):
        """Check if the host is an object the AFE knows.

        @returns the host object.
        """
        return self._AFE.get_hosts(hostname=self.hostname)


    def lookup_job_repo_url(self):
        """Looks up the job_repo_url for the host.

        @returns job_repo_url from AFE or None if not found.

        @raises KeyError if the host does not have a job_repo_url
        """
        if not self._host_in_AFE():
            return None

        hosts = self._AFE.get_hosts(hostname=self.hostname)
        if hosts and ds_constants.JOB_REPO_URL in hosts[0].attributes:
            return hosts[0].attributes[ds_constants.JOB_REPO_URL]


    def clear_cros_version_labels_and_job_repo_url(self):
        """Clear cros_version labels and host attribute job_repo_url."""
        if not self._host_in_AFE():
            return

        host_list = [self.hostname]
        labels = self._AFE.get_labels(
                name__startswith=ds_constants.VERSION_PREFIX,
                host__hostname=self.hostname)

        for label in labels:
            label.remove_hosts(hosts=host_list)

        self.update_job_repo_url(None, None)


    def update_job_repo_url(self, devserver_url, image_name):
        """
        Updates the job_repo_url host attribute and asserts it's value.

        @param devserver_url: The devserver to use in the job_repo_url.
        @param image_name: The name of the image to use in the job_repo_url.

        @raises AutoservError: If we failed to update the job_repo_url.
        """
        repo_url = None
        if devserver_url and image_name:
            repo_url = tools.get_package_url(devserver_url, image_name)
        self._AFE.set_host_attribute(ds_constants.JOB_REPO_URL, repo_url,
                                     hostname=self.hostname)
        if self.lookup_job_repo_url() != repo_url:
            raise error.AutoservError('Failed to update job_repo_url with %s, '
                                      'host %s' % (repo_url, self.hostname))


    def add_cros_version_labels_and_job_repo_url(self, image_name):
        """Add cros_version labels and host attribute job_repo_url.

        @param image_name: The name of the image e.g.
                lumpy-release/R27-3837.0.0

        """
        if not self._host_in_AFE():
            return

        cros_label = '%s%s' % (ds_constants.VERSION_PREFIX, image_name)
        devserver_url = dev_server.ImageServer.resolve(image_name).url()

        labels = self._AFE.get_labels(name=cros_label)
        if labels:
            label = labels[0]
        else:
            label = self._AFE.create_label(name=cros_label)

        label.add_hosts([self.hostname])
        self.update_job_repo_url(devserver_url, image_name)


    def verify_job_repo_url(self, tag=''):
        """
        Make sure job_repo_url of this host is valid.

        Eg: The job_repo_url "http://lmn.cd.ab.xyx:8080/static/\
        lumpy-release/R29-4279.0.0/autotest/packages" claims to have the
        autotest package for lumpy-release/R29-4279.0.0. If this isn't the case,
        download and extract it. If the devserver embedded in the url is
        unresponsive, update the job_repo_url of the host after staging it on
        another devserver.

        @param job_repo_url: A url pointing to the devserver where the autotest
            package for this build should be staged.
        @param tag: The tag from the server job, in the format
                    <job_id>-<user>/<hostname>, or <hostless> for a server job.

        @raises DevServerException: If we could not resolve a devserver.
        @raises AutoservError: If we're unable to save the new job_repo_url as
            a result of choosing a new devserver because the old one failed to
            respond to a health check.
        @raises urllib2.URLError: If the devserver embedded in job_repo_url
                                  doesn't respond within the timeout.
        """
        job_repo_url = self.lookup_job_repo_url()
        if not job_repo_url:
            logging.warning('No job repo url set on host %s', self.hostname)
            return

        logging.info('Verifying job repo url %s', job_repo_url)
        devserver_url, image_name = tools.get_devserver_build_from_package_url(
            job_repo_url)

        ds = dev_server.ImageServer(devserver_url)

        logging.info('Staging autotest artifacts for %s on devserver %s',
            image_name, ds.url())

        start_time = time.time()
        ds.stage_artifacts(image_name, ['autotest'])
        stage_time = time.time() - start_time

        # Record how much of the verification time comes from a devserver
        # restage. If we're doing things right we should not see multiple
        # devservers for a given board/build/branch path.
        try:
            board, build_type, branch = server_utils.ParseBuildName(
                                                image_name)[:3]
        except server_utils.ParseBuildNameException:
            pass
        else:
            devserver = devserver_url[
                devserver_url.find('/') + 2:devserver_url.rfind(':')]
            stats_key = {
                'board': board,
                'build_type': build_type,
                'branch': branch,
                'devserver': devserver.replace('.', '_'),
            }
            stats.Gauge('verify_job_repo_url').send(
                '%(board)s.%(build_type)s.%(branch)s.%(devserver)s' % stats_key,
                stage_time)


    def _try_stateful_update(self, update_url, force_update, updater):
        """Try to use stateful update to initialize DUT.

        When DUT is already running the same version that machine_install
        tries to install, stateful update is a much faster way to clean up
        the DUT for testing, compared to a full reimage. It is implemeted
        by calling autoupdater.run_update, but skipping updating root, as
        updating the kernel is time consuming and not necessary.

        @param update_url: url of the image.
        @param force_update: Set to True to update the image even if the DUT
            is running the same version.
        @param updater: ChromiumOSUpdater instance used to update the DUT.
        @returns: True if the DUT was updated with stateful update.

        """
        if not updater.check_version():
            return False
        if not force_update:
            logging.info('Canceling stateful update because the new and '
                         'old versions are the same.')
            return False
        # Following folders should be rebuilt after stateful update.
        # A test file is used to confirm each folder gets rebuilt after
        # the stateful update.
        folders_to_check = ['/var', '/home', '/mnt/stateful_partition']
        test_file = '.test_file_to_be_deleted'
        for folder in folders_to_check:
            touch_path = os.path.join(folder, test_file)
            self.run('touch %s' % touch_path)

        if not updater.run_update(force_update=True, update_root=False):
            return False

        # Reboot to complete stateful update.
        self.reboot(timeout=self.REBOOT_TIMEOUT, wait=True)
        check_file_cmd = 'test -f %s; echo $?'
        for folder in folders_to_check:
            test_file_path = os.path.join(folder, test_file)
            result = self.run(check_file_cmd % test_file_path,
                              ignore_status=True)
            if result.exit_status == 1:
                return False
        return True


    def _post_update_processing(self, updater, expected_kernel=None):
        """After the DUT is updated, confirm machine_install succeeded.

        @param updater: ChromiumOSUpdater instance used to update the DUT.
        @param expected_kernel: kernel expected to be active after reboot,
            or `None` to skip rollback checking.

        """
        # Touch the lab machine file to leave a marker that
        # distinguishes this image from other test images.
        # Afterwards, we must re-run the autoreboot script because
        # it depends on the _LAB_MACHINE_FILE.
        self.run('touch %s' % self._LAB_MACHINE_FILE)
        self.run('start autoreboot')
        updater.verify_boot_expectations(
                expected_kernel, rollback_message=
                'Build %s failed to boot on %s; system rolled back to previous'
                'build' % (updater.update_version, self.hostname))
        # Check that we've got the build we meant to install.
        if not updater.check_version_to_confirm_install():
            raise autoupdater.ChromiumOSError(
                'Failed to update %s to build %s; found build '
                '%s instead' % (self.hostname,
                                updater.update_version,
                                updater.get_build_id()))


    def _stage_image_for_update(self, image_name=None):
        """Stage a build on a devserver and return the update_url.

        @param image_name: a name like lumpy-release/R27-3837.0.0
        @returns an update URL like:
            http://172.22.50.205:8082/update/lumpy-release/R27-3837.0.0
        """
        if not image_name:
            image_name = self.get_repair_image_name()
        logging.info('Staging build for AU: %s', image_name)
        devserver = dev_server.ImageServer.resolve(image_name)
        devserver.trigger_download(image_name, synchronous=False)
        return tools.image_url_pattern() % (devserver.url(), image_name)


    def stage_image_for_servo(self, image_name=None):
        """Stage a build on a devserver and return the update_url.

        @param image_name: a name like lumpy-release/R27-3837.0.0
        @returns an update URL like:
            http://172.22.50.205:8082/update/lumpy-release/R27-3837.0.0
        """
        if not image_name:
            image_name = self.get_repair_image_name()
        logging.info('Staging build for servo install: %s', image_name)
        devserver = dev_server.ImageServer.resolve(image_name)
        devserver.stage_artifacts(image_name, ['test_image'])
        return devserver.get_test_image_url(image_name)


    def stage_factory_image_for_servo(self, image_name):
        """Stage a build on a devserver and return the update_url.

        @param image_name: a name like <baord>/4262.204.0

        @return: An update URL, eg:
            http://<devserver>/static/canary-channel/\
            <board>/4262.204.0/factory_test/chromiumos_factory_image.bin

        @raises: ValueError if the factory artifact name is missing from
                 the config.

        """
        if not image_name:
            logging.error('Need an image_name to stage a factory image.')
            return

        factory_artifact = global_config.global_config.get_config_value(
                'CROS', 'factory_artifact', type=str, default='')
        if not factory_artifact:
            raise ValueError('Cannot retrieve the factory artifact name from '
                             'autotest config, and hence cannot stage factory '
                             'artifacts.')

        logging.info('Staging build for servo install: %s', image_name)
        devserver = dev_server.ImageServer.resolve(image_name)
        devserver.stage_artifacts(
                image_name,
                [factory_artifact],
                archive_url=None)

        return tools.factory_image_url_pattern() % (devserver.url(), image_name)


    def machine_install(self, update_url=None, force_update=False,
                        local_devserver=False, repair=False):
        """Install the DUT.

        Use stateful update if the DUT is already running the same build.
        Stateful update does not update kernel and tends to run much faster
        than a full reimage. If the DUT is running a different build, or it
        failed to do a stateful update, full update, including kernel update,
        will be applied to the DUT.

        Once a host enters machine_install its cros_version label will be
        removed as well as its host attribute job_repo_url (used for
        package install).

        @param update_url: The url to use for the update
                pattern: http://$devserver:###/update/$build
                If update_url is None and repair is True we will install the
                stable image listed in global_config under
                CROS.stable_cros_version.
        @param force_update: Force an update even if the version installed
                is the same. Default:False
        @param local_devserver: Used by run_remote_test to allow people to
                use their local devserver. Default: False
        @param repair: Whether or not we are in repair mode. This adds special
                cases for repairing a machine like starting update_engine.
                Setting repair to True sets force_update to True as well.
                default: False
        @raises autoupdater.ChromiumOSError

        """
        if update_url:
            logging.debug('update url is set to %s', update_url)
        else:
            logging.debug('update url is not set, resolving...')
            if self._parser.options.image:
                requested_build = self._parser.options.image
                if requested_build.startswith('http://'):
                    update_url = requested_build
                    logging.debug('update url is retrieved from requested_build'
                                  ': %s', update_url)
                else:
                    # Try to stage any build that does not start with
                    # http:// on the devservers defined in
                    # global_config.ini.
                    update_url = self._stage_image_for_update(requested_build)
                    logging.debug('Build staged, and update_url is set to: %s',
                                  update_url)
            elif repair:
                update_url = self._stage_image_for_update()
                logging.debug('Build staged, and update_url is set to: %s',
                              update_url)
            else:
                raise autoupdater.ChromiumOSError(
                    'Update failed. No update URL provided.')

        if repair:
            # In case the system is in a bad state, we always reboot the machine
            # before machine_install.
            self.reboot(timeout=self.REBOOT_TIMEOUT, wait=True)
            self.run('stop update-engine; start update-engine')
            force_update = True

        updater = autoupdater.ChromiumOSUpdater(update_url, host=self,
                                                local_devserver=local_devserver)
        updated = False
        # Remove cros-version and job_repo_url host attribute from host.
        self.clear_cros_version_labels_and_job_repo_url()
        # If the DUT is already running the same build, try stateful update
        # first. Stateful update does not update kernel and tends to run much
        # faster than a full reimage.
        try:
            updated = self._try_stateful_update(
                    update_url, force_update, updater)
            if updated:
                logging.info('DUT is updated with stateful update.')
        except Exception as e:
            logging.exception(e)
            logging.warn('Failed to stateful update DUT, force to update.')

        inactive_kernel = None
        # Do a full update if stateful update is not applicable or failed.
        if not updated:
            # In case the system is in a bad state, we always reboot the
            # machine before machine_install.
            self.reboot(timeout=self.REBOOT_TIMEOUT, wait=True)

            # TODO(sosa): Remove temporary hack to get rid of bricked machines
            # that can't update due to a corrupted policy.
            self.run('rm -rf /var/lib/whitelist')
            self.run('touch /var/lib/whitelist')
            self.run('chmod -w /var/lib/whitelist')
            self.run('stop update-engine; start update-engine')

            if updater.run_update(force_update):
                updated = True
                # Figure out active and inactive kernel.
                active_kernel, inactive_kernel = updater.get_kernel_state()

                # Ensure inactive kernel has higher priority than active.
                if (updater.get_kernel_priority(inactive_kernel)
                        < updater.get_kernel_priority(active_kernel)):
                    raise autoupdater.ChromiumOSError(
                        'Update failed. The priority of the inactive kernel'
                        ' partition is less than that of the active kernel'
                        ' partition.')

                # Updater has returned successfully; reboot the host.
                self.reboot(timeout=self.REBOOT_TIMEOUT, wait=True)

        if updated:
            self._post_update_processing(updater, inactive_kernel)
            image_name = autoupdater.url_to_image_name(update_url)
            self.add_cros_version_labels_and_job_repo_url(image_name)

        # Clean up any old autotest directories which may be lying around.
        for path in global_config.global_config.get_config_value(
                'AUTOSERV', 'client_autodir_paths', type=list):
            self.run('rm -rf ' + path)


    def show_update_engine_log(self):
        """Output update engine log."""
        logging.debug('Dumping %s', constants.UPDATE_ENGINE_LOG)
        self.run('cat %s' % constants.UPDATE_ENGINE_LOG)


    def _get_board_from_afe(self):
        """Retrieve this host's board from its labels in the AFE.

        Looks for a host label of the form "board:<board>", and
        returns the "<board>" part of the label.  `None` is returned
        if there is not a single, unique label matching the pattern.

        @returns board from label, or `None`.
        """
        return server_utils.get_board_from_afe(self.hostname, self._AFE)


    def get_build(self):
        """Retrieve the current build for this Host from the AFE.

        Looks through this host's labels in the AFE to determine its build.

        @returns The current build or None if it could not find it or if there
                 were multiple build labels assigned to this host.
        """
        return server_utils.get_build_from_afe(self.hostname, self._AFE)


    def _install_repair(self):
        """Attempt to repair this host using upate-engine.

        If the host is up, try installing the DUT with a stable
        "repair" version of Chrome OS as defined in the global_config
        under CROS.stable_cros_version.

        @raises AutoservRepairMethodNA if the DUT is not reachable.
        @raises ChromiumOSError if the install failed for some reason.

        """
        if not self.is_up():
            raise error.AutoservRepairMethodNA('DUT unreachable for install.')

        logging.info('Attempting to reimage machine to repair image.')
        try:
            self.machine_install(repair=True)
        except autoupdater.ChromiumOSError as e:
            logging.exception(e)
            logging.info('Repair via install failed.')
            raise


    def _install_repair_with_powerwash(self):
        """Attempt to powerwash first then repair this host using update-engine.

        update-engine may fail due to a bad image. In such case, powerwash
        may help to cleanup the DUT for update-engine to work again.

        @raises AutoservRepairMethodNA if the DUT is not reachable.
        @raises ChromiumOSError if the install failed for some reason.

        """
        if not self.is_up():
            raise error.AutoservRepairMethodNA('DUT unreachable for install.')

        logging.info('Attempting to powerwash the DUT.')
        self.run('echo "fast safe" > '
                 '/mnt/stateful_partition/factory_install_reset')
        self.reboot(timeout=self.POWERWASH_BOOT_TIMEOUT, wait=True)
        if not self.is_up():
            logging.error('Powerwash failed. DUT did not come back after '
                          'reboot.')
            raise error.AutoservRepairFailure(
                    'DUT failed to boot from powerwash after %d seconds' %
                    self.POWERWASH_BOOT_TIMEOUT)

        logging.info('Powerwash succeeded.')
        self._install_repair()


    def servo_install(self, image_url=None, usb_boot_timeout=USB_BOOT_TIMEOUT,
                      install_timeout=INSTALL_TIMEOUT):
        """
        Re-install the OS on the DUT by:
        1) installing a test image on a USB storage device attached to the Servo
                board,
        2) booting that image in recovery mode, and then
        3) installing the image with chromeos-install.

        @param image_url: If specified use as the url to install on the DUT.
                otherwise boot the currently staged image on the USB stick.
        @param usb_boot_timeout: The usb_boot_timeout to use during reimage.
                Factory images need a longer usb_boot_timeout than regular
                cros images.
        @param install_timeout: The timeout to use when installing the chromeos
                image. Factory images need a longer install_timeout.

        @raises AutoservError if the image fails to boot.
        """

        usb_boot_timer_key = ('servo_install.usb_boot_timeout_%s'
                              % usb_boot_timeout)
        logging.info('Downloading image to USB, then booting from it. Usb boot '
                     'timeout = %s', usb_boot_timeout)
        timer = stats.Timer(usb_boot_timer_key)
        timer.start()
        self.servo.install_recovery_image(image_url)
        if not self.wait_up(timeout=usb_boot_timeout):
            raise error.AutoservRepairFailure(
                    'DUT failed to boot from USB after %d seconds' %
                    usb_boot_timeout)
        timer.stop()

        install_timer_key = ('servo_install.install_timeout_%s'
                             % install_timeout)
        timer = stats.Timer(install_timer_key)
        timer.start()
        logging.info('Installing image through chromeos-install.')
        self.run('chromeos-install --yes', timeout=install_timeout)
        timer.stop()

        logging.info('Power cycling DUT through servo.')
        self.servo.power_long_press()
        self.servo.switch_usbkey('off')
        # We *must* use power_on() here; on Parrot it's how we get
        # out of recovery mode.
        self.servo.get_power_state_controller().power_on()

        logging.info('Waiting for DUT to come back up.')
        if not self.wait_up(timeout=self.BOOT_TIMEOUT):
            raise error.AutoservError('DUT failed to reboot installed '
                                      'test image after %d seconds' %
                                      self.BOOT_TIMEOUT)


    def _servo_repair_reinstall(self):
        """Reinstall the DUT utilizing servo and a test image.

        Re-install the OS on the DUT by:
        1) installing a test image on a USB storage device attached to the Servo
                board,
        2) booting that image in recovery mode, and then
        3) installing the image with chromeos-install.

        @raises AutoservRepairMethodNA if the device does not have servo
                support.

        """
        if not self.servo:
            raise error.AutoservRepairMethodNA('Repair Reinstall NA: '
                                               'DUT has no servo support.')

        logging.info('Attempting to recovery servo enabled device with '
                     'servo_repair_reinstall')

        image_url = self.stage_image_for_servo()
        self.servo_install(image_url)


    def _servo_repair_power(self):
        """Attempt to repair DUT using an attached Servo.

        Attempt to power on the DUT via power_long_press.

        @raises AutoservRepairMethodNA if the device does not have servo
                support.
        @raises AutoservRepairFailure if the repair fails for any reason.
        """
        if not self.servo:
            raise error.AutoservRepairMethodNA('Repair Power NA: '
                                               'DUT has no servo support.')

        logging.info('Attempting to recover servo enabled device by '
                     'powering it off and on.')
        self.servo.get_power_state_controller().power_off()
        self.servo.get_power_state_controller().power_on()
        if self.wait_up(self.BOOT_TIMEOUT):
            return

        raise error.AutoservRepairFailure('DUT did not boot after long_press.')


    def _powercycle_to_repair(self):
        """Utilize the RPM Infrastructure to bring the host back up.

        If the host is not up/repaired after the first powercycle we utilize
        auto fallback to the last good install by powercycling and rebooting the
        host 6 times.

        @raises AutoservRepairMethodNA if the device does not support remote
                power.
        @raises AutoservRepairFailure if the repair fails for any reason.

        """
        if not self.has_power():
            raise error.AutoservRepairMethodNA('Device does not support power.')

        logging.info('Attempting repair via RPM powercycle.')
        failed_cycles = 0
        self.power_cycle()
        while not self.wait_up(timeout=self.BOOT_TIMEOUT):
            failed_cycles += 1
            if failed_cycles >= self._MAX_POWER_CYCLE_ATTEMPTS:
                raise error.AutoservRepairFailure(
                        'Powercycled host %s %d times; device did not come back'
                        ' online.' % (self.hostname, failed_cycles))
            self.power_cycle()
        if failed_cycles == 0:
            logging.info('Powercycling was successful first time.')
        else:
            logging.info('Powercycling was successful after %d failures.',
                         failed_cycles)


    def repair_full(self):
        """Repair a host for repair level NO_PROTECTION.

        This overrides the base class function for repair; it does
        not call back to the parent class, but instead offers a
        simplified implementation based on the capabilities in the
        Chrome OS test lab.

        It first verifies and repairs servo if it is a DUT in CrOS
        lab and a servo is attached.

        If `self.verify()` fails, the following procedures are
        attempted:
          1. Try to re-install to a known stable image using
             auto-update.
          2. If there's a servo for the DUT, try to power the DUT off and
             on.
          3. If there's a servo for the DUT, try to re-install via
             the servo.
          4. If the DUT can be power-cycled via RPM, try to repair
             by power-cycling.

        As with the parent method, the last operation performed on
        the DUT must be to call `self.verify()`; if that call fails,
        the exception it raises is passed back to the caller.

        @raises AutoservRepairTotalFailure if the repair process fails to
                fix the DUT.
        @raises ServoHostRepairTotalFailure if the repair process fails to
                fix the servo host if one is attached to the DUT.
        @raises AutoservSshPermissionDeniedError if it is unable
                to ssh to the servo host due to permission error.

        """
        if self._servo_host:
            try:
                self.servo = self._servo_host.create_healthy_servo_object()
            except Exception as e:
                self.servo = None
                logging.error('Could not create a healthy servo: %s', e)

        # TODO(scottz): This should use something similar to label_decorator,
        # but needs to be populated in order so DUTs are repaired with the
        # least amount of effort.
        repair_funcs = [self._install_repair,
                        self._install_repair_with_powerwash,
                        self._servo_repair_power,
                        self._servo_repair_reinstall,
                        self._powercycle_to_repair]
        errors = []
        board = self._get_board_from_afe()
        for repair_func in repair_funcs:
            try:
                repair_func()
                self.verify()
                stats.Counter(
                        '%s.SUCCEEDED' % repair_func.__name__).increment()
                if board:
                    stats.Counter(
                        '%s.%s.SUCCEEDED' % (repair_func.__name__,
                                             board)).increment()
                return
            except error.AutoservRepairMethodNA as e:
                stats.Counter(
                        '%s.RepairNA' % repair_func.__name__).increment()
                if board:
                    stats.Counter(
                        '%s.%s.RepairNA' % (repair_func.__name__,
                                            board)).increment()
                logging.warn('Repair function NA: %s', e)
                errors.append(str(e))
            except Exception as e:
                stats.Counter(
                        '%s.FAILED' % repair_func.__name__).increment()
                if board:
                    stats.Counter(
                        '%s.%s.FAILED' % (repair_func.__name__,
                                          board)).increment()
                logging.warn('Failed to repair device: %s', e)
                errors.append(str(e))

        stats.Counter('Full_Repair_Failed').increment()
        if board:
            stats.Counter(
                'Full_Repair_Failed.%s' % board).increment()
        raise error.AutoservRepairTotalFailure(
                'All attempts at repairing the device failed:\n%s' %
                '\n'.join(errors))


    def close(self):
        self.rpc_disconnect_all()
        super(CrosHost, self).close()


    def _cleanup_poweron(self):
        """Special cleanup method to make sure hosts always get power back."""
        afe = frontend_wrappers.RetryingAFE(timeout_min=5, delay_sec=10)
        hosts = afe.get_hosts(hostname=self.hostname)
        if not hosts or not (self._RPM_OUTLET_CHANGED in
                             hosts[0].attributes):
            return
        logging.debug('This host has recently interacted with the RPM'
                      ' Infrastructure. Ensuring power is on.')
        try:
            self.power_on()
        except rpm_client.RemotePowerException:
            # If cleanup has completed but there was an issue with the RPM
            # Infrastructure, log an error message rather than fail cleanup
            logging.error('Failed to turn Power On for this host after '
                          'cleanup through the RPM Infrastructure.')
        afe.set_host_attribute(self._RPM_OUTLET_CHANGED, None,
                               hostname=self.hostname)


    def _is_factory_image(self):
        """Checks if the image on the DUT is a factory image.

        @return: True if the image on the DUT is a factory image.
                 False otherwise.
        """
        result = self.run('[ -f /root/.factory_test ]', ignore_status=True)
        return result.exit_status == 0


    def _restart_ui(self):
        """Restarts ui.

        @raises: FactoryImageCheckerException for factory images, since
                 we cannot attempt to restart ui on them.
                 error.AutoservRunError for any other type of error that
                 occurs while restarting ui.
        """
        if self._is_factory_image():
           raise FactoryImageCheckerException('Cannot restart ui on factory '
                                              'images')

        client_at = autotest.Autotest(self)
        client_at.run_static_method('autotest_lib.client.cros.cros_ui',
                                    '_clear_login_prompt_state')
        self.run('restart ui')
        client_at.run_static_method('autotest_lib.client.cros.cros_ui',
                                    '_wait_for_login_prompt')


    def cleanup(self):
        self.run('rm -f %s' % constants.CLEANUP_LOGS_PAUSED_FILE)
        try:
            self._restart_ui()
        except (error.AutotestRunError, error.AutoservRunError,
                FactoryImageCheckerException):
            logging.warn('Unable to restart ui, rebooting device.')
            # Since restarting the UI fails fall back to normal Autotest
            # cleanup routines, i.e. reboot the machine.
            super(CrosHost, self).cleanup()
        # Check if the rpm outlet was manipulated.
        if self.has_power():
            self._cleanup_poweron()


    def reboot(self, **dargs):
        """
        This function reboots the site host. The more generic
        RemoteHost.reboot() performs sync and sleeps for 5
        seconds. This is not necessary for Chrome OS devices as the
        sync should be finished in a short time during the reboot
        command.
        """
        if 'reboot_cmd' not in dargs:
            dargs['reboot_cmd'] = ('((reboot & sleep 10; reboot -f &)'
                                   ' </dev/null >/dev/null 2>&1 &)')
        # Enable fastsync to avoid running extra sync commands before reboot.
        if 'fastsync' not in dargs:
            dargs['fastsync'] = True
        super(CrosHost, self).reboot(**dargs)


    def verify_software(self):
        """Verify working software on a Chrome OS system.

        Tests for the following conditions:
         1. All conditions tested by the parent version of this
            function.
         2. Sufficient space in /mnt/stateful_partition.
         3. Sufficient space in /mnt/stateful_partition/encrypted.
         4. update_engine answers a simple status request over DBus.

        """
        super(CrosHost, self).verify_software()
        self.check_diskspace(
            '/mnt/stateful_partition',
            global_config.global_config.get_config_value(
                'SERVER', 'gb_diskspace_required', type=float,
                default=20.0))
        self.check_diskspace(
            '/mnt/stateful_partition/encrypted',
            global_config.global_config.get_config_value(
                'SERVER', 'gb_encrypted_diskspace_required', type=float,
                default=0.1))

        # Factory images don't run update engine,
        # goofy controls dbus on these DUTs.
        if not self._is_factory_image():
            self.run('update_engine_client --status')
        # Makes sure python is present, loads and can use built in functions.
        # We have seen cases where importing cPickle fails with undefined
        # symbols in cPickle.so.
        self.run('python -c "import cPickle"')


    def make_ssh_command(self, user='root', port=22, opts='', hosts_file=None,
                         connect_timeout=None, alive_interval=None):
        """Override default make_ssh_command to use options tuned for Chrome OS.

        Tuning changes:
          - ConnectTimeout=30; maximum of 30 seconds allowed for an SSH
          connection failure.  Consistency with remote_access.sh.

          - ServerAliveInterval=180; which causes SSH to ping connection every
          180 seconds. In conjunction with ServerAliveCountMax ensures
          that if the connection dies, Autotest will bail out quickly.
          Originally tried 60 secs, but saw frequent job ABORTS where
          the test completed successfully.

          - ServerAliveCountMax=3; consistency with remote_access.sh.

          - ConnectAttempts=4; reduce flakiness in connection errors;
          consistency with remote_access.sh.

          - UserKnownHostsFile=/dev/null; we don't care about the keys.
          Host keys change with every new installation, don't waste
          memory/space saving them.

          - SSH protocol forced to 2; needed for ServerAliveInterval.

        @param user User name to use for the ssh connection.
        @param port Port on the target host to use for ssh connection.
        @param opts Additional options to the ssh command.
        @param hosts_file Ignored.
        @param connect_timeout Ignored.
        @param alive_interval Ignored.
        """
        base_command = ('/usr/bin/ssh -a -x %s %s %s'
                        ' -o StrictHostKeyChecking=no'
                        ' -o UserKnownHostsFile=/dev/null -o BatchMode=yes'
                        ' -o ConnectTimeout=30 -o ServerAliveInterval=180'
                        ' -o ServerAliveCountMax=3 -o ConnectionAttempts=4'
                        ' -o Protocol=2 -l %s -p %d')
        return base_command % (self._ssh_verbosity_flag, self._ssh_options,
                               opts, user, port)


    def _create_ssh_tunnel(self, port, local_port):
        """Create an ssh tunnel from local_port to port.

        @param port: remote port on the host.
        @param local_port: local forwarding port.

        @return: the tunnel process.
        """
        # Chrome OS on the target closes down most external ports
        # for security.  We could open the port, but doing that
        # would conflict with security tests that check that only
        # expected ports are open.  So, to get to the port on the
        # target we use an ssh tunnel.
        tunnel_options = '-n -N -q -L %d:localhost:%d' % (local_port, port)
        ssh_cmd = self.make_ssh_command(opts=tunnel_options)
        tunnel_cmd = '%s %s' % (ssh_cmd, self.hostname)
        logging.debug('Full tunnel command: %s', tunnel_cmd)
        tunnel_proc = subprocess.Popen(tunnel_cmd, shell=True, close_fds=True)
        logging.debug('Started ssh tunnel, local = %d'
                      ' remote = %d, pid = %d',
                      local_port, port, tunnel_proc.pid)
        return tunnel_proc


    def _setup_rpc(self, port, command_name, remote_pid=None):
        """Sets up a tunnel process and performs rpc connection book keeping.

        This method assumes that xmlrpc and jsonrpc never conflict, since
        we can only either have an xmlrpc or a jsonrpc server listening on
        a remote port. As such, it enforces a single proxy->remote port
        policy, i.e if one starts a jsonrpc proxy/server from port A->B,
        and then tries to start an xmlrpc proxy forwarded to the same port,
        the xmlrpc proxy will override the jsonrpc tunnel process, however:

        1. None of the methods on the xmlrpc proxy will work because
        the server listening on B is jsonrpc.

        2. The xmlrpc client cannot initiate a termination of the JsonRPC
        server, as the only use case currently is goofy, which is tied to
        the factory image. It is much easier to handle a failed xmlrpc
        call on the client than it is to terminate goofy in this scenario,
        as doing the latter might leave the DUT in a hard to recover state.

        With the current implementation newer rpc proxy connections will
        terminate the tunnel processes of older rpc connections tunneling
        to the same remote port. If methods are invoked on the client
        after this has happened they will fail with connection closed errors.

        @param port: The remote forwarding port.
        @param command_name: The name of the remote process, to terminate
                              using pkill.

        @return A url that we can use to initiate the rpc connection.
        """
        self.rpc_disconnect(port)
        local_port = utils.get_unused_port()
        tunnel_proc = self._create_ssh_tunnel(port, local_port)
        self._rpc_proxy_map[port] = (command_name, tunnel_proc, remote_pid)
        return self._RPC_PROXY_URL % local_port


    def xmlrpc_connect(self, command, port, command_name=None,
                       ready_test_name=None, timeout_seconds=10,
                       logfile='/dev/null'):
        """Connect to an XMLRPC server on the host.

        The `command` argument should be a simple shell command that
        starts an XMLRPC server on the given `port`.  The command
        must not daemonize, and must terminate cleanly on SIGTERM.
        The command is started in the background on the host, and a
        local XMLRPC client for the server is created and returned
        to the caller.

        Note that the process of creating an XMLRPC client makes no
        attempt to connect to the remote server; the caller is
        responsible for determining whether the server is running
        correctly, and is ready to serve requests.

        Optionally, the caller can pass ready_test_name, a string
        containing the name of a method to call on the proxy.  This
        method should take no parameters and return successfully only
        when the server is ready to process client requests.  When
        ready_test_name is set, xmlrpc_connect will block until the
        proxy is ready, and throw a TestError if the server isn't
        ready by timeout_seconds.

        If a server is already running on the remote port, this
        method will kill it and disconnect the tunnel process
        associated with the connection before establishing a new one,
        by consulting the rpc_proxy_map in rpc_disconnect.

        @param command Shell command to start the server.
        @param port Port number on which the server is expected to
                    be serving.
        @param command_name String to use as input to `pkill` to
            terminate the XMLRPC server on the host.
        @param ready_test_name String containing the name of a
            method defined on the XMLRPC server.
        @param timeout_seconds Number of seconds to wait
            for the server to become 'ready.'  Will throw a
            TestFail error if server is not ready in time.
        @param logfile Logfile to send output when running
            'command' argument.

        """
        # Clean up any existing state.  If the caller is willing
        # to believe their server is down, we ought to clean up
        # any tunnels we might have sitting around.
        self.rpc_disconnect(port)
        # Start the server on the host.  Redirection in the command
        # below is necessary, because 'ssh' won't terminate until
        # background child processes close stdin, stdout, and
        # stderr.
        remote_cmd = '%s </dev/null >%s 2>&1 & echo $!' % (command, logfile)
        remote_pid = self.run(remote_cmd).stdout.rstrip('\n')
        logging.debug('Started XMLRPC server on host %s, pid = %s',
                      self.hostname, remote_pid)

        # Tunnel through SSH to be able to reach that remote port.
        rpc_url = self._setup_rpc(port, command_name, remote_pid=remote_pid)
        proxy = xmlrpclib.ServerProxy(rpc_url, allow_none=True)

        if ready_test_name is not None:
            # retry.retry logs each attempt; calculate delay_sec to
            # keep log spam to a dull roar.
            @retry.retry((socket.error,
                          xmlrpclib.ProtocolError,
                          httplib.BadStatusLine),
                         timeout_min=timeout_seconds / 60.0,
                         delay_sec=min(max(timeout_seconds / 20.0, 0.1), 1))
            def ready_test():
                """ Call proxy.ready_test_name(). """
                getattr(proxy, ready_test_name)()
            successful = False
            try:
                logging.info('Waiting %d seconds for XMLRPC server '
                             'to start.', timeout_seconds)
                ready_test()
                successful = True
            finally:
                if not successful:
                    logging.error('Failed to start XMLRPC server.')
                    self.rpc_disconnect(port)
        logging.info('XMLRPC server started successfully.')
        return proxy


    def syslog(self, message, tag='autotest'):
        """Logs a message to syslog on host.

        @param message String message to log into syslog
        @param tag String tag prefix for syslog

        """
        self.run('logger -t "%s" "%s"' % (tag, message))


    def jsonrpc_connect(self, port):
        """Creates a jsonrpc proxy connection through an ssh tunnel.

        This method exists to facilitate communication with goofy (which is
        the default system manager on all factory images) and as such, leaves
        most of the rpc server sanity checking to the caller. Unlike
        xmlrpc_connect, this method does not facilitate the creation of a remote
        jsonrpc server, as the only clients of this code are factory tests,
        for which the goofy system manager is built in to the image and starts
        when the target boots.

        One can theoretically create multiple jsonrpc proxies all forwarded
        to the same remote port, provided the remote port has an rpc server
        listening. However, in doing so we stand the risk of leaking an
        existing tunnel process, so we always disconnect any older tunnels
        we might have through rpc_disconnect.

        @param port: port on the remote host that is serving this proxy.

        @return: The client proxy.
        """
        if not jsonrpclib:
            logging.warning('Jsonrpclib could not be imported. Check that '
                            'site-packages contains jsonrpclib.')
            return None

        proxy = jsonrpclib.jsonrpc.ServerProxy(self._setup_rpc(port, None))

        logging.info('Established a jsonrpc connection through port %s.', port)
        return proxy


    def rpc_disconnect(self, port):
        """Disconnect from an RPC server on the host.

        Terminates the remote RPC server previously started for
        the given `port`.  Also closes the local ssh tunnel created
        for the connection to the host.  This function does not
        directly alter the state of a previously returned RPC
        client object; however disconnection will cause all
        subsequent calls to methods on the object to fail.

        This function does nothing if requested to disconnect a port
        that was not previously connected via _setup_rpc.

        @param port Port number passed to a previous call to
                    `_setup_rpc()`.
        """
        if port not in self._rpc_proxy_map:
            return
        remote_name, tunnel_proc, remote_pid = self._rpc_proxy_map[port]
        if remote_name:
            # We use 'pkill' to find our target process rather than
            # a PID, because the host may have rebooted since
            # connecting, and we don't want to kill an innocent
            # process with the same PID.
            #
            # 'pkill' helpfully exits with status 1 if no target
            # process  is found, for which run() will throw an
            # exception.  We don't want that, so we the ignore
            # status.
            self.run("pkill -f '%s'" % remote_name, ignore_status=True)
            if remote_pid:
                logging.info('Waiting for RPC server "%s" shutdown',
                             remote_name)
                start_time = time.time()
                while (time.time() - start_time <
                       self._RPC_SHUTDOWN_TIMEOUT_SECONDS):
                    running_processes = self.run(
                            "pgrep -f '%s'" % remote_name,
                            ignore_status=True).stdout.split()
                    if not remote_pid in running_processes:
                        logging.info('Shut down RPC server.')
                        break
                    time.sleep(self._RPC_SHUTDOWN_POLLING_PERIOD_SECONDS)
                else:
                    raise error.TestError('Failed to shutdown RPC server %s' %
                                          remote_name)

        if tunnel_proc.poll() is None:
            tunnel_proc.terminate()
            logging.debug('Terminated tunnel, pid %d', tunnel_proc.pid)
        else:
            logging.debug('Tunnel pid %d terminated early, status %d',
                          tunnel_proc.pid, tunnel_proc.returncode)
        del self._rpc_proxy_map[port]


    def rpc_disconnect_all(self):
        """Disconnect all known RPC proxy ports."""
        for port in self._rpc_proxy_map.keys():
            self.rpc_disconnect(port)


    def _ping_check_status(self, status):
        """Ping the host once, and return whether it has a given status.

        @param status Check the ping status against this value.
        @return True iff `status` and the result of ping are the same
                (i.e. both True or both False).

        """
        ping_val = utils.ping(self.hostname, tries=1, deadline=1)
        return not (status ^ (ping_val == 0))

    def _ping_wait_for_status(self, status, timeout):
        """Wait for the host to have a given status (UP or DOWN).

        Status is checked by polling.  Polling will not last longer
        than the number of seconds in `timeout`.  The polling
        interval will be long enough that only approximately
        _PING_WAIT_COUNT polling cycles will be executed, subject
        to a maximum interval of about one minute.

        @param status Waiting will stop immediately if `ping` of the
                      host returns this status.
        @param timeout Poll for at most this many seconds.
        @return True iff the host status from `ping` matched the
                requested status at the time of return.

        """
        # _ping_check_status() takes about 1 second, hence the
        # "- 1" in the formula below.
        poll_interval = min(int(timeout / self._PING_WAIT_COUNT), 60) - 1
        end_time = time.time() + timeout
        while time.time() <= end_time:
            if self._ping_check_status(status):
                return True
            if poll_interval > 0:
                time.sleep(poll_interval)

        # The last thing we did was sleep(poll_interval), so it may
        # have been too long since the last `ping`.  Check one more
        # time, just to be sure.
        return self._ping_check_status(status)

    def ping_wait_up(self, timeout):
        """Wait for the host to respond to `ping`.

        N.B.  This method is not a reliable substitute for
        `wait_up()`, because a host that responds to ping will not
        necessarily respond to ssh.  This method should only be used
        if the target DUT can be considered functional even if it
        can't be reached via ssh.

        @param timeout Minimum time to allow before declaring the
                       host to be non-responsive.
        @return True iff the host answered to ping before the timeout.

        """
        return self._ping_wait_for_status(self._PING_STATUS_UP, timeout)

    def ping_wait_down(self, timeout):
        """Wait until the host no longer responds to `ping`.

        This function can be used as a slightly faster version of
        `wait_down()`, by avoiding potentially long ssh timeouts.

        @param timeout Minimum time to allow for the host to become
                       non-responsive.
        @return True iff the host quit answering ping before the
                timeout.

        """
        return self._ping_wait_for_status(self._PING_STATUS_DOWN, timeout)

    def test_wait_for_sleep(self):
        """Wait for the client to enter low-power sleep mode.

        The test for "is asleep" can't distinguish a system that is
        powered off; to confirm that the unit was asleep, it is
        necessary to force resume, and then call
        `test_wait_for_resume()`.

        This function is expected to be called from a test as part
        of a sequence like the following:

        ~~~~~~~~
            boot_id = host.get_boot_id()
            # trigger sleep on the host
            host.test_wait_for_sleep()
            # trigger resume on the host
            host.test_wait_for_resume(boot_id)
        ~~~~~~~~

        @exception TestFail The host did not go to sleep within
                            the allowed time.
        """
        if not self.ping_wait_down(timeout=self.SLEEP_TIMEOUT):
            raise error.TestFail(
                'client failed to sleep after %d seconds' %
                    self.SLEEP_TIMEOUT)


    def test_wait_for_resume(self, old_boot_id):
        """Wait for the client to resume from low-power sleep mode.

        The `old_boot_id` parameter should be the value from
        `get_boot_id()` obtained prior to entering sleep mode.  A
        `TestFail` exception is raised if the boot id changes.

        See @ref test_wait_for_sleep for more on this function's
        usage.

        @param old_boot_id A boot id value obtained before the
                               target host went to sleep.

        @exception TestFail The host did not respond within the
                            allowed time.
        @exception TestFail The host responded, but the boot id test
                            indicated a reboot rather than a sleep
                            cycle.
        """
        if not self.wait_up(timeout=self.RESUME_TIMEOUT):
            raise error.TestFail(
                'client failed to resume from sleep after %d seconds' %
                    self.RESUME_TIMEOUT)
        else:
            new_boot_id = self.get_boot_id()
            if new_boot_id != old_boot_id:
                raise error.TestFail(
                    'client rebooted, but sleep was expected'
                    ' (old boot %s, new boot %s)'
                        % (old_boot_id, new_boot_id))


    def test_wait_for_shutdown(self):
        """Wait for the client to shut down.

        The test for "has shut down" can't distinguish a system that
        is merely asleep; to confirm that the unit was down, it is
        necessary to force boot, and then call test_wait_for_boot().

        This function is expected to be called from a test as part
        of a sequence like the following:

        ~~~~~~~~
            boot_id = host.get_boot_id()
            # trigger shutdown on the host
            host.test_wait_for_shutdown()
            # trigger boot on the host
            host.test_wait_for_boot(boot_id)
        ~~~~~~~~

        @exception TestFail The host did not shut down within the
                            allowed time.
        """
        if not self.ping_wait_down(timeout=self.SHUTDOWN_TIMEOUT):
            raise error.TestFail(
                'client failed to shut down after %d seconds' %
                    self.SHUTDOWN_TIMEOUT)


    def test_wait_for_boot(self, old_boot_id=None):
        """Wait for the client to boot from cold power.

        The `old_boot_id` parameter should be the value from
        `get_boot_id()` obtained prior to shutting down.  A
        `TestFail` exception is raised if the boot id does not
        change.  The boot id test is omitted if `old_boot_id` is not
        specified.

        See @ref test_wait_for_shutdown for more on this function's
        usage.

        @param old_boot_id A boot id value obtained before the
                               shut down.

        @exception TestFail The host did not respond within the
                            allowed time.
        @exception TestFail The host responded, but the boot id test
                            indicated that there was no reboot.
        """
        if not self.wait_up(timeout=self.REBOOT_TIMEOUT):
            raise error.TestFail(
                'client failed to reboot after %d seconds' %
                    self.REBOOT_TIMEOUT)
        elif old_boot_id:
            if self.get_boot_id() == old_boot_id:
                raise error.TestFail(
                    'client is back up, but did not reboot'
                    ' (boot %s)' % old_boot_id)


    @staticmethod
    def check_for_rpm_support(hostname):
        """For a given hostname, return whether or not it is powered by an RPM.

        @param hostname: hostname to check for rpm support.

        @return None if this host does not follows the defined naming format
                for RPM powered DUT's in the lab. If it does follow the format,
                it returns a regular expression MatchObject instead.
        """
        return re.match(CrosHost._RPM_HOSTNAME_REGEX, hostname)


    def has_power(self):
        """For this host, return whether or not it is powered by an RPM.

        @return True if this host is in the CROS lab and follows the defined
                naming format.
        """
        return CrosHost.check_for_rpm_support(self.hostname)


    def _set_power(self, state, power_method):
        """Sets the power to the host via RPM, Servo or manual.

        @param state Specifies which power state to set to DUT
        @param power_method Specifies which method of power control to
                            use. By default "RPM" will be used. Valid values
                            are the strings "RPM", "manual", "servoj10".

        """
        ACCEPTABLE_STATES = ['ON', 'OFF']

        if state.upper() not in ACCEPTABLE_STATES:
            raise error.TestError('State must be one of: %s.'
                                   % (ACCEPTABLE_STATES,))

        if power_method == self.POWER_CONTROL_SERVO:
            logging.info('Setting servo port J10 to %s', state)
            self.servo.set('prtctl3_pwren', state.lower())
            time.sleep(self._USB_POWER_TIMEOUT)
        elif power_method == self.POWER_CONTROL_MANUAL:
            logging.info('You have %d seconds to set the AC power to %s.',
                         self._POWER_CYCLE_TIMEOUT, state)
            time.sleep(self._POWER_CYCLE_TIMEOUT)
        else:
            if not self.has_power():
                raise error.TestFail('DUT does not have RPM connected.')
            afe = frontend_wrappers.RetryingAFE(timeout_min=5, delay_sec=10)
            afe.set_host_attribute(self._RPM_OUTLET_CHANGED, True,
                                   hostname=self.hostname)
            rpm_client.set_power(self.hostname, state.upper(), timeout_mins=5)


    def power_off(self, power_method=POWER_CONTROL_RPM):
        """Turn off power to this host via RPM, Servo or manual.

        @param power_method Specifies which method of power control to
                            use. By default "RPM" will be used. Valid values
                            are the strings "RPM", "manual", "servoj10".

        """
        self._set_power('OFF', power_method)


    def power_on(self, power_method=POWER_CONTROL_RPM):
        """Turn on power to this host via RPM, Servo or manual.

        @param power_method Specifies which method of power control to
                            use. By default "RPM" will be used. Valid values
                            are the strings "RPM", "manual", "servoj10".

        """
        self._set_power('ON', power_method)


    def power_cycle(self, power_method=POWER_CONTROL_RPM):
        """Cycle power to this host by turning it OFF, then ON.

        @param power_method Specifies which method of power control to
                            use. By default "RPM" will be used. Valid values
                            are the strings "RPM", "manual", "servoj10".

        """
        if power_method in (self.POWER_CONTROL_SERVO,
                            self.POWER_CONTROL_MANUAL):
            self.power_off(power_method=power_method)
            time.sleep(self._POWER_CYCLE_TIMEOUT)
            self.power_on(power_method=power_method)
        else:
            rpm_client.set_power(self.hostname, 'CYCLE')


    def get_platform(self):
        """Determine the correct platform label for this host.

        @returns a string representing this host's platform.
        """
        crossystem = utils.Crossystem(self)
        crossystem.init()
        # Extract fwid value and use the leading part as the platform id.
        # fwid generally follow the format of {platform}.{firmware version}
        # Example: Alex.X.YYY.Z or Google_Alex.X.YYY.Z
        platform = crossystem.fwid().split('.')[0].lower()
        # Newer platforms start with 'Google_' while the older ones do not.
        return platform.replace('google_', '')


    def get_chrome_version(self):
        """Gets the Chrome version number and milestone as strings.

        Invokes "chrome --version" to get the version number and milestone.

        @return A tuple (chrome_ver, milestone) where "chrome_ver" is the
            current Chrome version number as a string (in the form "W.X.Y.Z")
            and "milestone" is the first component of the version number
            (the "W" from "W.X.Y.Z").  If the version number cannot be parsed
            in the "W.X.Y.Z" format, the "chrome_ver" will be the full output
            of "chrome --version" and the milestone will be the empty string.

        """
        version_string = self.run(constants.CHROME_VERSION_COMMAND).stdout
        return utils.parse_chrome_version(version_string)

    @label_decorator()
    def get_board(self):
        """Determine the correct board label for this host.

        @returns a string representing this host's board.
        """
        release_info = utils.parse_cmd_output('cat /etc/lsb-release',
                                              run_method=self.run)
        board = release_info['CHROMEOS_RELEASE_BOARD']
        # Devices in the lab generally have the correct board name but our own
        # development devices have {board_name}-signed-{key_type}. The board
        # name may also begin with 'x86-' which we need to keep.
        board_format_string = ds_constants.BOARD_PREFIX + '%s'
        if 'x86' not in board:
            return board_format_string % board.split('-')[0]
        return board_format_string % '-'.join(board.split('-')[0:2])


    @label_decorator('lightsensor')
    def has_lightsensor(self):
        """Determine the correct board label for this host.

        @returns the string 'lightsensor' if this host has a lightsensor or
                 None if it does not.
        """
        search_cmd = "find -L %s -maxdepth 4 | egrep '%s'" % (
            self._LIGHTSENSOR_SEARCH_DIR, '|'.join(self._LIGHTSENSOR_FILES))
        try:
            # Run the search cmd following the symlinks. Stderr_tee is set to
            # None as there can be a symlink loop, but the command will still
            # execute correctly with a few messages printed to stderr.
            self.run(search_cmd, stdout_tee=None, stderr_tee=None)
            return 'lightsensor'
        except error.AutoservRunError:
            # egrep exited with a return code of 1 meaning none of the possible
            # lightsensor files existed.
            return None


    @label_decorator('bluetooth')
    def has_bluetooth(self):
        """Determine the correct board label for this host.

        @returns the string 'bluetooth' if this host has bluetooth or
                 None if it does not.
        """
        try:
            self.run('test -d /sys/class/bluetooth/hci0')
            # test exited with a return code of 0.
            return 'bluetooth'
        except error.AutoservRunError:
            # test exited with a return code 1 meaning the directory did not
            # exist.
            return None


    @label_decorator('graphics')
    def get_graphics(self):
        """
        Determine the correct board label for this host.

        @returns a string representing this host's graphics. For now ARM boards
        return graphics:gles while all other boards return graphics:gl. This
        may change over time, but for robustness reasons this should avoid
        executing code in actual graphics libraries (which may not be ready and
        is tested by graphics_GLAPICheck).
        """
        uname = self.run('uname -a').stdout.lower()
        if 'arm' in uname:
            return 'graphics:gles'
        return 'graphics:gl'


    def get_labels(self):
        """Return a list of labels for this given host.

        This is the main way to retrieve all the automatic labels for a host
        as it will run through all the currently implemented label functions.
        """
        labels = []
        for label_function in self._LABEL_FUNCTIONS:
            label = label_function(self)
            if label:
                labels.append(label)
        return labels
