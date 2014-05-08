# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, stat, subprocess, utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, login

class logging_LogVolume(cros_ui_test.UITest):
    version = 1


    def log_stateful_used(self):
        output = utils.system_output('df /mnt/stateful_partition/')
        matches = re.search('(\d+)%', output)
        if matches is None:
            error.TestError('df failed')
        self._perf['percent_stateful_used'] = int(matches.group(1))


    def run_once(self, top_patterns=50):
        login.wait_for_cryptohome(self.username)

        self._perf = {}
        self.log_stateful_used()
        whitelist = open(os.path.join(self.bindir,
                                      'stateful_whitelist.txt'))
        patterns = {}
        for pattern in whitelist.readlines():
            pattern = pattern.strip()
            if pattern == '' or pattern[0] == '#':
                continue
            if pattern in patterns:
                logging.error('Duplicate pattern in file: %s' % pattern)
            full_pattern = pattern + '$'
            try:
                patterns[pattern] = {
                    'bytes': 0,
                    'count': 0,
                    'regexp': re.compile(full_pattern),
                    }
            except re.error, e:
                raise error.TestError('Bad regular expression: "%s" Error: %s' %
                                      (full_pattern, e))

        mount_point = '/mnt/stateful_partition'
        find_handle = subprocess.Popen(['find', mount_point],
                                       stdout=subprocess.PIPE)
        stateful_files = 0
        # Count number of files that were found but not whitelisted.
        unexpected_files = 0
        # Count total size of files that were found but not whitelisted.
        unexpected_bytes = 0
        for filename in find_handle.stdout.readlines():
            filename = filename.strip()
            try:
                bytes = os.lstat(filename)[stat.ST_SIZE]
            except OSError, e:
                bytes = 0

            filename = filename[len(mount_point):]
            if filename == '':
                continue
            stateful_files += 1
            match = False
            for pattern in patterns:
                regexp = patterns[pattern]['regexp']
                if regexp.match(filename):
                    match = True
                    patterns[pattern]['bytes'] += bytes
                    patterns[pattern]['count'] += 1
                    break
            if not match:
                logging.warning('Unexpected file %s (%d bytes)' %
                               (filename, bytes))
                unexpected_bytes += bytes
                unexpected_files += 1

        unmatched_patterns = []
        for pattern in patterns:
            if patterns[pattern]['count'] == 0:
                unmatched_patterns.append(pattern)

        unmatched_patterns.sort()
        for pattern in unmatched_patterns:
            logging.warning('No files matched: %s' % pattern)


        if top_patterns:
            largest_size = [(patterns[pattern_]['bytes'], pattern_)
                            for pattern_ in patterns]
            largest_size.sort()
            largest_size.reverse()
            logging.info('Largest %d patterns:', top_patterns)
            for (bytes, pattern) in largest_size:
                top_patterns -= 1
                logging.info('%s (%d bytes)' % (pattern, bytes))
                if top_patterns <= 0:
                    break

        self._perf['bytes_unexpected'] = unexpected_bytes
        self._perf['files_unexpected'] = unexpected_files

        self._perf['files_in_stateful_partition'] = stateful_files

        self._perf['percent_unused_patterns'] = \
            int(100 * len(unmatched_patterns) / len(patterns))

        self.write_perf_keyval(self._perf)
