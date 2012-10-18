# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib, logging, os, time, urllib, urllib2

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, wifi_simple_connector


MAX_WAIT_TIME_IN_MSEC = 15 * 60 * 1000


class network_WiFiDownloads(cros_ui_test.UITest):
    version = 1


    def initialize(self):
        base_class = 'chromeos_network.PyNetworkUITest'
        # Switch wifi to be the primary connection
        cros_ui_test.UITest.initialize(self, pyuitest_class=base_class,
                                       creds='$default')


    def start_authserver(self):
        # We want to be able to get to the real internet.
        pass


    def _print_failure_messages_set_state(self, state, message):
        self.job.set_state('client_passed', state)
        logging.debug(message)
        if not state:
            raise error.TestFail(message)


    def run_once(self, ssid=None, ssid_visible=True,
                 wifi_security='SECURITY_NONE', wifi_password=''):
        self.job.set_state('client_passed', False)
        connector = wifi_simple_connector.WifiSimpleConnector(self.pyauto)
        connected = connector.connect_to_wifi_network(ssid=ssid,
            ssid_visible=ssid_visible, wifi_security=wifi_security,
            wifi_password=wifi_password)
        self._DownloadAndVerifyFile('http://172.22.12.253:80/downloads/100M.slf')
        self.job.set_state('client_passed', True)
        logging.debug('Connection establish, client test exiting.')


    def _DownloadAndVerifyFile(self, download_url):
        """Downloads a file at a given URL and validates it.

        This method downloads a file from a server whose filename matches the
        md5 checksum.  Then we manually generate the md5 and check it against
        the filename.

        Args:
           download_url: URL of the file to download.

        Returns:
           The download time in seconds.
        """
        start = time.time()
        # Make a copy of the download directory now to work around segfault
        downloads_dir = self.pyauto.GetDownloadDirectory().value()
        try:
          self.pyauto.DownloadAndWaitForStart(download_url)
        except AssertionError:
          # We need to redo this since the external server may not respond the
          # first time.
          logging.info('Could not start download. Retrying ...')
          self.pyauto.DownloadAndWaitForStart(download_url)
        # Maximum wait time is set as 15 mins as an 100MB file may take
        # somewhere between 8-12 mins to download.
        self.pyauto.WaitForAllDownloadsToComplete(timeout=MAX_WAIT_TIME_IN_MSEC)
        end = time.time()
        logging.info('Download took %2.2f seconds to complete' % (end - start))
        downloaded_files = os.listdir(downloads_dir)
        self.assertEqual(len(downloaded_files), 1,
                         msg='Expected only one file in the Downloads folder. '
                         'but got this: %s' % ', '.join(downloaded_files))
        filename = os.path.splitext(str(downloaded_files[0]))[0]
        file_path = os.path.join(self.pyauto.GetDownloadDirectory().value(),
                                 str(downloaded_files[0]))
        md5_sum = self._Md5Checksum(file_path)
        md5_url = str(download_url[:-4]) + '.md5'  #replacing .slf with .md5
        md5_file = urllib2.urlopen(md5_url).readlines()[0]
        self.assertTrue(md5_file.rstrip().endswith(md5_sum.encode()),
                        msg='Unexpected checksum. The download is incomplete.')
        return end - start


    def _Md5Checksum(self, file_path):
        """Returns the md5 checksum of a file at a given path.

        Args:
          file_path: The complete path of the file to generate the md5
          checksum for.
        """
        file_handle = open(file_path, 'rb')
        m = hashlib.md5()
        while True:
          data = file_handle.read(8192)
          if not data:
            break
          m.update(data)
        file_handle.close()
        return m.hexdigest()
