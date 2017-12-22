# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# repohooks/pre-upload.py currently does not run pylint. But for developers who
# want to check their code manually we disable several harmless pylint warnings
# which just distract from more serious remaining issues.
#
# The instance variables _host and _install_paths are not defined in __init__().
# pylint: disable=attribute-defined-outside-init
#
# Many short variable names don't follow the naming convention.
# pylint: disable=invalid-name
#
# _parse_result() and _dir_size() don't access self and could be functions.
# pylint: disable=no-self-use
#
# _ChromeLogin and _TradefedLogCollector have no public methods.
# pylint: disable=too-few-public-methods

import contextlib
import errno
import glob
import hashlib
import lockfile
import logging
import os
import pipes
import random
import re
import shutil
import stat
import tempfile
import urlparse

from autotest_lib.client.bin import utils as client_utils
from autotest_lib.client.common_lib import utils as common_utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.server import autotest
from autotest_lib.server import test
from autotest_lib.server import utils
from autotest_lib.server.cros import cts_expected_failure_parser

# TODO(ihf): If akeshet doesn't fix crbug.com/691046 delete metrics again.
try:
    from chromite.lib import metrics
except ImportError:
    metrics = utils.metrics_mock

# TODO(ihf): Find a home for all these paths. This is getting out of hand.
_SDK_TOOLS_DIR = 'gs://chromeos-arc-images/builds/git_nyc-mr1-arc-linux-static_sdk_tools/3544738'
_SDK_TOOLS_FILES = ['aapt']

# To stabilize adb behavior, we use dynamically linked adb.
_ADB_DIR = 'gs://chromeos-arc-images/builds/git_nyc-mr1-arc-linux-cheets_arm-user/3544738'
_ADB_FILES = ['adb']

_ADB_POLLING_INTERVAL_SECONDS = 1
_ADB_READY_TIMEOUT_SECONDS = 60
_ANDROID_ADB_KEYS_PATH = '/data/misc/adb/adb_keys'

_ARC_POLLING_INTERVAL_SECONDS = 1
_ARC_READY_TIMEOUT_SECONDS = 60

_TRADEFED_PREFIX = 'autotest-tradefed-install_'
# While running CTS tradefed creates state in the installed location (there is
# currently no way to specify a dedicated result directory for all changes).
# For this reason we start each test with a clean copy of the CTS/GTS bundle.
_TRADEFED_CACHE_LOCAL = '/tmp/autotest-tradefed-cache'
# On lab servers and moblab all server tests run inside of lxc instances
# isolating file systems from each other. To avoid downloading CTS artifacts
# repeatedly for each test (or lxc instance) we share a common location
# /usr/local/autotest/results/shared which is visible to all lxc instances on
# that server. It needs to be writable as the cache is maintained jointly by
# all CTS/GTS tests. Currently both read and write access require taking the
# lock. Writes happen rougly monthly while reads are many times a day. If this
# becomes a bottleneck we could examine allowing concurrent reads.
_TRADEFED_CACHE_CONTAINER = '/usr/local/autotest/results/shared/cache'
_TRADEFED_CACHE_CONTAINER_LOCK = '/usr/local/autotest/results/shared/lock'
# The maximum size of the shared global cache. It needs to be able to hold
# N, M, x86, arm CTS bundles (500MB), the GTS bundle and media stress videos
# (2GB) zipped to not thrash. In addition it needs to be able to hold one
# different revision per Chrome OS branch. While this sounds  like a lot,
# only a single bundle is copied into each lxc instance (500MB), hence the
# impact of running say 100 CTS tests in parallel is acceptable (quarter
# servers have 500GB of disk, while full servers have 2TB).
_TRADEFED_CACHE_MAX_SIZE = (20 * 1024 * 1024 * 1024)

# It looks like the GCE builder can be very slow and login on VMs take much
# longer than on hardware or bare metal.
_LOGIN_BOARD_TIMEOUT = {'betty': 300}
_LOGIN_DEFAULT_TIMEOUT = 90


