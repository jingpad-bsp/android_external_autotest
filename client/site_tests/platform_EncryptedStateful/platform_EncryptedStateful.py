# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, tempfile, shutil, stat, time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class test_checker(object):
    def _passed(self, msg):
        logging.info('ok: %s' % (msg))

    def _failed(self, msg):
        logging.error('FAIL: %s' % (msg))
        self._failures.append(msg)

    def _fatal(self, msg):
        logging.error('FATAL: %s' % (msg))
        raise error.TestError(msg)

    def check(self, boolean, msg, fatal=False):
        if boolean == True:
            self._passed(msg)
        else:
            msg = "could not satisfy '%s'" % (msg)
            if fatal:
                self._fatal(msg)
            else:
                self._failed(msg)


class EncryptedStateful(test_checker):
    def __init__(self):
        self.root = tempfile.mkdtemp(dir='/mnt/stateful_partition',
                                     prefix='.test-enc-stateful-')

        try:
            self.var = os.path.join(self.root, 'var')
            os.makedirs(self.var)

            self.chronos = os.path.join(self.root, 'home', 'chronos')
            os.makedirs(self.chronos)

            self.stateful = os.path.join(self.root, 'mnt', 'stateful_partition')
            os.makedirs(self.stateful)

            utils.system("mount -n -t tmpfs tmp %s" % (self.stateful))

            self.key = os.path.join(self.stateful, 'encrypted.key')
            self.block = os.path.join(self.stateful, 'encrypted.block')
            self.encrypted = os.path.join(self.stateful, 'encrypted')
        except:
            shutil.rmtree(self.root)
            raise

        self.mounted = False

    def mount(self, args=""):
        if self.mounted:
            return
        utils.system("MOUNT_ENCRYPTED_ROOT=%s mount-encrypted %s" %
                         (self.root, args))
        self.mounted = True

    def umount(self):
        if not self.mounted:
            return
        utils.system("MOUNT_ENCRYPTED_ROOT=%s mount-encrypted umount" %
                         (self.root))
        self.mounted = False

    # Clean up when destroyed.
    def __del__(self):
        self.umount()
        utils.system("umount -n %s" % (self.stateful))
        shutil.rmtree(self.root)

    # Perform common post-mount sanity checks on the filesystem and backing
    # files.
    def sanity_check(self):
        # Do we have the expected backing files?
        self.check(os.path.exists(self.key), "%s exists" % (self.key))
        self.check(os.path.exists(self.block), "%s exists" % (self.block))

        # Sanity check the key file stat.
        info = os.stat(self.key)
        self.check(stat.S_ISREG(info.st_mode),
                   "%s is regular file" % (self.key))
        self.check(info.st_uid == 0, "%s is owned by root" % (self.key))
        self.check(info.st_gid == 0, "%s has group root" % (self.key))
        self.check(stat.S_IMODE(info.st_mode) == (stat.S_IRUSR | stat.S_IWUSR),
                   "%s is S_IRUSR | S_IWUSR" % (self.key))
        self.check(info.st_size == 48, "%s is 48 bytes" % (self.key))

        # Sanity check the block file stat.
        info = os.stat(self.block)
        self.check(stat.S_ISREG(info.st_mode),
                   "%s is regular file" % (self.block))
        self.check(info.st_uid == 0, "%s is owned by root" % (self.block))
        self.check(info.st_gid == 0, "%s has group root" % (self.block))
        self.check(stat.S_IMODE(info.st_mode) == (stat.S_IRUSR | stat.S_IWUSR),
                   "%s is S_IRUSR | S_IWUSR" % (self.block))
        # Make sure block file is roughly a third of the size of the root
        # filesystem (within 20%).
        top = os.statvfs(self.stateful)
        third = top.f_blocks * top.f_bsize / 3
        self.check(info.st_size > (third * .8)
                   and info.st_size < (third * 1.2),
                   "%s is near %d bytes (was %d)" % (self.block, third,
                                                     info.st_size))

        # Wait for resize to finish.
        utils.poll_for_condition(lambda: utils.system("pgrep resize2fs",
                                                      ignore_status=True) != 0,
                                 error.TestError('resize still running'))

        # Verify there is a reasonable number of inodes in the encrypted
        # filesystem (> 20% inodes-to-blocks ratio).
        info = os.statvfs(self.encrypted)
        self.check(float(info.f_files) / float(info.f_blocks) > 0.20,
                   "%s has at least 20%% inodes-to-blocks" % (self.encrypted))


class platform_EncryptedStateful(test.test, test_checker):
    version = 1

    def factory_key(self):
        # Create test root directory.
        encstate = EncryptedStateful()

        # Make sure we haven't run here before.
        self.check(not os.path.exists(encstate.key),
                   "%s does not exist" % (encstate.key))
        self.check(not os.path.exists(encstate.block),
                   "%s does not exist" % (encstate.block))

        # Mount a fresh encrypted stateful, with factory static key.
        encstate.mount("factory")

        # Perform post-mount sanity checks.
        encstate.sanity_check()

    def run_once(self):
        # Empty failure list means test passes.
        self._failures = []

        # There is no interactively controllable TPM mock yet for
        # mount-encrypted, so we can only test the static key currently.
        self.factory_key()

        # Raise a failure if anything unexpected was seen.
        if len(self._failures):
            raise error.TestFail((", ".join(self._failures)))
