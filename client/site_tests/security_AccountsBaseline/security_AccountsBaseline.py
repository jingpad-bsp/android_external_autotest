# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import shutil

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils


class security_AccountsBaseline(test.test):
    """Enforces a whitelist of known user and group IDs."""

    version = 1


    @staticmethod
    def validate_passwd(entry):
        """Check users that are not in the baseline.
           The user ID should match the group ID, and the user's home directory
           and shell should be invalid."""
        uid = int(entry[2])
        gid = int(entry[3])

        if uid != gid:
            logging.error("New user '%s' has uid %d and different gid %d",
                          entry[0], uid, gid)
            return False

        if entry[5] != '/dev/null':
            logging.error("New user '%s' has valid home dir '%s'", entry[0],
                          entry[5])
            return False

        if entry[6] != '/bin/false':
            logging.error("New user '%s' has valid shell '%s'", entry[0],
                          entry[6])
            return False

        return True


    @staticmethod
    def validate_group(entry):
        """Check groups that are not in the baseline.
           Allow groups that have no users and groups with only the matching
           user."""
        group_name = entry[0]
        users = entry[3]

        # Groups with no users and groups with only the matching user are OK.
        if len(users) == 0 or users == group_name:
            return True

        logging.error("New group '%s' has users '%s'", group_name, users)
        return False


    @staticmethod
    def match_passwd(expected, actual):
        """Match login shell (2nd field), uid (3rd field),
           and gid (4th field)."""
        if expected[1:4] != actual[1:4]:
            logging.error(
                "Expected shell/uid/gid %s for user '%s', got %s.",
                tuple(expected[1:4]), expected[0], tuple(actual[1:4]))
            return False
        return True


    @staticmethod
    def match_group(expected, actual):
        """Match login shell (2nd field), gid (3rd field),
           and members (4th field, comma-separated)."""
        matched = True
        if expected[1:3] != actual[1:3]:
            matched = False
            logging.error(
                "Expected shell/id %s for group '%s', got %s.",
                tuple(expected[1:3]), expected[0], tuple(actual[1:3]))
        if set(expected[3].split(',')) != set(actual[3].split(',')):
            matched = False
            logging.error(
                "Expected members '%s' for group '%s', got '%s'.",
                expected[3], expected[0], actual[3])
        return matched


    def load_path(self, path):
        """Load the given passwd/group file.

        @param path: Path to the file.

        @returns: A dict of passwd/group entries indexed by account name.
        """
        entries = [x.strip().split(':') for x in open(path).readlines()]
        return dict((e[0], e) for e in entries)


    def load_baseline(self, basename):
        """Loads baseline."""
        expected_entries = self.load_path(
            os.path.join(self.bindir, 'baseline.%s' % basename))

        # TODO(jorgelo): Merge this into the main baseline once:
        #     *Freon users are included in the main overlay.
        extra_baseline = 'baseline.%s.freon' % basename
        expected_entries.update(self.load_path(
            os.path.join(self.bindir, extra_baseline)))

        board = utils.get_current_board()
        board_baseline_path = os.path.join(self.bindir, 'baseline.%s.%s' %
                                           (basename, board))
        if os.path.exists(board_baseline_path):
            board_baseline = self.load_path(board_baseline_path)
            expected_entries.update(board_baseline)

        return expected_entries


    def capture_files(self):
        """Copies passwd and group files from rootfs to |resultsdir|.

        We first bind mount the rootfs to a temporary location and read the etc
        files from there, because on some boards, e.g., lakitu, /etc is
        remounted as read-write and its content non-deterministic.
        """
        rootfs_bindmount_path = os.path.join(self.tmpdir, 'rootfs_bindmount')
        os.mkdir(rootfs_bindmount_path)
        utils.system(['mount', '--bind', '/', rootfs_bindmount_path])

        for f in ['passwd','group']:
            shutil.copyfile(os.path.join(rootfs_bindmount_path, 'etc', f),
                            os.path.join(self.resultsdir, f))

        utils.system(['umount', rootfs_bindmount_path])


    def check_file(self, basename):
        """Validates the passwd or group file."""
        match_func = getattr(self, 'match_%s' % basename)
        validate_func = getattr(self, 'validate_%s' % basename)

        expected_entries = self.load_baseline(basename)
        actual_entries = self.load_path(os.path.join(self.resultsdir, basename))

        if len(actual_entries) > len(expected_entries):
            logging.warning(
                '%s baseline mismatch: expected %d entries, got %d.',
                basename, len(expected_entries), len(actual_entries))

        success = True
        for entry, details in actual_entries.iteritems():
            if entry not in expected_entries:
                logging.warning("Unexpected %s entry for '%s'.", basename,
                                entry)
                success = success and validate_func(details)
                continue
            expected = expected_entries[entry]
            match_res = match_func(expected, details)
            success = success and match_res

        missing = set(expected_entries.keys()) - set(actual_entries.keys())
        for m in missing:
            logging.info("Ignoring missing %s entry for '%s'.", basename, m)

        return success


    def run_once(self):
        self.capture_files()

        passwd_ok = self.check_file('passwd')
        group_ok = self.check_file('group')

        # Fail after all mismatches have been reported.
        if not (passwd_ok and group_ok):
            raise error.TestFail('Baseline mismatch, see error log')