class _ChromeLogin(object):
    """Context manager to handle Chrome login state."""

    def need_reboot(self):
        """Marks state as "dirty" - reboot needed during/after test."""
        logging.info('Will reboot DUT when Chrome stops.')
        self._need_reboot = True

    def need_restart(self):
        """Marks state as "dirty" - restart needed after test."""
        self._need_restart = True

    def __init__(self, host, kwargs):
        """Initializes the _ChromeLogin object.

        @param reboot: indicate if a reboot before destruction is required.
        @param restart: indicate if a restart before destruction is required.
        @param board: optional parameter to extend timeout for login for slow
                      DUTs. Used in particular for virtual machines.
        """
        self._host = host
        self._cts_helper_kwargs = kwargs
        # We will override reboot/restart options to some degree. Keep track
        # of them in a local copy.
        self._need_reboot = False
        if kwargs.get('reboot'):
            self.need_reboot()
        self._need_restart = False
        if kwargs.get('restart'):
            self.need_restart()
        self._timeout = _LOGIN_DEFAULT_TIMEOUT
        board = kwargs.get('board')
        if board in _LOGIN_BOARD_TIMEOUT:
            self._timeout = _LOGIN_BOARD_TIMEOUT[board]

    def _cmd_builder(self, verbose=False):
        """Gets remote command to start browser with ARC enabled."""
        # If autotest is not installed on the host, as with moblab at times,
        # getting the autodir will raise an exception.
        cmd = autotest.Autotest.get_installed_autodir(self._host)
        cmd += '/bin/autologin.py --arc'
        if self._cts_helper_kwargs.get('dont_override_profile'):
            logging.info('Using --dont_override_profile to start Chrome.')
            cmd += ' --dont_override_profile'
        else:
            logging.info('Not using --dont_override_profile to start Chrome.')
        if not verbose:
            cmd += ' > /dev/null 2>&1'
        return cmd

    def login(self, timeout=None, raise_exception=False, verbose=False):
        """Logs into Chrome."""
        if not timeout:
            timout = self._timeout
        try:
            # We used to call cheets_StartAndroid, but it is a little faster to
            # call a script on the DUT. This also saves CPU time on the server.
            self._host.run(
                self._cmd_builder(),
                ignore_status=False,
                verbose=verbose,
                timeout=timeout)
            return True
        except autotest.AutodirNotFoundError:
            # Autotest is not installed (can happen on moblab after image
            # install). Fall back to logging in via client test, which as a side
            # effect installs autotest in the right place, so we should not hit
            # this slow path repeatedly.
            logging.warning('Autotest not installed, fallback to slow path...')
            try:
                autotest.Autotest(self._host).run_timed_test(
                    'cheets_StartAndroid',
                    timeout=2 * timeout,
                    check_client_result=True,
                    **self._cts_helper_kwargs)
                return True
            except:
                # We were unable to start the browser/Android. Maybe we can
                # salvage the DUT by rebooting. This can hide some failures.
                self.reboot()
                if raise_exception:
                    raise
        except:
            # We were unable to start the browser/Android. Maybe we can
            # salvage the DUT by rebooting. This can hide some failures.
            self.reboot()
            if raise_exception:
                raise
        return False

    def __enter__(self):
        """Logs into Chrome with retry."""
        timeout = self._timeout
        logging.info('Ensure Android is running (timeout=%d)...', timeout)
        if not self.login(timeout=timeout):
            timeout *= 2
            # The DUT reboots after unsuccessful login, try with more time again.
            logging.info('Retrying failed login (timeout=%d)...', timeout)
            self.login(timeout=timeout, raise_exception=True, verbose=True)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """On exit restart the browser or reboot the machine.

        @param exc_type: Exception type if an exception is raised from the
                         with-block.
        @param exc_value: Exception instance if an exception is raised from
                          the with-block.
        @param traceback: Stack trace info if an exception is raised from
                          the with-block.
        @return None, indicating not to ignore an exception from the with-block
                if raised.
        """
        if not self._need_reboot:
            logging.info('Skipping reboot, restarting browser.')
            try:
                self.restart()
            except:
                logging.error('Restarting browser has failed.')
                self.need_reboot()
        if self._need_reboot:
            self.reboot(exc_type, exc_value, traceback)

    def restart(self):
        # We clean up /tmp (which is memory backed) from crashes and
        # other files. A reboot would have cleaned /tmp as well.
        # TODO(ihf): Remove "start ui" which is a nicety to non-ARC tests (i.e.
        # now we wait on login screen, but login() above will 'stop ui' again
        # before launching Chrome with ARC enabled).
        script = 'stop ui'
        script += '&& find /tmp/ -mindepth 1 -delete '
        script += '&& start ui'
        self._host.run(script, ignore_status=False, verbose=False, timeout=120)

    def reboot(self, exc_type=None, exc_value=None, traceback=None):
        """Reboot the machine.

        @param exc_type: Exception type if an exception is raised from the
                         with-block.
        @param exc_value: Exception instance if an exception is raised from
                          the with-block.
        @param traceback: Stack trace info if an exception is raised from
                          the with-block.
        @return None, indicating not to ignore an exception from the with-block
                if raised.
        """
        logging.info('Rebooting...')
        try:
            self._host.reboot()
            self._need_reboot = False
        except Exception:
            if exc_type is None:
                raise
            # If an exception is raise from the with-block, just record the
            # exception for the rebooting to avoid ignoring the original
            # exception.
            logging.exception('Rebooting failed.')


@contextlib.contextmanager
def lock(filename):
    """Prevents other autotest/tradefed instances from accessing cache.

    @param filename: The file to be locked.
    """
    filelock = lockfile.FileLock(filename)
    # It is tempting just to call filelock.acquire(3600). But the implementation
    # has very poor temporal granularity (timeout/10), which is unsuitable for
    # our needs. See /usr/lib64/python2.7/site-packages/lockfile/
    attempts = 0
    while not filelock.i_am_locking():
        try:
            logging.info('Waiting for cache lock...')
            # We must not use a random integer as the filelock implementations
            # may underflow an integer division.
            filelock.acquire(random.uniform(0.0, pow(2.0, attempts)))
            attempts += 1
        except (lockfile.AlreadyLocked, lockfile.LockTimeout):
            # Our goal is to wait long enough to be sure something very bad
            # happened to the locking thread. 11 attempts is between 15 and
            # 30 minutes.
            if attempts > 11:
                # Normally we should aqcuire the lock immediately. Once we
                # wait on the order of 10 minutes either the dev server IO is
                # overloaded or a lock didn't get cleaned up. Take one for the
                # team, break the lock and report a failure. This should fix
                # the lock for following tests. If the failure affects more than
                # one job look for a deadlock or dev server overload.
                logging.error('Permanent lock failure. Trying to break lock.')
                # TODO(ihf): Think how to do this cleaner without having a
                # recursive lock breaking problem. We may have to kill every
                # job that is currently waiting. The main goal though really is
                # to have a cache that does not corrupt. And cache updates
                # only happen once a month or so, everything else are reads.
                filelock.break_lock()
                raise error.TestFail('Error: permanent cache lock failure.')
        else:
            logging.info('Acquired cache lock after %d attempts.', attempts)
    try:
        yield
    finally:
        filelock.release()
        logging.info('Released cache lock.')


@contextlib.contextmanager
def adb_keepalive(target, extra_paths):
    """A context manager that keeps the adb connection alive.

    AdbKeepalive will spin off a new process that will continuously poll for
    adb's connected state, and will attempt to reconnect if it ever goes down.
    This is the only way we can currently recover safely from (intentional)
    reboots.

    @param target: the hostname and port of the DUT.
    @param extra_paths: any additional components to the PATH environment
                        variable.
    """
    from autotest_lib.client.common_lib.cros import adb_keepalive as module
    # |__file__| returns the absolute path of the compiled bytecode of the
    # module. We want to run the original .py file, so we need to change the
    # extension back.
    script_filename = module.__file__.replace('.pyc', '.py')
    job = common_utils.BgJob(
        [script_filename, target],
        nickname='adb_keepalive',
        stderr_level=logging.DEBUG,
        stdout_tee=common_utils.TEE_TO_LOGS,
        stderr_tee=common_utils.TEE_TO_LOGS,
        extra_paths=extra_paths)

    try:
        yield
    finally:
        # The adb_keepalive.py script runs forever until SIGTERM is sent.
        common_utils.nuke_subprocess(job.sp)
        common_utils.join_bg_jobs([job])


@contextlib.contextmanager
def pushd(d):
    """Defines pushd.
    @param d: the directory to change to.
    """
    current = os.getcwd()
    os.chdir(d)
    try:
        yield
    finally:
        os.chdir(current)


