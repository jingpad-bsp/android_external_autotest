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

    def cleanup(self):
        # Clear the STORAGE after the test as well.
        shutil.rmtree(self.STORAGE, ignore_errors=True)
        utils.system('umount /run/imageloader/PepperFlashPlayer')
