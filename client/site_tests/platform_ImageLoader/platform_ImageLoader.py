# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import os
import shutil
import subprocess
import utils

from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib.cros import dbus_send


class platform_ImageLoader(test.test):
    """Tests the ImageLoader dbus service.
    """

    version = 1
    STORAGE = '/var/lib/imageloader'
    BUS_NAME = 'org.chromium.ImageLoader'
    BUS_PATH = '/org/chromium/ImageLoader'
    BUS_INTERFACE = 'org.chromium.ImageLoaderInterface'
    GET_COMPONENT_VERSION = 'GetComponentVersion'
    REGISTER_COMPONENT = 'RegisterComponent'
    BAD_RESULT = ''
    USER = 'chronos'
    COMPONENT_NAME = 'PepperFlashPlayer'
    CORRUPT_COMPONENT_NAME = 'CorruptPepperFlashPlayer'
    CORRUPT_COMPONENT_PATH = '/tmp/CorruptPepperFlashPlayer'
    OLD_VERSION = '23.0.0.207'
    NEW_VERSION = '24.0.0.186'

    def _get_component_version(self, name):
        args = [dbus.String(name)]
        return dbus_send.dbus_send(
            self.BUS_NAME,
            self.BUS_INTERFACE,
            self.BUS_PATH,
            self.GET_COMPONENT_VERSION,
            user=self.USER,
            args=args).response

    def _register_component(self, name, version, path):
        args = [dbus.String(name), dbus.String(version), dbus.String(path)]
        return dbus_send.dbus_send(
            self.BUS_NAME,
            self.BUS_INTERFACE,
            self.BUS_PATH,
            self.REGISTER_COMPONENT,
            timeout_seconds=20,
            user=self.USER,
            args=args).response

    def _corrupt_and_load_component(self, component, iteration, target, offset):
        """
        Registers a valid component and then corrupts it by writing a
        random byte to the target file at the given offset. It then attemps
        to load the component and returns whether or not that succeeded.

        @component The path to the component to register.
        @iteration A prefix to append to the name of the component, so that
                   multiple registrations do not clash.
        @target    The name of the file in the component to corrupt.
        @offset    The offset in the file to corrupt.
        """

        if not self._register_component(self.CORRUPT_COMPONENT_NAME + iteration,
                                        self.OLD_VERSION, component):
            raise error.TestError('Failed to register a valid component')

        corrupt_path = ('/var/lib/imageloader/' + self.CORRUPT_COMPONENT_NAME +
                        iteration + '/' + self.OLD_VERSION)
        os.system('printf \'\\xa1\' | dd conv=notrunc of=%s bs=1 seek=%s' %
                  (corrupt_path + '/' + target, offset))

        return subprocess.call([
            '/usr/sbin/imageloader', '--mount',
            '--mount_component=' + self.CORRUPT_COMPONENT_NAME + iteration,
            '--mount_point=/run/imageloader/' + self.CORRUPT_COMPONENT_NAME +
            iteration
        ]) == 0

    def initialize(self):
        # Clear any existing storage before the test.
        shutil.rmtree(self.STORAGE, ignore_errors=True)

    def run_once(self, component1=None, component2=None):

        if component1 == None or component2 == None:
            raise error.TestError('Must supply two versions of '
                                  'a production signed component.')

        # Make sure there is no version returned at first.
        if self._get_component_version(self.COMPONENT_NAME) != self.BAD_RESULT:
            raise error.TestError('There should be no currently '
                                  'registered component version')

        # Register a component and fetch the version.
        if not self._register_component(self.COMPONENT_NAME, self.OLD_VERSION,
                                        component1):
            raise error.TestError('The component failed to register')

        if self._get_component_version(self.COMPONENT_NAME) != '23.0.0.207':
            raise error.TestError('The component version is incorrect')

        # Make sure the same version cannot be re-registered.
        if self._register_component(self.COMPONENT_NAME, self.OLD_VERSION,
                                    component1):
            raise error.TestError('ImageLoader allowed registration '
                                  'of duplicate component version')

        # Make sure that ImageLoader matches the reported version to the
        # manifest.
        if self._register_component(self.COMPONENT_NAME, self.NEW_VERSION,
                                    component1):
            raise error.TestError('ImageLoader allowed registration of a '
                                  'mismatched component version')

        # Register a newer component and fetch the version.
        if not self._register_component(self.COMPONENT_NAME, self.NEW_VERSION,
                                        component2):
            raise error.TestError('Failed to register updated version')

        if self._get_component_version(self.COMPONENT_NAME) != '24.0.0.186':
            raise error.TestError('The component version is incorrect')

        # Simulate a rollback.
        if self._register_component(self.COMPONENT_NAME, self.OLD_VERSION,
                                    component1):
            raise error.TestError('ImageLoader allowed a rollback')

        # Now test loading the component.
        if subprocess.call([
                '/usr/sbin/imageloader', '--mount',
                '--mount_component=PepperFlashPlayer',
                '--mount_point=/run/imageloader/PepperFlashPlayer'
        ]) != 0:
            raise error.TestError('Failed to mount component')

        if not os.path.exists(
                '/run/imageloader/PepperFlashPlayer/libpepflashplayer.so'):
            raise error.TestError('Flash player file does not exist')

        # Now test some corrupt components.
        shutil.copytree(component1, self.CORRUPT_COMPONENT_PATH)
        # Corrupt the disk image file in the corrupt component.
        os.system('printf \'\\xa1\' | dd conv=notrunc of=%s bs=1 seek=1000000' %
                  (self.CORRUPT_COMPONENT_PATH + '/image.squash'))
        # Make sure registration fails.
        if self._register_component(self.CORRUPT_COMPONENT_NAME,
                                    self.OLD_VERSION,
                                    self.CORRUPT_COMPONENT_PATH):
            raise error.TestError('Registered a corrupt component')

        # Now register a valid component, and then corrupt it.
        if not self._corrupt_and_load_component(component1, '1', 'image.squash',
                                                '1000000'):
            raise error.TestError('Failed to load component with corrupt image')

        corrupt_file = ('/run/imageloader/CorruptPepperFlashPlayer1/'
                        'libpepflashplayer.so')
        if not os.path.exists(corrupt_file):
            raise error.TestError('Flash player file does not exist')

        # Reading the files should fail.
        # This is a critical test. We assume dm-verity works, but by default it
        # panics the machine and forces a powerwash. For component updates,
        # ImageLoader should configure the dm-verity table to just return an I/O
        # error. If this test does not throw an exception at all, ImageLoader
        # may not be attaching the dm-verity tree correctly.
        try:
            with open(corrupt_file, 'rb') as f:
                byte = f.read(1)
                while byte != '':
                    byte = f.read(1)
        except IOError:
            pass
            # Catching an IOError once we read the corrupt block is the expected
            # behavior.
        else:
            raise error.TestError(
                'Did not receive an I/O error while reading the corrupt image')

        # Modify the signature and make sure the component does not load.
        if self._corrupt_and_load_component(component1, '2',
                                            'imageloader.sig.1', '50'):
            raise error.TestError('Mounted component with corrupt signature')

        # Modify the manifest and make sure the component does not load.
        if self._corrupt_and_load_component(component1, '3', 'imageloader.json',
                                            '1'):
            raise error.TestError('Mounted component with corrupt manifest')

        # Modify the table and make sure the component does not load.
        if self._corrupt_and_load_component(component1, '4', 'table', '1'):
            raise error.TestError('Mounted component with corrupt table')

    def cleanup(self):
        # Clear the STORAGE after the test as well.
        shutil.rmtree(self.STORAGE, ignore_errors=True)
        shutil.rmtree(self.CORRUPT_COMPONENT_PATH, ignore_errors=True)
        utils.system(
            'umount /run/imageloader/PepperFlashPlayer', ignore_status=True)
        utils.system(
            'umount /run/imageloader/CorruptPepperFlashPlayer1',
            ignore_status=True)
