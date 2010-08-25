# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ftplib
import gzip
import hashlib
import os
import StringIO

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class factory_UploadLogs(test.test):
    version = 1

    DEFAULT_DESTINATION_PARAM = {
        'method': 'ftp',
        'host': 'localhost',
        'port': ftplib.FTP.port,
        'user': 'anonymous',
        'passwd': '',
        'timeout': 3*60,
        'initdir': '',
    }

    USE_GZIP = True

    def prepare_source_object(self, text_source_filename):
        ''' prepares the source file object from logs '''
        content = open(text_source_filename, 'r').read()
        hashval = hashlib.sha1(content).hexdigest()
        if self.USE_GZIP:
            buf = StringIO.StringIO()
            zbuf = gzip.GzipFile(fileobj=buf, mode='w')
            zbuf.write(content)
            zbuf.close()  # force gzip flush to stringIO buffer
        else:
            buf.write(content)
        buf.seek(0)  # prepare for further read
        return hashval, buf

    def do_upload_file(self, dest, fileobj):
        ''' uploads (via FTP) fileobj to dest '''
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

    def run_once(self, destination):
        assert 'filename' not in destination, "file names must be generated"
        if destination['host'] == '*':
            factory.log('WARNING: FACTORY LOG UPLOADING IS BYPASSED.')
            return
        src_hash, src_obj = self.prepare_source_object(factory.LOG_PATH)
        dest = {}
        dest.update(DEFAULT_DESTINATION_PARAM)
        dest.update(destination)
        dest_name = src_hash + '.log'
        if self.USE_GZIP:
            dest_name = dest_name + '.gz'
        dest['filename'] = os.path.join(dest['initdir'], dest_name)
        self.do_upload_file(dest, src_obj)
