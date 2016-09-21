# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os
import sys

import common
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.server import adb_utils
from autotest_lib.server import afe_utils
from autotest_lib.server import constants
from autotest_lib.server import test
from autotest_lib.server.cros import dnsname_mangler
from autotest_lib.site_utils import sponge_utils

CONFIG_FOLDER_LOCATION = global_config.global_config.get_config_value(
        'ACTS', 'acts_config_folder', default='')

TEST_CONFIG_FILE_FOLDER = os.path.join(CONFIG_FOLDER_LOCATION,
        'autotest_config')
TEST_CAMPAIGN_FILE_FOLDER = os.path.join(CONFIG_FOLDER_LOCATION,
        'autotest_campaign')

DEFAULT_TEST_RELATIVE_LOG_PATH = 'results/logs'


class android_ACTS(test.test):
    """Run an Android CTS test case.

    Component relationship:
    Workstation ----(ssh)---> TestStation -----(adb)-----> Android DUT
    This code runs on Workstation.
    """
    version = 1
    acts_result_to_autotest = {
        'PASS': 'GOOD',
        'FAIL': 'FAIL',
        'UNKNOWN': 'WARN',
        'SKIP': 'ABORT'
    }

    def push_file_to_teststation(self,
                                 filename,
                                 input_path=None,
                                 output_path=None):
        """Ensures the file specified by a path exists on test station. If the
        file specified by input_path does not exist, attempt to locate it in
        ACTS dirctory.

        @param filename: The name of the file relative to both the input and output
                         path.
        @param input_path: The base path on the drone to get the file
                           from. If none, then the folder in the filename
                           is used.
        @param output_path: The base path on the test station to put the file.
                            By default this is the temp folder.

        @returns: The full path on the test station.
        """
        logging.debug('Starting push for %s.', filename)

        if not input_path:
            input_path = os.path.dirname(os.path.abspath(filename))

        if not output_path:
            output_path = os.path.join(self.ts_tempfolder, 'configs')

        # Find the path on the source machine
        full_input_path = os.path.abspath(input_path)
        if not os.path.exists(full_input_path):
            raise error.TestError('Invalid input path given %s' % input_path)
        full_src_file = os.path.join(full_input_path, filename)
        if not os.path.exists(full_src_file):
            raise error.TestError(
                    'Invalid filename, no full path %s exists' % full_src_file)

        # Find the directory part of the file
        file_dir = os.path.dirname(filename)

        # Find the path on the test station
        dst_dir = os.path.join(output_path, file_dir)

        logging.info('Pushing file %s to %s.', full_src_file, dst_dir)

        self.test_station.send_file(full_src_file, dst_dir)
        return os.path.join(output_path, filename)

    def install_sl4a_apk(self):
        """Installs sl4a on all phones connected to the testbed."""
        for serial, adb_host in self.testbed.get_adb_devices().iteritems():
            adb_utils.install_apk_from_build(
                    adb_host,
                    constants.SL4A_APK,
                    constants.SL4A_PACKAGE,
                    package_name=constants.SL4A_PACKAGE)

    def download_acts(self, download_locaiton=None):
        """Downloads acts onto a test station.

        Pulls down acts.zip from from devserver and unzips it into the temp
        directory for this test.

        @param download_locaiton: The directory on the test station to download
                                  acts into.

        @returns: The base directory for acts.
        """
        if not download_locaiton:
            download_locaiton = self.ts_tempfolder

        host = next(v for v in self.testbed.get_adb_devices().values())

        if not host:
            raise error.TestError(
                    'No hosts defined for this test, cannot'
                    ' determine build to grab artifact from.')

        job_repo_url = afe_utils.get_host_attribute(
                host, host.job_repo_url_attribute)
        if not job_repo_url:
            raise error.TestError('No job repo url defined for this DUT.')

        logging.info('Pulling acts from artifact, url: %s.', job_repo_url)

        devserver_url = dev_server.AndroidBuildServer.get_server_url(
                job_repo_url)
        devserver = dev_server.AndroidBuildServer(devserver_url)
        build_info = host.get_build_info_from_build_url(job_repo_url)

        devserver.trigger_download(
                build_info['target'],
                build_info['build_id'],
                build_info['branch'],
                files='acts.zip',
                synchronous=True)

        temp_dir = download_locaiton

        download_dir = '%s/acts' % temp_dir

        logging.info('Downloading from dev server %s to %s',
                     job_repo_url,
                     download_dir)

        host.download_file(
                build_url=job_repo_url,
                file='acts.zip',
                dest_dir=temp_dir,
                unzip=True,
                unzip_dest=download_dir)

        base_acts_dir = os.path.join(
                download_dir, 'tools/test/connectivity/acts')


        logging.info('ACTs downloaded to %s on test station', base_acts_dir)

        return base_acts_dir

    def setup_configs(self,
                      config_file,
                      additional_configs=[],
                      configs_local_location=None,
                      configs_remote_location=None):
        """Setup config files on the test station.

        Takes configuration files and uploads them onto the tests station.
        Then does any additional setup that is needed.

        @param config_file: The main config for acts to use.
        @param additional_configs: An additional set of config files to send.
        @param configs_local_location: Where on the drone are config files
                                       being found. If none then the default
                                       location defined in the autotest
                                       configs is used.
        @param configs_remote_location: The directory to store configs in,
                                        by default it is a sub folder of the
                                        temp folder.

        @returns A list of locations on the test station where the configs where
                 uploaded. The first element is always the main config.
        """
        if not configs_local_location:
            configs_local_location = TEST_CONFIG_FILE_FOLDER

        if not configs_remote_location:
            configs_remote_location = os.path.join(
                    self.ts_tempfolder,
                    'configs')

        if not config_file:
            raise error.TestFail('A config file must be specified.')

        logging.info('Pulling configs from %s.', configs_local_location)

        remote_config_file = self.push_file_to_teststation(
                config_file,
                input_path=configs_local_location,
                output_path=configs_remote_location)

        remote_configs = [remote_config_file]

        for additional_config in additional_configs:
            remote_location = self.push_file_to_teststation(
                    additional_config,
                    input_path=configs_local_location,
                    output_path=configs_remote_location)

            remote_configs.append(remote_location)

        return remote_configs

    def setup_campaign(self,
                       campaign_file,
                       campaign_local_location=None,
                       campagin_remote_location = None):
        """Sets up campaign files on a test station.

        Will take a local campaign file and upload it to the test station.

        @param campaign_file: The name of the campaign file.
        @param campaign_local_location: The local directory the campaign file
                                        is in.
        @param campagin_remote_location: The remote directory to place the
                                         campaign file in.

        @returns The remote path to the campaign file.
        """
        if not campaign_local_location:
            campaign_local_location = TEST_CAMPAIGN_FILE_FOLDER

        if not campagin_remote_location:
            campagin_remote_location = os.path.join(self.ts_tempfolder,
                                                    'campaigns')

        logging.info('Pulling campaign from %s.', campaign_local_location)

        remote_campaign_file = self.push_file_to_teststation(
                campaign_file,
                input_path=campaign_local_location,
                output_path=campagin_remote_location)

        return remote_campaign_file


    def build_environment(self, base_acts_dir=None, log_path=None):
        """Builds the environment variables for a run.

        @param base_acts_dir: Where acts is stored. If none then the default
                              acts download location is used.
        @param log_path: The path to the log file. If none then a log folder
                         under the temp folder is used.

        @returns: The enviroment variables as a dictionary.
        """
        if not log_path:
            log_path = '%s/%s' % (
                    self.ts_tempfolder,
                    DEFAULT_TEST_RELATIVE_LOG_PATH)

        if not base_acts_dir:
            base_acts_dir = self.acts_download_dir

        framework_dir = os.path.join(base_acts_dir, 'framework')
        base_test_dir = os.path.join(base_acts_dir, 'tests')

        get_test_paths_result = self.test_station.run(
                'find %s -type d' % base_test_dir)
        test_search_dirs = get_test_paths_result.stdout.splitlines()

        get_path_result = self.test_station.run('echo $PYTHONPATH')
        remote_path = get_path_result.stdout
        new_python_path = '%s:%s' % (remote_path, framework_dir)

        env = {'ACTS_TESTPATHS': ':'.join(test_search_dirs),
               'ACTS_LOGPATH': log_path,
               'PYTHONPATH': new_python_path}

        logging.info('Enviroment set to: %s', str(env))

        return env

    def run_acts(self,
                 remote_config_file,
                 testing_working_dir=None,
                 remote_acts_file='framework/acts/bin/act.py',
                 test_file=None,
                 test_case=None,
                 env={},
                 testbed_name=None,
                 timeout=7200):
        """Runs ACTs on the test station.

        Runs a test on on the test station and handles logging any details
        about it during runtime.

        @param remote_config_file: The config file on the test station to use.
        @param testing_working_dir: The working directory to run acts from.
                                    By default the acts download location is
                                    used.
        @param remote_acts_file: The acts file to use relative from the wokring
                                 directory.
        @param test_file: The -tf argument for acts.
        @param test_case: The tc argument for acts.
        @param env: The enviroment variables to use with acts.
        @param testbed_name: The name of the test bed to use, if None then the
                             default testbed name for the test is used.
        @param timeout: How long to wait for acts.
        """
        if not testbed_name:
            testbed_name = self.testbed_name

        if not testing_working_dir:
            testing_working_dir = self.acts_download_dir

        exports = []
        for key, value in env.items():
            exports.append('export %s="%s"' % (key, str(value)))
        env_setup = '; '.join(exports)

        command_setup = 'cd %s' % testing_working_dir
        act_base_cmd = 'python %s -c %s -tb %s ' % (
                remote_acts_file, remote_config_file, testbed_name)

        if test_case and test_file:
            raise ValueError(
                    'test_case and test_file cannot both have a value.')
        elif test_case:
            act_cmd = '%s -tc %s' % (act_base_cmd, test_case)
        elif test_file:
            full_test_file = self.setup_campaign(test_file)
            act_cmd = '%s -tf %s' % (act_base_cmd, full_test_file)
        else:
            raise error.TestFail('No tests was specified!')

        command_list = [command_setup, env_setup, act_cmd]
        full_command = '; '.join(command_list)

        try:
            logging.debug('Running: %s', full_command)
            act_result = self.test_station.run(full_command, timeout=timeout)
            logging.debug('ACTS Output:\n%s', act_result.stdout)
        except:
            raise error.TestError('Unexpected error: %s', sys.exc_info())

    def post_act_cmd(self, test_case=None, test_file=None, log_path=None):
        """Actions to take after act_cmd is finished or failed.

        Actions include collect logs from test station generated by act_cmd
        and record job results based on `test_run_summary.json`.
        @param test_case: A string that's passed to act.py's -tc option.
        @param test_file: A string that's passed to act.py's -tf option.

        @param log_path: The path to where the log output.
        """
        logging.info('Running cleanup.')
        if not log_path:
            log_path = os.path.join(
                    self.ts_tempfolder,
                    DEFAULT_TEST_RELATIVE_LOG_PATH)

        testbed_log_path = os.path.join(log_path, self.testbed_name, 'latest')

        # Following call may fail if logs are not generated by act_cmd yet.
        # Anyhow, the test must have failed already in that case.
        self.test_station.get_file(testbed_log_path, self.resultsdir)
        # Load summary json file.
        summary_path = os.path.join(
                self.resultsdir, 'latest', 'test_run_summary.json')
        # If the test has failed, test_run_summary.json may not exist.
        if os.path.exists(summary_path):
            sponge_utils.upload_results_in_test(
                    self, acts_summary=summary_path)
            with open(summary_path, 'r') as f:
                results = json.load(f)['Results']
            # Report results to Autotest.
            for result in results:
                verdict = self.acts_result_to_autotest[result['Result']]
                details = result['Details']
                self.job.record(
                        verdict,
                        None,
                        test_case or test_file,
                        status=(details or ''))
        else:
            logging.debug('summary at path %s does not exist!', summary_path)

    def run_once(self,
                 testbed=None,
                 config_file=None,
                 testbed_name=None,
                 test_case=None,
                 test_file=None,
                 additional_configs=[],
                 acts_timeout=7200):
        """Run ACTS on the DUT.

        Exactly one of test_case and test_file should be provided.

        @param testbed: Testbed representing the testbed under test. Required.
        @param config_file: Path to config file locally. Required.
        @param testbed_name: A string that's passed to act.py's -tb option.
                             If testbed_name is not provided, set it to the
                             testbed's hostname without the DNS zone.
        @param test_case: A string that's passed to act.py's -tc option.
        @param test_file: A string that's passed to act.py's -tf option.
        @param additional_configs: A list of paths to be copied over to
                                   the test station. These files must reside
                                   in the TEST_CONFIG_FILE_FOLDER.
        @param acts_timeout: A timeout for the specific ACTS test.
        """
        # setup properties
        self.testbed = testbed
        if not testbed_name:
            hostname = testbed.hostname
            if dnsname_mangler.is_ip_address(hostname):
                self.testbed_name = hostname
            else:
                self.testbed_name = hostname.split('.')[0]
        else:
            self.testbed_name = testbed_name
        self.test_station = testbed.teststation
        self.ts_tempfolder = self.test_station.get_tmp_dir()

        # install all needed tools
        self.install_sl4a_apk()
        self.acts_download_dir = self.download_acts()
        remote_config_file = self.setup_configs(
                config_file, additional_configs)
        env = self.build_environment()

        exception = None
        try:
            # launch acts
            self.run_acts(
                    remote_config_file[0],
                    test_file=test_file,
                    test_case=test_case,
                    env=env,
                    timeout=acts_timeout)
        except Exception, e:
            logging.error('Unexpected error: %s', sys.exc_info())
            exception = e

        # cleanup
        self.post_act_cmd(test_case=test_case, test_file=test_file)

        if exception:
            raise exception