def parse_tradefed_result(result, waivers=None):
    """Check the result from the tradefed output.

    @param result: The result stdout string from the tradefed command.
    @param waivers: a set() of tests which are permitted to fail.
    @return 5-tuple (tests, passed, failed, notexecuted, waived)
    """
    # Regular expressions for start/end messages of each test-run chunk.
    abi_re = r'arm\S*|x86\S*'
    # TODO(kinaba): use the current running module name.
    module_re = r'\S+'
    start_re = re.compile(r'(?:Start|Continu)ing (%s) %s with'
                          r' (\d+(?:,\d+)?) test' % (abi_re, module_re))
    end_re = re.compile(r'(%s) %s (?:complet|fail)ed in .*\.'
                        r' (\d+) passed, (\d+) failed, (\d+) not executed' %
                        (abi_re, module_re))

    # Records the result per each ABI.
    total_test = dict()
    total_pass = dict()
    total_fail = dict()
    last_notexec = dict()

    # ABI and the test count for the current chunk.
    abi = None
    ntest = None
    prev_npass = prev_nfail = prev_nnotexec = None

    for line in result.splitlines():
        # Beginning of a chunk of tests.
        match = start_re.search(line)
        if match:
            if abi:
                raise error.TestFail('Error: Unexpected test start: ' + line)
            abi = match.group(1)
            ntest = int(match.group(2).replace(',', ''))
            prev_npass = prev_nfail = prev_nnotexec = None
        else:
            # End of the current chunk.
            match = end_re.search(line)
            if not match:
                continue

            npass, nfail, nnotexec = map(int, match.group(2, 3, 4))
            if abi != match.group(1):
                # When the last case crashed during teardown, tradefed emits two
                # end-messages with possibly increased fail count. Ignore it.
                if (prev_npass == npass and
                    (prev_nfail == nfail or prev_nfail == nfail - 1) and
                        prev_nnotexec == nnotexec):
                    continue
                raise error.TestFail('Error: Unexpected test end: ' + line)
            prev_npass, prev_nfail, prev_nnotexec = npass, nfail, nnotexec

            # When the test crashes too ofen, tradefed seems to finish the
            # iteration by running "0 tests, 0 passed, ...". Do not count
            # that in.
            if ntest > 0:
                total_test[abi] = (
                    total_test.get(abi, 0) + ntest - last_notexec.get(abi, 0))
                total_pass[abi] = total_pass.get(abi, 0) + npass
                total_fail[abi] = total_fail.get(abi, 0) + nfail
                last_notexec[abi] = nnotexec
            abi = None

    if abi:
        # When tradefed crashes badly, it may exit without printing the counts
        # from the last chunk. Regard them as not executed and retry (rather
        # than aborting the test cycle at this point.)
        if ntest > 0:
            total_test[abi] = (
                total_test.get(abi, 0) + ntest - last_notexec.get(abi, 0))
            last_notexec[abi] = ntest
        logging.warning('No result reported for the last chunk. ' +
                        'Assuming all not executed.')

    # TODO(rohitbm): make failure parsing more robust by extracting the list
    # of failing tests instead of searching in the result blob. As well as
    # only parse for waivers for the running ABI.
    waived = 0
    if waivers:
        abis = total_test.keys()
        for testname in waivers:
            # TODO(dhaddock): Find a more robust way to apply waivers.
            fail_count = (
                result.count(testname + ' FAIL') +
                result.count(testname + ' fail'))
            if fail_count:
                if fail_count > len(abis):
                    # This should be an error.TestFail, but unfortunately
                    # tradefed has a bug that emits "fail" twice when a
                    # test failed during teardown. It will anyway causes
                    # a test count inconsistency and visible on the dashboard.
                    logging.error('Found %d failures for %s '
                                  'but there are only %d abis: %s', fail_count,
                                  testname, len(abis), abis)
                waived += fail_count
                logging.info('Waived failure for %s %d time(s)', testname,
                             fail_count)
    counts = tuple(
        sum(count_per_abi.values())
        for count_per_abi in (total_test, total_pass, total_fail,
                              last_notexec)) + (waived,)
    msg = (
        'tests=%d, passed=%d, failed=%d, not_executed=%d, waived=%d' % counts)
    logging.info(msg)
    if counts[2] - waived < 0:
        raise error.TestFail('Error: Internal waiver bookkeeping has '
                             'become inconsistent (%s)' % msg)
    return counts


def select_32bit_java():
    """Switches to 32 bit java if installed (like in lab lxc images) to save
    about 30-40% server/shard memory during the run."""
    if utils.is_in_container() and not client_utils.is_moblab():
        java = '/usr/lib/jvm/java-8-openjdk-i386'
        if os.path.exists(java):
            logging.info('Found 32 bit java, switching to use it.')
            os.environ['JAVA_HOME'] = java
            os.environ['PATH'] = (
                os.path.join(java, 'bin') + os.pathsep + os.environ['PATH'])


