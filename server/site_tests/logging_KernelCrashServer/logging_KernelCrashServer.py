# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, shutil, time
from autotest_lib.client.common_lib import error
from autotest_lib.server import autotest, site_host_attributes, test

_CONSENT_FILE = '/home/chronos/Consent To Send Stats'
_STOWED_CONSENT_FILE = '/var/lib/kernel-crash-server.consent'


class logging_KernelCrashServer(test.test):
    version = 1


    def _exact_copy(self, source, dest):
        """Copy remote source to dest, where dest removed if src not present."""
        self._host.run('rm -f "%s"; cp "%s" "%s" 2>/dev/null; true' %
                       (dest, source, dest))


    def cleanup(self):
        self._exact_copy(_STOWED_CONSENT_FILE, _CONSENT_FILE)
        test.test.cleanup(self)


    def _can_disable_consent(self):
        """Returns whether or not host can have consent disabled.

        Presence of /etc/send_metrics causes ui.conf job (which starts
        after chromeos_startup) to regenerate a consent file if one
        does not exist.  Therefore, we cannot guarantee that
        crash-reporter.conf will start with the file gone if we
        removed it before causing a crash.
        """
        status = self._host.run('[ -r /etc/send_metrics ]', ignore_status=True)
        return status.exit_status != 0


    def _crash_it(self, consent):
        """Crash the host after setting the consent as given."""
        if consent:
            self._host.run('echo test-consent > "%s"' % _CONSENT_FILE)
        else:
            self._host.run('rm -f "%s"' % _CONSENT_FILE)
        logging.info('KernelCrashServer: crashing %s' % self._host.hostname)
        boot_id = self._host.get_boot_id()
        self._host.run(
            'sh -c "sync; sleep 1; echo bug > /proc/breakme" >/dev/null 2>&1 &')
        self._host.wait_for_restart(old_boot_id=boot_id)


    def run_once(self, host=None):
        self._host = host
        client_attributes = site_host_attributes.HostAttributes(host.hostname)
        client_at = autotest.Autotest(host)
        self._exact_copy(_CONSENT_FILE, _STOWED_CONSENT_FILE)

        client_at.run_test('logging_KernelCrash',
                           tag='before-crash',
                           is_before=True,
                           consent=True)

        if not client_attributes.has_working_kcrash:
            raise error.TestNAError(
                'This device is unable to report kernel crashes')

        self._crash_it(True)

        # Check for crash handling with consent.
        client_at.run_test('logging_KernelCrash',
                           tag='after-crash-consent',
                           is_before=False,
                           consent=True)

        if not self._can_disable_consent():
            logging.info('This device always has metrics enabled, '
                         'skipping test of metrics disabled mode.')
        else:
            self._crash_it(False)

            # Check for crash handling without consent.
            client_at.run_test('logging_KernelCrash',
                               tag='after-crash-no-consent',
                               is_before=False,
                               consent=False)
