#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import os, shutil, re, string
from autotest_lib.client.bin import utils, test

class kernel_fs_Punybench(test.test):
    """
    Run selected puny benchmarks
    """
    version = 1
    Bin = '/usr/local/opt/punybench/bin/'


    def initialize(self):
        self.results = []
        self.job.drop_caches_between_iterations = True


    def run(self, cmd, args):
        return utils.system_output(
            os.path.join(self.Bin, cmd) + ' ' + args)

    def find_max(self, tag, text):
        r1 = re.search(tag + ".*\n(\d.*\n)+", text)
        r2 = re.search(r"(\d+\. \d+\.\d+.*\n)+", r1.group(0))
        runs = string.split(r2.group(0), '\n')
        max = 0.0
        for r in runs:
            a = re.search('\d+.\d+', r)
            if (a):
                b = float(a.group(0))
                if (b > max):
                    max = b
        return max


    def memcpy(self):
        size = '0x4000000'
        loops = '4'
        iterations = '10'
        args  = '-z' + size
        args += ' -i' + iterations
        args += ' -l' + loops
        result = self.run('memcpy', args)

        for tag in ['memcpy', '32bit', '64bit']:
           max = self.find_max(tag, result)
           self.write_perf_keyval({tag: max})


    def memcpy_test(self):
        result = self.run('memcpy_test', "")
        r1 = re.search("L1 cache.*\n.*\n.*", result)
        r2 = re.search("\d+\.\d+ MiB/s$", r1.group())
        self.write_perf_keyval({'L1cache': r2.group()})

        r1 = re.search("L2 cache.*\n.*\n.*", result)
        r2 = re.search("\d+\.\d+ MiB/s$", r1.group(0))
        self.write_perf_keyval({'L2cache': r2.group()})

        r1 = re.search("SDRAM.*\n.*\n.*", result)
        r2 = re.search("\d+\.\d+ MiB/s$", r1.group(0))
        self.write_perf_keyval({'SDRAM': r2.group()})


    def threadtree(self):
        directory = '/usr/local/_Dir'
        iterations = '4'
        tasks = '2'
        width = '3'
        depth = '5'
        args  = '-d' + directory
        args += ' -i' + iterations
        args += ' -t' + tasks
        args += ' -w' + width
        args += ' -k' + depth

        result = self.run('threadtree', args)
        r1 = re.search("timer avg= \d*.\d*.*$", result)
        r2 = re.search("\d*\.\d*", r1.group())
        p = int(tasks) * pow(int(width), int(depth) + 1) / float(r2.group(0))
        self.write_perf_keyval({'threadtree': p})


    def uread(self):
        file = '/usr/local/xyzzy'
        size = '0x200000000'
        loops = '4'
        iterations = '1'
        args = '-f' + file
        args += ' -z' + size
        args += ' -i' + iterations
        args += ' -l' + loops
        args += ' -b12'
        result = self.run('uread', args)

        r1 = re.search("timer avg=\d*.\d*.*$", result)
        r2 = re.search("\d*\.\d*", r1.group(0))
        p = int(size, 0) * int(iterations) / float(r2.group(0)) \
            / 1024.0 / 1024.0
        self.write_perf_keyval({'uread': p})


    def ureadrand(self):
        file = '/usr/local/xyzzy'
        size = '0x200000000'
        loops = '4'
        iterations = '100000'
        args = '-f' + file
        args += ' -z' + size
        args += ' -i' + iterations
        args += ' -l' + loops
        args += ' -b12'
        result = self.run('ureadrand', args)

        r1 = re.search("timer avg=\d*.\d*.*$", result)
        r2 = re.search("\d*\.\d*", r1.group(0))
        p =  4096.0 * int(iterations) / float(r2.group(0)) / 1024.0 / 1024.0
        self.write_perf_keyval({'ureadrand': p})

    def parse_args(self, args):
        """Parse input arguments to this autotest.

        Args:
          args: List of arguments to parse.
        Returns:
          opts: Options, as per optparse.
          args: Non-option arguments, as per optparse.
        """
        parser = optparse.OptionParser()
        parser.add_option('--nomem', dest='want_mem_tests',
                          action='store_false', default=True,
                          help='Skip memory tests.')
        parser.add_option('--nodisk', dest='want_disk_tests',
                          action='store_false', default=True,
                          help='Skip disk tests.')
        # Preprocess the args to remove quotes before/after each one if they
        # exist.  This is necessary because arguments passed via
        # run_remote_tests.sh may be individually quoted, and those quotes must
        # be stripped before they are parsed.
        return parser.parse_args(map(lambda arg: arg.strip('\'\"'), args))

    def run_once(self, args=[]):
        """Run the PyAuto performance tests.

        Args:
          args: Either space-separated arguments or a list of string arguments.
              If this is a space separated string, we'll just call split() on
              it to get a list.  The list will be sent to optparse for parsing.
        """
        if isinstance(args, str):
          args = args.split()
        options, test_args = self.parse_args(args)

        if test_args:
            raise error.TestFail("Unknown args: %s" % repr(test_args))

        if options.want_mem_tests:
            self.memcpy_test()
            self.memcpy()
        if options.want_disk_tests:
            self.threadtree()
            self.uread()
            self.ureadrand()