class TradefedTest(test.test):
    """Base class to prepare DUT to run tests via tradefed."""
    version = 1

    # Default max_retry based on board and channel.
    _BOARD_RETRY = {}
    _CHANNEL_RETRY = {'dev': 5}

    def _log_java_version(self):
        """Quick sanity and spew of java version installed on the server."""
        utils.run(
            'java',
            args=('-version',),
            ignore_status=False,
            verbose=True,
            stdout_tee=utils.TEE_TO_LOGS,
            stderr_tee=utils.TEE_TO_LOGS)

    def initialize(self,
                   bundle=None,
                   uri=None,
                   host=None,
                   max_retry=None,
                   retry_manual_tests=False,
                   warn_on_test_retry=True):
        """Sets up the tools and binary bundles for the test."""
        logging.info('Hostname: %s', host.hostname)
        self._host = host
        self._max_retry = self._get_max_retry(max_retry, self._host)
        self._install_paths = []
        self._warn_on_test_retry = warn_on_test_retry
        # Tests in the lab run within individual lxc container instances.
        if utils.is_in_container():
            cache_root = _TRADEFED_CACHE_CONTAINER
        else:
            cache_root = _TRADEFED_CACHE_LOCAL

        # TODO(ihf): reevaluate this again when we run out of memory. We could
        # for example use 32 bit java on the first run but not during retries.
        # b/62895114. If select_32bit_java gets deleted for good also remove it
        # from the base image.
        # Try to save server memory (crbug.com/717413).
        # select_32bit_java()

        # The content of the cache survives across jobs.
        self._safe_makedirs(cache_root)
        self._tradefed_cache = os.path.join(cache_root, 'cache')
        self._tradefed_cache_lock = os.path.join(cache_root, 'lock')
        self._tradefed_cache_dirty = os.path.join(cache_root, 'dirty')
        # The content of the install location does not survive across jobs and
        # is isolated (by using a unique path)_against other autotest instances.
        # This is not needed for the lab, but if somebody wants to run multiple
        # TradedefTest instance.
        self._tradefed_install = tempfile.mkdtemp(prefix=_TRADEFED_PREFIX)
        # Under lxc the cache is shared between multiple autotest/tradefed
        # instances. We need to synchronize access to it. All binaries are
        # installed through the (shared) cache into the local (unshared)
        # lxc/autotest instance storage.
        # If clearing the cache it must happen before all downloads.
        self._clean_download_cache_if_needed()
        # Set permissions (rwxr-xr-x) to the executable binaries.
        permission = (
            stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH
            | stat.S_IXOTH)
        self._install_files(_ADB_DIR, _ADB_FILES, permission)
        self._install_files(_SDK_TOOLS_DIR, _SDK_TOOLS_FILES, permission)

        # Install the tradefed bundle.
        bundle_install_path = self._install_bundle(
            uri or self._get_default_bundle_url(bundle))
        self._repository = os.path.join(bundle_install_path,
                                        self._get_tradefed_base_dir())

        # Load expected test failures to exclude them from re-runs.
        self._waivers = self._get_expected_failures('expectations')
        if not retry_manual_tests:
            self._waivers.update(self._get_expected_failures('manual_tests'))

        # Load modules with no tests.
        self._notest_modules = self._get_expected_failures('notest_modules')

    def cleanup(self):
        """Cleans up any dirtied state."""
        # Kill any lingering adb servers.
        self._run('adb', verbose=True, args=('kill-server',))
        logging.info('Cleaning up %s.', self._tradefed_install)
        shutil.rmtree(self._tradefed_install)

    def _login_chrome(self, **cts_helper_kwargs):
        """Returns Chrome log-in context manager.

        Please see also cheets_StartAndroid for details about how this works.
        """
        return _ChromeLogin(self._host, cts_helper_kwargs)

    def _get_adb_target(self):
        return '{}:{}'.format(self._host.hostname, self._host.port)

    def _try_adb_connect(self):
        """Attempts to connect to adb on the DUT.

        @return boolean indicating if adb connected successfully.
        """
        # This may fail return failure due to a race condition in adb connect
        # (b/29370989). If adb is already connected, this command will
        # immediately return success.
        hostport = self._get_adb_target()
        result = self._run(
            'adb', args=('connect', hostport), verbose=True, ignore_status=True)
        logging.info('adb connect {}:\n{}'.format(hostport, result.stdout))
        if result.exit_status != 0:
            return False

        result = self._run('adb', args=('devices',))
        logging.info('adb devices:\n' + result.stdout)
        if not re.search(r'{}\s+(device|unauthorized)'.format(
                re.escape(hostport)), result.stdout):
            return False

        # Actually test the connection with an adb command as there can be
        # a race between detecting the connected device and actually being
        # able to run a commmand with authenticated adb.
        result = self._run('adb', args=('shell', 'exit'), ignore_status=True)
        return result.exit_status == 0

    def _android_shell(self, command):
        """Run a command remotely on the device in an android shell

        This function is strictly for internal use only, as commands do not run
        in a fully consistent Android environment. Prefer adb shell instead.
        """
        self._host.run('android-sh -c ' + pipes.quote(command))

    def _write_android_file(self, filename, data):
        """Writes a file to a location relative to the android container.

        This is an internal function used to bootstrap adb.
        Tests should use adb push to write files.
        """
        android_cmd = 'echo %s > %s' % (pipes.quote(data),
                                        pipes.quote(filename))
        self._android_shell(android_cmd)

    def _connect_adb(self):
        """Sets up ADB connection to the ARC container."""
        logging.info('Setting up adb connection.')
        # Generate and push keys for adb.
        # TODO(elijahtaylor): Extract this code to arc_common and de-duplicate
        # code in arc.py on the client side tests.
        key_path = os.path.join(self.tmpdir, 'test_key')
        pubkey_path = key_path + '.pub'
        self._run('adb', verbose=True, args=('keygen', pipes.quote(key_path)))
        with open(pubkey_path, 'r') as f:
            self._write_android_file(_ANDROID_ADB_KEYS_PATH, f.read())
        self._android_shell('restorecon ' + pipes.quote(_ANDROID_ADB_KEYS_PATH))
        os.environ['ADB_VENDOR_KEYS'] = key_path

        # Kill existing adb server to ensure that the env var is picked up.
        self._run('adb', verbose=True, args=('kill-server',))

        # This starts adbd.
        self._android_shell('setprop sys.usb.config mtp,adb')

        # Also let it be automatically started upon reboot.
        self._android_shell('setprop persist.sys.usb.config mtp,adb')

        # adbd may take some time to come up. Repeatedly try to connect to adb.
        utils.poll_for_condition(
            lambda: self._try_adb_connect(),
            exception=error.TestFail('Error: Failed to set up adb connection'),
            timeout=_ADB_READY_TIMEOUT_SECONDS,
            sleep_interval=_ADB_POLLING_INTERVAL_SECONDS)

        logging.info('Successfully setup adb connection.')

    def _wait_for_arc_boot(self):
        """Wait until ARC is fully booted.

        Tests for the presence of the intent helper app to determine whether ARC
        has finished booting.
        """

        def _intent_helper_running():
            result = self._run(
                'adb',
                args=('shell', 'pgrep', '-f', 'org.chromium.arc.intent_helper'))
            return bool(result.stdout)

        utils.poll_for_condition(
            _intent_helper_running,
            exception=error.TestFail(
                'Error: Timed out waiting for intent helper.'),
            timeout=_ARC_READY_TIMEOUT_SECONDS,
            sleep_interval=_ARC_POLLING_INTERVAL_SECONDS)

    def _disable_adb_install_dialog(self):
        """Disables a dialog shown on adb install execution.

        By default, on adb install execution, "Allow Google to regularly check
        device activity ... " dialog is shown. It requires manual user action
        so that tests are blocked at the point.
        This method disables it.
        """
        logging.info('Disabling the adb install dialog.')
        result = self._run(
            'adb',
            verbose=True,
            args=('shell', 'settings', 'put', 'global',
                  'verifier_verify_adb_installs', '0'))
        logging.info('Disable adb dialog: %s', result.stdout)

    def _ready_arc(self):
        """Ready ARC and adb for running tests via tradefed."""
        self._connect_adb()
        self._disable_adb_install_dialog()
        self._wait_for_arc_boot()

    def _safe_makedirs(self, path):
        """Creates a directory at |path| and its ancestors.

        Unlike os.makedirs(), ignore errors even if directories exist.
        """
        try:
            os.makedirs(path)
        except OSError as e:
            if not (e.errno == errno.EEXIST and os.path.isdir(path)):
                raise

    def _unzip(self, filename):
        """Unzip the file.

        The destination directory name will be the stem of filename.
        E.g., _unzip('foo/bar/baz.zip') will create directory at
        'foo/bar/baz', and then will inflate zip's content under the directory.
        If here is already a directory at the stem, that directory will be used.

        @param filename: Path to the zip archive.
        @return Path to the inflated directory.
        """
        destination = os.path.splitext(filename)[0]
        if os.path.isdir(destination):
            logging.info('Skipping unzip %s, reusing content of %s', filename,
                         destination)
            return destination
        tmp = tempfile.mkdtemp(dir=os.path.dirname(filename))
        logging.info('Begin unzip %s', filename)
        try:
            utils.run('unzip', args=('-d', tmp, filename))
        except:
            logging.error('Failed unzip, cleaning up.')
            # Clean up just created files.
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        logging.info('End unzip %s', filename)
        try:
            os.renames(tmp, destination)
        except:
            logging.error('Failed rename, cleaning up.')
            shutil.rmtree(destination, ignore_errors=True)
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        return destination

    def _dir_size(self, directory):
        """Compute recursive size in bytes of directory."""
        size = 0
        for root, _, files in os.walk(directory):
            for name in files:
                try:
                    size += os.path.getsize(os.path.join(root, name))
                except OSError:
                    logging.error('Inaccessible path (crbug/793696): %s/%s',
                                  root, name)
        return size

    def _invalidate_download_cache(self):
        """Marks the download cache for deferred deletion.

        Used to make cache file operations atomic across failures and reboots.
        The caller is responsible to hold the lock to the cache.
        """
        if not os.path.exists(self._tradefed_cache_dirty):
            os.mkdir(self._tradefed_cache_dirty)

    def _validate_download_cache(self):
        """Validates and unmarks the download cache from deletion.

        Used to make cache file operations atomic across failures and reboots.
        The caller is responsible to hold the lock to the cache.
        """
        shutil.rmtree(self._tradefed_cache_dirty, ignore_errors=True)

    def _clean_download_cache_if_needed(self, force=False):
        """Invalidates cache to prevent it from growing too large."""
        # If the cache is large enough to hold a working set, we can simply
        # delete everything without thrashing.
        # TODO(ihf): Investigate strategies like LRU.
        clean = force
        with lock(self._tradefed_cache_lock):
            size = self._dir_size(self._tradefed_cache)
            if size > _TRADEFED_CACHE_MAX_SIZE:
                logging.info(
                    'Current cache size=%d got too large. Clearing %s.', size,
                    self._tradefed_cache)
                clean = True
            else:
                logging.info('Current cache size=%d of %s.', size,
                             self._tradefed_cache)
            if os.path.exists(self._tradefed_cache_dirty):
                logging.info('Found dirty cache.')
                clean = True
            if clean:
                logging.warning('Cleaning download cache.')
                shutil.rmtree(self._tradefed_cache, ignore_errors=True)
                self._safe_makedirs(self._tradefed_cache)
                shutil.rmtree(self._tradefed_cache_dirty, ignore_errors=True)

    def _download_to_cache(self, uri):
        """Downloads the uri from the storage server.

        It always checks the cache for available binaries first and skips
        download if binaries are already in cache.

        The caller of this function is responsible for holding the cache lock.

        @param uri: The Google Storage or dl.google.com uri.
        @return Path to the downloaded object, name.
        """
        # Split uri into 3 pieces for use by gsutil and also by wget.
        parsed = urlparse.urlparse(uri)
        filename = os.path.basename(parsed.path)
        # We are hashing the uri instead of the binary. This is acceptable, as
        # the uris are supposed to contain version information and an object is
        # not supposed to be changed once created.
        output_dir = os.path.join(self._tradefed_cache,
                                  hashlib.md5(uri).hexdigest())
        output = os.path.join(output_dir, filename)
        # Check for existence of cache entry. We check for directory existence
        # instead of file existence, so that _install_bundle can delete original
        # zip files to save disk space.
        if os.path.exists(output_dir):
            logging.info('Skipping download of %s, reusing content of %s.', uri,
                         output_dir)
            return output

        self._safe_makedirs(output_dir)
        if parsed.scheme not in ['gs', 'http', 'https']:
            raise error.TestFail(
                'Error: Unknown download scheme %s' % parsed.scheme)
        if parsed.scheme in ['http', 'https']:
            logging.info('Using wget to download %s to %s.', uri, output_dir)
            # We are downloading 1 file at a time, hence using -O over -P.
            utils.run(
                'wget',
                args=('--report-speed=bits', '-O', output, uri),
                verbose=True)
            return output

        if not client_utils.is_moblab():
            # If the machine can access to the storage server directly,
            # defer to "gsutil" for downloading.
            logging.info('Host %s not in lab. Downloading %s directly to %s.',
                         self._host.hostname, uri, output)
            # b/17445576: gsutil rsync of individual files is not implemented.
            utils.run('gsutil', args=('cp', uri, output), verbose=True)
            return output

        # We are in the moblab. Because the machine cannot access the storage
        # server directly, use dev server to proxy.
        logging.info('Host %s is in lab. Downloading %s by staging to %s.',
                     self._host.hostname, uri, output)

        dirname = os.path.dirname(parsed.path)
        archive_url = '%s://%s%s' % (parsed.scheme, parsed.netloc, dirname)

        # First, request the devserver to download files into the lab network.
        # TODO(ihf): Switch stage_artifacts to honor rsync. Then we don't have
        # to shuffle files inside of tarballs.
        info = self._host.host_info_store.get()
        ds = dev_server.ImageServer.resolve(info.build)
        ds.stage_artifacts(
            info.build, files=[filename], archive_url=archive_url)

        # Then download files from the dev server.
        # TODO(ihf): use rsync instead of wget. Are there 3 machines involved?
        # Itself, dev_server plus DUT? Or is there just no rsync in moblab?
        ds_src = '/'.join([ds.url(), 'static', dirname, filename])
        logging.info('dev_server URL: %s', ds_src)
        # Calls into DUT to pull uri from dev_server.
        utils.run(
            'wget',
            args=('--report-speed=bits', '-O', output, ds_src),
            verbose=True)
        return output

    def _instance_copyfile(self, cache_path):
        """Makes a copy of a file from the (shared) cache to a wholy owned
        local instance. Also copies one level of cache directoy (MD5 named).
        """
        filename = os.path.basename(cache_path)
        dirname = os.path.basename(os.path.dirname(cache_path))
        instance_dir = os.path.join(self._tradefed_install, dirname)
        # Make sure destination directory is named the same.
        self._safe_makedirs(instance_dir)
        instance_path = os.path.join(instance_dir, filename)
        shutil.copyfile(cache_path, instance_path)
        return instance_path

    def _instance_copytree(self, cache_path):
        """Makes a copy of a directory from the (shared and writable) cache to
        a wholy owned local instance.

        TODO(ihf): Consider using cp -al to only copy links. Not sure if this
        is really a benefit across the container boundary, but it is risky due
        to the possibility of corrupting the original files by an lxc instance.
        """
        # We keep the top 2 names from the cache_path = .../dir1/dir2.
        dir2 = os.path.basename(cache_path)
        dir1 = os.path.basename(os.path.dirname(cache_path))
        instance_path = os.path.join(self._tradefed_install, dir1, dir2)
        logging.info('Copying %s to instance %s', cache_path, instance_path)
        shutil.copytree(cache_path, instance_path)
        return instance_path

    def _install_bundle(self, gs_uri):
        """Downloads a zip file, installs it and returns the local path."""
        if not gs_uri.endswith('.zip'):
            raise error.TestFail('Error: Not a .zip file %s.', gs_uri)
        # Atomic write through of file.
        with lock(self._tradefed_cache_lock):
            # Atomic operations.
            self._invalidate_download_cache()
            # Download is lazy (cache_path may not actually exist if
            # cache_unzipped does).
            cache_path = self._download_to_cache(gs_uri)
            # Unzip is lazy as well (but cache_unzipped guaranteed to
            # exist).
            cache_unzipped = self._unzip(cache_path)
            # To save space we delete the original zip file. This works as
            # _download only checks existence of the cache directory for
            # lazily skipping download, and unzip itself will bail if the
            # unzipped destination exists. Hence we don't need the original
            # anymore.
            if os.path.exists(cache_path):
                logging.info('Deleting original %s', cache_path)
                os.remove(cache_path)
            # Erase dirty marker from disk.
            self._validate_download_cache()
            # We always copy files to give tradefed a clean copy of the
            # bundle.
            unzipped_local = self._instance_copytree(cache_unzipped)
        self._abi = 'x86' if 'x86-x86' in gs_uri else 'arm'
        return unzipped_local

    def _install_files(self, gs_dir, files, permission):
        """Installs binary tools."""
        for filename in files:
            gs_uri = os.path.join(gs_dir, filename)
            # Atomic write through of file.
            with lock(self._tradefed_cache_lock):
                # We don't want to leave a corrupt cache for other jobs.
                self._invalidate_download_cache()
                cache_path = self._download_to_cache(gs_uri)
                # Mark cache as clean again.
                self._validate_download_cache()
                # This only affects the current job, so not part of cache
                # validation.
                local = self._instance_copyfile(cache_path)
            os.chmod(local, permission)
            # Keep track of PATH.
            self._install_paths.append(os.path.dirname(local))

    def _copy_media(self, media):
        """Calls copy_media to push media files to DUT via adb."""
        logging.info('Copying media to device. This can take a few minutes.')
        copy_media = os.path.join(media, 'copy_media.sh')
        with pushd(media):
            try:
                self._run(
                    'file',
                    args=('/bin/sh',),
                    verbose=True,
                    ignore_status=True,
                    timeout=60,
                    stdout_tee=utils.TEE_TO_LOGS,
                    stderr_tee=utils.TEE_TO_LOGS)
                self._run(
                    'sh',
                    args=('--version',),
                    verbose=True,
                    ignore_status=True,
                    timeout=60,
                    stdout_tee=utils.TEE_TO_LOGS,
                    stderr_tee=utils.TEE_TO_LOGS)
            except:
                logging.warning('Could not obtain sh version.')
            self._run(
                'sh',
                args=('-e', copy_media, 'all'),
                timeout=7200,  # Wait at most 2h for download of media files.
                verbose=True,
                ignore_status=False,
                stdout_tee=utils.TEE_TO_LOGS,
                stderr_tee=utils.TEE_TO_LOGS)

    def _verify_media(self, media):
        """Verify that the local media directory matches the DUT.
        Used for debugging b/32978387 where we may see file corruption."""
        # TODO(ihf): Remove function once b/32978387 is resolved.
        # Find all files in the bbb_short and bbb_full directories, md5sum these
        # files and sort by filename, both on the DUT and on the local tree.
        logging.info('Computing md5 of remote media files.')
        remote = self._run(
            'adb',
            args=('shell', 'cd /sdcard/test; '
                  'find ./bbb_short ./bbb_full -type f -print0 | '
                  'xargs -0 md5sum | grep -v "\.DS_Store" | sort -k 2'))
        logging.info('Computing md5 of local media files.')
        local = self._run(
            '/bin/sh',
            args=('-c', (
                'cd %s; find ./bbb_short ./bbb_full -type f -print0 | '
                'xargs -0 md5sum | grep -v "\.DS_Store" | sort -k 2') % media))

        # 'adb shell' terminates lines with CRLF. Normalize before comparing.
        if remote.stdout.replace('\r\n', '\n') != local.stdout:
            logging.error(
                'Some media files differ on DUT /sdcard/test vs. local.')
            logging.info('media=%s', media)
            logging.error('remote=%s', remote)
            logging.error('local=%s', local)
            # TODO(ihf): Return False.
            return True
        logging.info('Media files identical on DUT /sdcard/test vs. local.')
        return True

    def _push_media(self, CTS_URI):
        """Downloads, caches and pushes media files to DUT."""
        media = self._install_bundle(CTS_URI['media'])
        base = os.path.splitext(os.path.basename(CTS_URI['media']))[0]
        cts_media = os.path.join(media, base)
        # TODO(ihf): this really should measure throughput in Bytes/s.
        m = 'chromeos/autotest/infra_benchmark/cheets/push_media/duration'
        fields = {'success': False, 'dut_host_name': self._host.hostname}
        with metrics.SecondsTimer(m, fields=fields) as c:
            self._copy_media(cts_media)
            c['success'] = True
        if not self._verify_media(cts_media):
            raise error.TestFail('Error: saw corruption pushing media files.')

    def _run(self, *args, **kwargs):
        """Executes the given command line.

        To support SDK tools, such as adb or aapt, this adds _install_paths
        to the extra_paths. Before invoking this, ensure _install_files() has
        been called.
        """
        kwargs['extra_paths'] = (
            kwargs.get('extra_paths', []) + self._install_paths)
        return utils.run(*args, **kwargs)

    def _collect_tradefed_global_log(self, result, destination):
        """Collects the tradefed global log.

        @param result: The result object from utils.run.
        @param destination: Autotest result directory (destination of logs).
        """
        match = re.search(r'Saved log to /tmp/(tradefed_global_log_.*\.txt)',
                          result.stdout)
        if not match:
            logging.error('no tradefed_global_log file is found')
            return

        name = match.group(1)
        dest = os.path.join(destination, 'logs', 'tmp')
        self._safe_makedirs(dest)
        shutil.copy(os.path.join('/tmp', name), os.path.join(dest, name))

    def _parse_tradefed_datetime(self, result, summary=None):
        """Get the tradefed provided result ID consisting of a datetime stamp.

        Unfortunately we are unable to tell tradefed where to store the results.
        In the lab we have multiple instances of tradefed running in parallel
        writing results and logs to the same base directory. This function
        finds the identifier which tradefed used during the current run and
        returns it for further processing of result files.

        @param result: The result object from utils.run.
        @param summary: Test result summary from runs so far.
        @return datetime_id: The result ID chosen by tradefed.
                             Example: '2016.07.14_00.34.50'.
        """
        # This string is show for both 'run' and 'continue' after all tests.
        match = re.search(r'(\d\d\d\d.\d\d.\d\d_\d\d.\d\d.\d\d)', result.stdout)
        if not (match and match.group(1)):
            error_msg = 'Error: Test did not complete. (Chrome or ARC crash?)'
            if summary:
                error_msg += (' Test summary from previous runs: %s' % summary)
            raise error.TestFail(error_msg)
        datetime_id = match.group(1)
        logging.info('Tradefed identified results and logs with %s.',
                     datetime_id)
        return datetime_id

    def _parse_result(self, result, waivers=None):
        """Check the result from the tradefed output.

        This extracts the test pass/fail/executed list from the output of
        tradefed. It is up to the caller to handle inconsistencies.

        @param result: The result object from utils.run.
        @param waivers: a set[] of tests which are permitted to fail.
        """
        return parse_tradefed_result(result.stdout, waivers)

    def _collect_logs(self, datetime, destination):
        """Collects the tradefed logs.

        It is legal to collect the same logs multiple times. This is normal
        after 'tradefed continue' updates existing logs with new results.

        @param datetime: The identifier which tradefed assigned to the run.
                         Currently this looks like '2016.07.14_00.34.50'.
        @param destination: Autotest result directory (destination of logs).
        """
        logging.info('Collecting tradefed testResult.xml and logs to %s.',
                     destination)
        repository_results = os.path.join(self._repository, 'results')
        repository_logs = os.path.join(self._repository, 'logs')
        # Because other tools rely on the currently chosen Google storage paths
        # we need to keep destination_results in
        # cheets_CTS.*/results/android-cts/2016.mm.dd_hh.mm.ss(/|.zip)
        # and destination_logs in
        # cheets_CTS.*/results/android-cts/logs/2016.mm.dd_hh.mm.ss/
        destination_results = destination
        destination_results_datetime = os.path.join(destination_results,
                                                    datetime)
        destination_results_datetime_zip = destination_results_datetime + '.zip'
        destination_logs = os.path.join(destination, 'logs')
        destination_logs_datetime = os.path.join(destination_logs, datetime)
        # We may have collected the same logs before, clean old versions.
        if os.path.exists(destination_results_datetime_zip):
            os.remove(destination_results_datetime_zip)
        if os.path.exists(destination_results_datetime):
            shutil.rmtree(destination_results_datetime)
        if os.path.exists(destination_logs_datetime):
            shutil.rmtree(destination_logs_datetime)
        shutil.copytree(
            os.path.join(repository_results, datetime),
            destination_results_datetime)
        # Copying the zip file has to happen after the tree so the destination
        # directory is available.
        shutil.copy(
            os.path.join(repository_results, datetime) + '.zip',
            destination_results_datetime_zip)
        shutil.copytree(
            os.path.join(repository_logs, datetime), destination_logs_datetime)

    def _get_expected_failures(self, *directories):
        """Return a list of expected failures or no test module.

        @param directories: A list of directories with expected no tests
                            or failures files.
        @return: A list of expected failures or no test modules for the current
                 testing device.
        """
        # Load waivers and manual tests so TF doesn't re-run them.
        expected_fail_files = []
        test_board = self._get_board_name(self._host)
        test_arch = self._get_board_arch(self._host)
        for directory in directories:
            expected_fail_dir = os.path.join(self.bindir, directory)
            if os.path.exists(expected_fail_dir):
                expected_fail_files += glob.glob(expected_fail_dir + '/*.yaml')

        waivers = cts_expected_failure_parser.ParseKnownCTSFailures(
            expected_fail_files)
        return waivers.find_waivers(test_board, test_arch)

    def _get_release_channel(self, host):
        """Returns the DUT channel of the image ('dev', 'beta', 'stable')."""
        channel = host.get_channel()
        return channel or 'dev'

    def _get_board_arch(self, host):
        """ Return target DUT arch name."""
        return 'arm' if host.get_cpu_arch() == 'arm' else 'x86'

    def _get_board_name(self, host):
        """Return target DUT board name."""
        return host.get_board().split(':')[1]

    def _get_max_retry(self, max_retry, host):
        """Return the maximum number of retries.

        @param max_retry: max_retry specified in the control file.
        @param host: target DUT for retry adjustment.
        @return: number of retries for this specific host.
        """
        candidate = [max_retry]
        candidate.append(self._get_board_retry(host))
        candidate.append(self._get_channel_retry(host))
        return min(x for x in candidate if x is not None)

    def _get_board_retry(self, host):
        """Return the maximum number of retries for DUT board name.

        @param host: target DUT for retry adjustment.
        @return: number of max_retry for this specific board or None.
        """
        board = self._get_board_name(host)
        if board in self._BOARD_RETRY:
            return self._BOARD_RETRY[board]
        logging.debug('No board retry specified for board: %s', board)
        return None

    def _get_channel_retry(self, host):
        """Returns the maximum number of retries for DUT image channel."""
        channel = self._get_release_channel(host)
        if channel in self._CHANNEL_RETRY:
            return self._CHANNEL_RETRY[channel]
        retry = self._CHANNEL_RETRY['dev']
        logging.warning('Could not establish channel. Using retry=%d.', retry)
        return retry

    def _run_precondition_scripts(self, host, commands, steps):
        for command in commands:
            # Replace {0} (if any) with the retry count.
            formatted_command = command.format(steps)
            logging.info('RUN: %s\n', formatted_command)
            output = host.run(formatted_command, ignore_status=True)
            logging.info('END: %s\n', output)

    def _run_and_parse_tradefed(self, commands):
        """Kick off the tradefed command.

        Assumes that only last entry of |commands| actually runs tests and has
        interesting output (results, logs) for collection. Ignores all other
        commands for this purpose.

        @param commands: List of lists of command tokens.
        @raise TestFail: when a test failure is detected.
        @return: tuple of (tests, pass, fail, notexecuted) counts.
        """
        try:
            output = self._run_tradefed(commands)
        except:
            logging.error('Failed to run tradefed! Cleaning up now.')
            self._log_java_version()
            # In case this happened due to file corruptions, try to force to
            # recreate the cache.
            self._clean_download_cache_if_needed(force=True)
            raise

        result_destination = os.path.join(self.resultsdir,
                                          self._get_tradefed_base_dir())
        # Gather the global log first. Datetime parsing below can abort the test
        # if tradefed startup had failed. Even then the global log is useful.
        self._collect_tradefed_global_log(output, result_destination)
        # Parse stdout to obtain datetime of the session. This is needed to
        # locate result xml files and logs.
        datetime_id = self._parse_tradefed_datetime(output, self.summary)
        # Collect tradefed logs for autotest.
        self._collect_logs(datetime_id, result_destination)
        # Result parsing must come after all other essential operations as test
        # warnings, errors and failures can be raised here.
        return self._parse_result(output, waivers=self._waivers)

    def _clean_repository(self):
        """Ensures all old logs, results and plans are deleted.

        This function should be called at the start of each autotest iteration.
        """
        logging.info('Cleaning up repository.')
        for directory in ['logs', 'subplans', 'results']:
            path = os.path.join(self._repository, directory)
            if os.path.exists(path):
                shutil.rmtree(path)
            self._safe_makedirs(path)

    def _install_plan(self, plan):
        logging.info('Install plan: %s', plan)
        plans_dir = os.path.join(self._repository, 'repository', 'plans')
        src_plan_file = os.path.join(self.bindir, 'plans', '%s.xml' % plan)
        shutil.copy(src_plan_file, plans_dir)

    def _should_skip_test(self):
        """Some tests are expected to fail and are skipped.

        Subclasses should override with specific details.
        """
        return False

    def _should_reboot(self, steps):
        """Oracle to decide if DUT should reboot or just restart Chrome.

        For now we will not reboot after the first two iterations, but on all
        iterations afterward as before. In particular this means that most CTS
        tests will now not get a "clean" machine, but one on which tests ran
        before. But we will still reboot after persistent failures, hopefully
        not causing too many flakes down the line.
        """
        if steps < 3:
            return False
        return True

    def _run_tradefed_list_results(self):
        """Run the `tradefed list results` command.

        @return: tuple of the last (session_id, pass, fail, all_done?).
        """
        output = self._run_tradefed([['list', 'results']])

        # Parses the last session from the output that looks like:
        #
        # Session  Pass  Fail  Modules Complete ...
        # 0        90    10    1 of 2
        # 1        199   1     2 of 2
        # ...
        lastmatch = None
        for m in re.finditer(r'^(\d+)\s+(\d+)\s+(\d+)\s+(\d+) of (\d+)',
                             output.stdout, re.MULTILINE):
            session, passed, failed, done, total = map(int, m.group(1,2,3,4,5))
            lastmatch = (session, passed, failed, done==total)
        return lastmatch

    def _run_tradefed_with_retries(self,
                                   target_module,
                                   test_command,
                                   test_name,
                                   target_plan=None,
                                   needs_push_media=False,
                                   cts_uri=None,
                                   login_precondition_commands=[],
                                   precondition_commands=[]):
        """Run CTS/GTS with retry logic.

        We first kick off the specified module. Then rerun just the failures
        on the next MAX_RETRY iterations.
        """
        if self._should_skip_test():
            logging.warning('Skipped test %s', ' '.join(test_command))
            return

        steps = -1  # For historic reasons the first iteration is not counted.
        pushed_media = False
        self.summary = ''
        board = self._get_board_name(self._host)
        session_id = None

        while steps < self._max_retry:
            steps += 1
            self._run_precondition_scripts(self._host,
                                           login_precondition_commands, steps)
            with self._login_chrome(
                    board=board, reboot=self._should_reboot(steps),
                    dont_override_profile=pushed_media) as current_login:
                self._ready_arc()
                self._run_precondition_scripts(self._host,
                                               precondition_commands, steps)

                # Only push media for tests that need it. b/29371037
                if needs_push_media and not pushed_media:
                    self._push_media(cts_uri)
                    # copy_media.sh is not lazy, but we try to be.
                    pushed_media = True

                # Run tradefed.
                if session_id == None:
                    # Start each valid iteration with a clean repository. This
                    # allows us to track session_id blindly.
                    self._clean_repository()
                    if target_plan is not None:
                        self._install_plan(target_plan)

                    logging.info('Running %s:', test_name)
                    commands = [test_command]
                else:
                    logging.info('Retrying failures of %s with session_id %d:',
                                 test_name, session_id)
                    commands = [test_command + ['--retry', '%d' % session_id]]

                legacy_counts = self._run_and_parse_tradefed(commands)
                result = self._run_tradefed_list_results()
                if not result:
                    logging.error('Did not find any test results. Retry.')
                    current_login.need_reboot()
                    continue

                # TODO(kinaba): stop parsing |legacy_counts| except for waivers,
                # and rely more on |result| for generating the message.
                ltests, lpassed, lfailed, lnotexecuted, lwaived = legacy_counts
                last_session_id, passed, failed, all_done = result

                msg = 'run' if session_id == None else ' retry'
                msg += '(t=%d, p=%d, f=%d, ne=%d, w=%d)' % legacy_counts
                self.summary += msg
                logging.info('RESULT: %s %s', msg, result)

                # Check for no-test modules
                notest = (passed + failed == 0 and all_done)
                if target_module in self._notest_modules:
                    if notest:
                        logging.info('Package has no tests as expected.')
                        return
                    else:
                        # We expected no tests, but the new bundle drop must
                        # have added some for us. Alert us to the situation.
                        raise error.TestFail(
                            'Failed: Remove module %s from '
                            'notest_modules directory!' % target_module)
                elif notest:
                    logging.error('Did not find any tests in module. Hoping '
                                  'this is transient. Retry after reboot.')
                    current_login.need_reboot()
                    continue

                session_id = last_session_id

                # Check if all the tests passed.
                if failed <= lwaived and all_done:
                    # TODO(ihf): Make this error.TestPass('...') once available.
                    if steps > 0 and self._warn_on_test_retry:
                        raise error.TestWarn(
                            'Passed: after %d retries passing %d tests, waived='
                            '%d. %s' % (steps, passed, lwaived, self.summary))
                    return

        if session_id == None:
            raise error.TestFail('Error: Could not find any tests in module.')
        raise error.TestFail(
            'Failed: after %d retries giving up. '
            'passed=%d, failed=%d, notexecuted=%d, waived=%d. %s' %
             (steps, passed, failed, lnotexecuted, lwaived, self.summary))
