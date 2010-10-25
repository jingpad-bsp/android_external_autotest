# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This test provides uploading text-based factory log files to a FTP site.
# To add extra information into log, please create a new standalone test
# and output text-safe information via API "factory.log".
# You can find a good example in test factory_LogVpd.

import ftplib
import gzip
import hashlib
import os
import StringIO

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import test, utils
from autotest_lib.client.bin import factory_error as error

class factory_UploadLogs(test.test):
    version = 2

    # Please check suite_Factory/test_list for the more information
    DEFAULT_DESTINATION_PARAM = {
        'method': 'ftp',
        'host': 'localhost',
        'port': ftplib.FTP.port,
        'user': 'anonymous',
        'passwd': '',
        'timeout': 3*60,
        'initdir': '',
        'gzip': True,
        'source_log_path': factory.LOG_PATH,
        'filename_pattern': '%(hash)s.log%(gz)s',
    }

    def prepare_source_object(self, text_source_filename, use_gzip):
        ''' Prepares the source file object from logs '''
        content = open(text_source_filename, 'r').read()
        hashval = hashlib.sha1(content).hexdigest()
        buf = StringIO.StringIO()
        if use_gzip:
            zbuf = gzip.GzipFile(fileobj=buf, mode='w')
            zbuf.write(content)
            zbuf.close()  # force gzip flush to stringIO buffer
        else:
            buf.write(content)
        buf.seek(0)  # prepare for further read
        return hashval, buf

    def do_upload_file(self, dest, fileobj):
        ''' Uploads (via FTP) fileobj to dest '''
        factory.log('upload destination: %s://%s:%s@%s:%s/%s' %
                    (dest['method'], dest['user'],
                     '*',
                     #dest['password'],
                     dest['host'], dest['port'], dest['filename']))

        assert dest['method'] == 'ftp', "only FTP is supported now."
        ftp = ftplib.FTP()
        ftp.connect(host=dest['host'], port=dest['port'],
                    timeout=dest['timeout'])
        ftp.login(user=dest['user'], passwd=dest['passwd'])
        ftp.storbinary('STOR %s' % dest['filename'], fileobj)
        ftp.quit()

    def collect_vpd_values(self):
        ''' Collects VPD properties and return as dictionary '''
        vpd_key_values = {}
        vpd_data = utils.system_output(
                "mosys -l vpd print all", ignore_status=True).strip()
        # The output of mosys VPD is "key | value" format.
        for line in vpd_data.split('\n'):
            if line.find('|') < 0:
                continue
            k, v = line.split('|', 1)
            vpd_key_values['vpd_' + k.strip()] = v.strip()
        return vpd_key_values

    def run_once(self, destination):
        assert 'filename' not in destination, "file names must be generated"
        if destination['host'] == '*':
            factory.log('WARNING: FACTORY LOG UPLOADING IS BYPASSED.')
            return
        dest = {}
        dest.update(self.DEFAULT_DESTINATION_PARAM)
        dest.update(destination)
        src_hash, src_obj = self.prepare_source_object(
                dest['source_log_path'], dest['gzip'])
        filename_params = {
                'gz': '.gz' if dest['gzip'] else '',
                'hash': src_hash, }
        if dest['filename_pattern'].find('%(vpd_') >= 0:
            filename_params.update(self.collect_vpd_values())
        dest_name = dest['filename_pattern'] % filename_params
        dest['filename'] = os.path.join(dest['initdir'], dest_name)
        self.do_upload_file(dest, src_obj)
