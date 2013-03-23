import grp
import logging
import mock_flimflam
import os
import pwd
import stat
import time
import utils

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class network_ShillInitScripts(test.test):
    """ Test that shill init scripts perform as expected.  Use the
        real filesystem (doing a best effort to archive and restore
        current state).  The shill manager is stopped and a proxy
        DBus entity is installed to accept DBus messages that are sent
        via "dbus-send" in the shill startup scripts.  However, the
        "real" shill is still also started from time to time and we
        check that it is run with the right command line arguments.
    """
    version = 1
    save_directories = [ '/var/cache/shill',
                         '/var/cache/flimflam',
                         '/var/run/shill',
                         '/home/chronos/user/shill',
                         '/home/chronos/user/flimflam',
                         '/var/run/state/logged-in',
                         '/var/run/dhcpcd',
                         '/var/lib/dhcpcd',
                         '/home/chronos/.disable_shill' ]
    fake_user = 'not-a-real-user@chromium.org'
    saved_config = '/tmp/network_ShillInitScripts_saved_config.tgz'
    cryptohome_path_command = 'cryptohome-path'
    flimflam_user_profile = '/home/chronos/user/flimflam/flimflam.profile'
    old_shill_user_profile = '/home/chronos/user/shill/shill.profile'
    guest_shill_user_profile_dir = '/var/run/shill/guest_user_profile/shill'
    magic_header = '# --- shill init file test magic header ---'

    def start_shill(self):
        utils.system('start shill')

    def stop_shill(self):
        # Halt the running shill instance.
        utils.system('stop shill', ignore_status=True)

        for attempt in range(10):
            if not self.find_pid('shill'):
                break
            time.sleep(1)
        else:
            error.TestFail('Shill process does not appear to be dying')

    def login(self, user=None):
        # Note: "start" blocks until the "script" block completes.
        utils.system('start login CHROMEOS_USER=%s' % (user or self.fake_user))

    def login_guest(self):
        # For guest login, session-manager passes an empty CHROMEOS_USER arg.
        self.login('""')

    def logout(self):
        # Note: "start" blocks until the "script" block completes.
        utils.system('start logout')

    def start_test(self):
        self.stop_shill()

        # Deduce the cryptohome directory name for our fake user.
        self.cryptohome_dir = utils.system_output(
            '%s system %s' % (self.cryptohome_path_command, self.fake_user))

        # Just in case this hash actually exists, add this to the list of
        # saved directories.
        self.save_directories.append(self.cryptohome_dir)

        # Archive the system state we will be modifying, then remove them.
        utils.system('tar zcvf %s --directory / --ignore-failed-read %s'
                     ' 2>/dev/null' %
                     (self.saved_config, ' '.join(self.save_directories)))
        utils.system('rm -rf %s' % ' '.join(self.save_directories),
                     ignore_status=True)

        # Create the fake user's system cryptohome directory.
        os.mkdir(self.cryptohome_dir)
        self.new_shill_user_profile_dir = ('%s/shill' % self.cryptohome_dir)
        self.new_shill_user_profile = ('%s/shill.profile' %
                                       self.new_shill_user_profile_dir)

        # Start a mock flimflam instance to accept and log DBus calls.
        self.mock_flimflam = mock_flimflam.MockFlimflam()
        self.mock_flimflam.start()

    def erase_state(self):
        utils.system('rm -rf %s' % ' '.join(self.save_directories))
        os.mkdir(self.cryptohome_dir)

    def end_test(self):
        self.mock_flimflam.quit()
        self.mock_flimflam.join()
        self.erase_state()
        utils.system('tar zxvf %s --directory /' % self.saved_config)
        utils.system('rm -f %s' % self.saved_config)
        self.start_shill()

    def assure(self, must_be_true, assertion_name):
        if not must_be_true:
            raise error.TestFail('Assertion failed: %s' % assertion_name)

    def assure_path_owner(self, path, owner):
        self.assure(pwd.getpwuid(os.stat(path).st_uid)[0] == owner,
                    'Path %s is owned by %s' % (path, owner))

    def assure_path_group(self, path, group):
        self.assure(grp.getgrgid(os.stat(path).st_gid)[0] == group,
                    'Path %s is group-owned by %s' % (path, group))

    def assure_exists(self, path, assertion_name):
        self.assure(os.path.exists(path), '%s exists' % assertion_name)

    def assure_is_dir(self, path, assertion_name):
        self.assure_exists(path, assertion_name)
        self.assure(stat.S_ISDIR(os.lstat(path).st_mode),
                    '%s is a directory' % assertion_name)

    def assure_is_link(self, path, assertion_name):
        self.assure_exists(path, assertion_name)
        self.assure(stat.S_ISLNK(os.lstat(path).st_mode),
                    '%s is a symbolic link' % assertion_name)

    def assure_is_link_to(self, path, pointer, assertion_name):
        self.assure_is_link(path, assertion_name)
        self.assure(os.readlink(path) == pointer,
                    '%s is a symbolic link to %s' % (assertion_name, pointer))

    def assure_method_calls(self, expected_method_calls, assertion_name):
        method_calls = self.mock_flimflam.get_method_calls()
        if len(expected_method_calls) != len(method_calls):
            self.assure(False, '%s: method call count does not match' %
                        assertion_name)
        for expected, actual in zip(expected_method_calls, method_calls):
            self.assure(actual.method == expected[0],
                        '%s: method %s matches expected %s' %
                        (assertion_name, actual.method, expected[0]))
            self.assure(actual.argument == expected[1],
                        '%s: argument %s matches expected %s' %
                        (assertion_name, actual.argument, expected[1]))

    def create_file_with_contents(self, filename, contents):
        file(filename, 'w').write(contents)

    def touch(self, filename):
        self.create_file_with_contents(filename, '')

    def create_new_shill_user_profile(self, contents):
        os.mkdir(self.new_shill_user_profile_dir)
        self.create_file_with_contents(self.new_shill_user_profile, contents)

    def create_old_shill_user_profile(self, contents):
        os.mkdir('/home/chronos/user/shill')
        self.create_file_with_contents(self.old_shill_user_profile, contents)

    def create_flimflam_user_profile(self, contents):
        os.mkdir('/home/chronos/user/flimflam')
        self.create_file_with_contents(self.flimflam_user_profile, contents)

    def file_contents(self, filename):
        return file(filename).read()

    def find_pid(self, process_name):
        return utils.system_output('pgrep %s' % process_name,
                                   ignore_status=True).split('\n')

    def get_commandline(self):
        pid = self.find_pid('shill')[0]
        return file('/proc/%s/cmdline' % pid).read().split('\0')

    def run_once(self):
        self.start_test()
        try:
            self.run_tests()
        finally:
            # Stop any shill instances started during testing.
            self.stop_shill()
            self.end_test()

    def run_tests(self):
        for test in (self.test_start_shill,
                     self.test_start_logged_in,
                     self.test_start_port_flimflam_profile,
                     self.test_login,
                     self.test_login_guest,
                     self.test_login_profile_exists,
                     self.test_login_old_shill_profile,
                     self.test_login_invalid_old_shill_profile,
                     self.test_login_ignore_old_shill_profile,
                     self.test_login_flimflam_profile,
                     self.test_login_ignore_flimflam_profile,
                     self.test_login_prefer_old_shill_profile,
                     self.test_login_multi_profile,
                     self.test_logout):
          test()
          self.stop_shill()
          self.erase_state()

    def test_start_shill(self):
        """ Test all created pathnames during shill startup.  Ensure the
            push argument is not provided by default.
        """
        self.touch('/home/chronos/.disable_shill')
        self.start_shill()
        self.assure_is_dir('/var/run/shill', 'Shill run directory')
        self.assure_is_dir('/var/lib/dhcpcd', 'dhcpcd lib directory')
        self.assure_path_owner('/var/lib/dhcpcd', 'dhcp')
        self.assure_path_group('/var/lib/dhcpcd', 'dhcp')
        self.assure_is_dir('/var/run/dhcpcd', 'dhcpcd run directory')
        self.assure_path_owner('/var/run/dhcpcd', 'dhcp')
        self.assure_path_group('/var/run/dhcpcd', 'dhcp')
        self.assure(not os.path.exists('/home/chronos/.disable_shill'),
                    'Shill disable file does not exist')
        self.assure('--push=~chronos/shill' not in self.get_commandline(),
                    'Shill command line does not contain push argument')

    def test_start_logged_in(self):
        """ The "--push" argument should be added if the shill is started
            while a user is logged in.
        """
        os.mkdir('/var/run/shill')
        os.mkdir('/var/run/shill/user_profiles')
        self.create_new_shill_user_profile('')
        os.symlink(self.new_shill_user_profile_dir,
                   '/var/run/shill/user_profiles/chronos')
        self.touch('/var/run/state/logged-in')
        self.start_shill()
        command_line = self.get_commandline()
        self.assure('--push=~chronos/shill' in command_line,
                    'Shill command line contains push argument: %s' %
                    repr(command_line))
        os.unlink('/var/run/state/logged-in')

    def test_start_port_flimflam_profile(self):
        """ Startup should move an old flimflam profile into place if
            a shill profile does not already exist.
        """
        os.mkdir('/var/cache/flimflam')
        flimflam_profile = '/var/cache/flimflam/default.profile'
        self.create_file_with_contents(flimflam_profile, self.magic_header)
        shill_profile = '/var/cache/shill/default.profile'
        self.start_shill()
        self.assure(not os.path.exists(flimflam_profile),
                    'Flimflam profile no longer exists')
        self.assure(os.path.exists(shill_profile),
                    'Shill profile exists')
        self.assure(self.magic_header in self.file_contents(shill_profile),
                    'Shill default profile contains our magic header')

    def test_start_ignore_flimflam_profile(self):
        """ Startup should ignore an old flimflam profile if a shill profile
            already exists.
        """
        os.mkdir('/var/cache/flimflam')
        os.mkdir('/var/cache/shill')
        flimflam_profile = '/var/cache/flimflam/default.profile'
        self.create_file_with_contents(flimflam_profile, self.magic_header)
        shill_profile = '/var/cache/shill/default.profile'
        self.touch(shill_profile)
        self.start_shill()
        self.assure(os.path.exists(flimflam_profile),
                    'Flimflam profile still exists')
        self.assure(self.magic_header not in self.file_contents(shill_profile),
                    'Shill default profile does not contain our magic header')

    def test_login(self):
        """ Login should create a profile directory, then create and push
            a user profile, given no previous state.
        """
        os.mkdir('/var/run/shill')
        self.login()
        self.assure(not os.path.exists(self.flimflam_user_profile),
                    'Flimflam user profile does not exist')
        self.assure(not os.path.exists(self.old_shill_user_profile),
                    'Old shill user profile does not exist')
        self.assure(not os.path.exists(self.new_shill_user_profile),
                    'New shill user profile does not exist')
        # The DBus "CreateProfile" method should have been handled
        # by our mock_flimflam instance, so the profile directory
        # should not have actually been created.
        self.assure_is_dir(self.new_shill_user_profile_dir,
                           'New shill user profile directory')
        self.assure_is_dir('/var/run/shill/user_profiles',
                           'Shill profile root')
        self.assure_is_link_to('/var/run/shill/user_profiles/chronos',
                               self.new_shill_user_profile_dir,
                               'Shill profile link')
        self.assure_method_calls([[ 'CreateProfile', '~chronos/shill' ],
                                  [ 'PushProfile', '~chronos/shill' ]],
                                 'CreateProfile and PushProfile are called')

    def test_login_guest(self):
        """ Login should create a temporary profile directory in /var/run,
            instead of using one within the root directory for normal users.
        """
        os.mkdir('/var/run/shill')
        self.login_guest()
        self.assure(not os.path.exists(self.flimflam_user_profile),
                    'Flimflam user profile does not exist')
        self.assure(not os.path.exists(self.old_shill_user_profile),
                    'Old shill user profile does not exist')
        self.assure(not os.path.exists(self.new_shill_user_profile),
                    'New shill user profile does not exist')
        self.assure(not os.path.exists(self.new_shill_user_profile_dir),
                    'New shill user profile directory')
        self.assure_is_dir(self.guest_shill_user_profile_dir,
                           'shill guest user profile directory')
        self.assure_is_dir('/var/run/shill/user_profiles',
                           'Shill profile root')
        self.assure_is_link_to('/var/run/shill/user_profiles/chronos',
                               self.guest_shill_user_profile_dir,
                               'Shill profile link')
        self.assure_method_calls([[ 'CreateProfile', '~chronos/shill' ],
                                  [ 'PushProfile', '~chronos/shill' ]],
                                 'CreateProfile and PushProfile are called')

    def test_login_profile_exists(self):
        """ Login script should only push (and not create) the user profile
            if a user profile already exists.
        """
        os.mkdir('/var/run/shill')
        os.mkdir(self.new_shill_user_profile_dir)
        self.touch(self.new_shill_user_profile)
        self.login()
        self.assure_method_calls([[ 'PushProfile', '~chronos/shill' ]],
                                 'Only PushProfile is called')

    def test_login_old_shill_profile(self):
        """ Login script should move an old shill user profile into place
            if a new one does not exist.
        """
        os.mkdir('/var/run/shill')
        self.create_old_shill_user_profile(self.magic_header)
        self.login()
        self.assure(not os.path.exists(self.old_shill_user_profile),
                    'Old shill user profile no longer exists')
        self.assure(not os.path.exists('/home/chronos/user/shill'),
                    'Old shill user profile directory no longer exists')
        self.assure_exists(self.new_shill_user_profile,
                           'New shill profile')
        self.assure(self.magic_header in
                    self.file_contents(self.new_shill_user_profile),
                    'Shill user profile contains our magic header')
        self.assure_method_calls([[ 'PushProfile', '~chronos/shill' ]],
                                 'Only PushProfile is called')

    def make_symlink(self, path):
        os.symlink('/etc/hosts', path)

    def make_special_file(self, path):
        os.mknod(path, stat.S_IFIFO)

    def make_bad_owner(self, path):
        self.touch(path)
        os.lchown(path, 1000, 1000)

    def test_login_invalid_old_shill_profile(self):
        """ Login script should ignore non-regular files or files not owned
            by the correct user.  The original file should be removed.
        """
        os.mkdir('/var/run/shill')
        for file_creation_method in (self.make_symlink,
                                     self.make_special_file,
                                     os.mkdir,
                                     self.make_bad_owner):
            os.mkdir('/home/chronos/user/shill')
            file_creation_method(self.old_shill_user_profile)
            self.login()
            self.assure(not os.path.exists(self.old_shill_user_profile),
                        'Old shill user profile no longer exists')
            self.assure(not os.path.exists('/home/chronos/user/shill'),
                        'Old shill user profile directory no longer exists')
            self.assure(not os.path.exists(self.new_shill_user_profile),
                        'New shill profile was not created')
            self.assure_method_calls([[ 'CreateProfile', '~chronos/shill' ],
                                      [ 'PushProfile', '~chronos/shill' ]],
                                     'CreateProfile and PushProfile are called')
            os.unlink('/var/run/shill/user_profiles/chronos')

    def test_login_ignore_old_shill_profile(self):
        """ Login script should ignore an old shill user profile if a new one
            exists.
        """
        os.mkdir('/var/run/shill')
        self.create_new_shill_user_profile('')
        self.create_old_shill_user_profile(self.magic_header)
        self.login()
        self.assure(os.path.exists(self.old_shill_user_profile),
                    'Old shill user profile still exists')
        self.assure_exists(self.new_shill_user_profile,
                           'New shill profile')
        self.assure(self.magic_header not in
                    self.file_contents(self.new_shill_user_profile),
                    'Shill user profile does not contain our magic header')
        self.assure_method_calls([[ 'PushProfile', '~chronos/shill' ]],
                                 'Only PushProfile is called')

    def test_login_flimflam_profile(self):
        """ Login script should move a flimflam user profile into place
            if a shill one does not exist.
        """
        os.mkdir('/var/run/shill')
        self.create_flimflam_user_profile(self.magic_header)
        self.login()
        self.assure(not os.path.exists(self.flimflam_user_profile),
                    'Flimflam user profile no longer exists')
        self.assure(not os.path.exists('/home/chronos/user/flimflam'),
                    'Flimflam user profile directory no longer exists')
        self.assure_exists(self.new_shill_user_profile,
                           'New shill profile')
        self.assure(self.magic_header in
                    self.file_contents(self.new_shill_user_profile),
                    'Shill user profile contains our magic header')
        self.assure_method_calls([[ 'PushProfile', '~chronos/shill' ]],
                                 'Only PushProfile is called')

    def test_login_ignore_flimflam_profile(self):
        """ Login script should ignore an old flimflam user profile if a new
            one exists.
        """
        os.mkdir('/var/run/shill')
        self.create_flimflam_user_profile(self.magic_header)
        self.create_new_shill_user_profile('')
        self.login()
        self.assure_exists(self.new_shill_user_profile,
                           'New shill profile')
        self.assure(self.magic_header not in
                    self.file_contents(self.new_shill_user_profile),
                    'Shill user profile does not contain our magic header')
        self.assure_method_calls([[ 'PushProfile', '~chronos/shill' ]],
                                 'Only PushProfile is called')

    def test_login_prefer_old_shill_profile(self):
        """ Login script should use the old shill user profile in preference
            to a flimflam user profile if the new user profile does not
            exist.
        """
        os.mkdir('/var/run/shill')
        self.create_flimflam_user_profile('')
        self.create_old_shill_user_profile(self.magic_header)
        self.login()
        self.assure(not os.path.exists(self.flimflam_user_profile),
                    'Flimflam user profile was removed')
        self.assure(not os.path.exists(self.old_shill_user_profile),
                    'Old shill user profile no longer exists')
        self.assure_exists(self.new_shill_user_profile,
                           'New shill profile')
        self.assure(self.magic_header in
                    self.file_contents(self.new_shill_user_profile),
                    'Shill user profile contains our magic header')
        self.assure_method_calls([[ 'PushProfile', '~chronos/shill' ]],
                                 'Only PushProfile is called')

    def test_login_multi_profile(self):
        """ Login script should create multiple profiles in parallel
            if called more than once without an intervening logout. If
            shill is started while all these profiles are present, each
            of these should be listed in the '--push' command-line
            argument to shill.
        """
        os.mkdir('/var/run/shill')
        self.create_new_shill_user_profile('')
        expected_usernames = [ 'chronos', 'user001', 'user002', 'user003' ]
        created_profiles = []
        for username in expected_usernames:
            self.login()
            profile = "~%s/shill" % username
            self.assure_method_calls([[ 'PushProfile', profile ]],
                                     'PushProfile is called for %s' % profile)
            self.assure_is_link_to('/var/run/shill/user_profiles/%s' % username,
                                   self.new_shill_user_profile_dir,
                                   'Shill profile link for %s' % username)
            created_profiles.append(profile)

        # Start up shill with the data from all the user profiles above
        # in place.  Shill should be started with instructions to push
        # each of these profiles.
        self.touch('/var/run/state/logged-in')
        self.start_shill()
        command_line = self.get_commandline()
        push_argument = '--push=%s' % ','.join(created_profiles)
        self.assure(push_argument in command_line,
                    'Shill command line contains push argument: %s' %
                    repr(command_line))

    def test_logout(self):
        os.makedirs('/var/run/shill/user_profiles')
        os.makedirs(self.guest_shill_user_profile_dir)
        self.touch('/var/run/state/logged-in')
        self.logout()
        self.assure(not os.path.exists('/var/run/state/logged-in'),
                    'Logged-in file was removed')
        self.assure(not os.path.exists('/var/run/shill/user_profiles'),
                    'User profile directory was removed')
        self.assure(not os.path.exists(self.guest_shill_user_profile_dir),
                    'Guest user profile directory was removed')
        self.assure_method_calls([[ 'PopAllUserProfiles', '' ]],
                                 'PopAllUserProfiles is called')
