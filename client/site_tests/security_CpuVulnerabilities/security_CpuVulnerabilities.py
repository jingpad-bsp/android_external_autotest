# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class security_CpuVulnerabilities(test.test):
    """
    This test ensures that the kernel contains appropriate mitigations against
    CPU vulnerabilities by checking what the kernel reports in
    '/sys/devices/system/cpu/vulnerabilities'.
    """
    version = 1

    SYSTEM_CPU_VULNERABILITIES = '/sys/devices/system/cpu/vulnerabilities'

    TESTS = {
        'amd': {
            'meltdown': ('0', 'Not affected'),
            'spectre_v1': ('0', 'Mitigation: __user pointer sanitization'),
            'spectre_v2': ('0', 'Mitigation: Full AMD retpoline'),
        },
        'arm': {},
        'i386': {},
        'x86_64': {
            'meltdown': ('0', 'Mitigation: PTI'),
            'spectre_v1': ('4.4', 'Mitigation: __user pointer sanitization'),
            'spectre_v2': ('0', 'Mitigation: Full generic retpoline'),
        },
    }


    def run_once(self):
        """Runs the test."""
        arch = utils.get_cpu_arch()
        if arch == 'x86_64':
            arch = utils.get_cpu_soc_family()
        curr_kernel = utils.get_kernel_version()

        logging.debug('CPU arch is "%s"', arch)
        logging.debug('Kernel version is "%s"', curr_kernel)

        if arch not in self.TESTS:
            raise error.TestNAError('"%s" arch not in test baseline' % arch)

        # Kernels <= 3.14 don't have this directory and are expected to abort
        # with TestNA.
        if not os.path.exists(self.SYSTEM_CPU_VULNERABILITIES):
            raise error.TestNAError('"%s" directory not present, not testing' %
                                    self.SYSTEM_CPU_VULNERABILITIES)

        failures = []
        for filename, expected in self.TESTS[arch].items():
            file = os.path.join(self.SYSTEM_CPU_VULNERABILITIES, filename)
            if not os.path.exists(file):
                raise error.TestError('"%s" file does not exist, cannot test' %
                                      file)

            min_kernel = expected[0]
            if utils.compare_versions(curr_kernel, min_kernel) == -1:
                # The kernel on the DUT is older than the version where
                # the mitigation was introduced.
                info_message = 'DUT kernel version "%s"' % curr_kernel
                info_message += ' is older than "%s"' % min_kernel
                info_message += ', skipping "%s" test' % filename
                logging.info(info_message)
                continue

            # E.g.:
            # $ cat /sys/devices/system/cpu/vulnerabilities/meltdown
            # Mitigation: PTI
            with open(file) as f:
                lines = f.readlines()
                if len(lines) > 1:
                    logging.warning('"%s" has more than one line', file)

                actual = lines[0].strip()
                logging.debug('"%s" -> "%s"', file, actual)

                if actual != expected[1]:
                    failures.append((file, actual, expected[1]))

        if failures:
            for failure in failures:
                logging.error('"%s" was "%s", expected "%s"', *failure)
            raise error.TestFail('CPU vulnerabilities not mitigated properly')
