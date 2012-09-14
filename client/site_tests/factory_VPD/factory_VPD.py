# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import serial_task
import region_task

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.cros import factory_setup_modules
from cros.factory.test import factory
from cros.factory.test import registration_codes
from cros.factory.test import shopfloor
from cros.factory.test import task
from cros.factory.test import ui

_MESSAGE_FETCH_FROM_SHOP_FLOOR = "Fetching VPD from shop floor server..."
_MESSAGE_WRITING = "Writing VPD:"


def format_vpd_parameter(vpd_dict):
    """Formats a key-value dictionary into VPD syntax."""
    # Writes in sorted ordering so the VPD structure will be more
    # deterministic.
    return ' '.join(('-s "%s"="%s"' % (key, vpd_dict[key])
                     for key in sorted(vpd_dict)))


class WriteVpdTask(task.FactoryTask):

    def __init__(self, vpd, registration_code_map):
        self.vpd = vpd
        self.registration_code_map = registration_code_map

    def write_vpd(self):
        """Writes a VPD structure into system.

        @param vpd: A dictionary with 'ro' and 'rw' keys, each associated with a
          key-value VPD data set.
        """
        def shell(command):
            factory.log(command)
            utils.system(command)

        vpd = self.vpd
        VPD_LIST = (('RO_VPD', 'ro'), ('RW_VPD', 'rw'))
        for (section, vpd_type) in VPD_LIST:
            if not vpd.get(vpd_type, None):
                continue
            parameter = format_vpd_parameter(vpd[vpd_type])
            shell('vpd -i %s %s' % (section, parameter))

        if self.registration_code_map is not None:
            # Check registration codes (fail test if invalid).
            for k in ['user', 'group']:
                if k not in self.registration_code_map:
                    raise error.TestError('Missing %s registration code' % k)
                registration_codes.CheckRegistrationCode(
                    self.registration_code_map[k])

            # Add registration codes, being careful not to log the command.
            factory.log('Storing registration codes')
            utils.system(
                'vpd -i %s %s' % (
                    'RW_VPD',
                    format_vpd_parameter(
                        # See <http://src.chromium.org/svn/trunk/src/chrome/
                        # browser/chromeos/extensions/echo_private_api.cc>.
                        {'ubind_attribute':
                             self.registration_code_map['user'],
                         'gbind_attribute':
                             self.registration_code_map['group']})))

        self.stop()

    def start(self):
        # Flatten key-values in VPD dictionary.
        vpd = self.vpd
        vpd_list = []
        for vpd_type in ('ro', 'rw'):
            vpd_list += ['%s: %s = %s' % (vpd_type, key, vpd[vpd_type][key])
                         for key in sorted(vpd[vpd_type])]
        if self.registration_code_map:
            vpd_list += ['rw: registration codes']

        self.add_widget(ui.make_label("%s\n%s" % (_MESSAGE_WRITING,
                                                  '\n'.join(vpd_list))))
        task.schedule(self.write_vpd)


class ShopFloorVpdTask(task.FactoryTask):

    def __init__(self, vpd, registration_code_map):
        self.vpd = vpd
        self.registration_code_map = registration_code_map

    def start(self):
        self.add_widget(ui.make_label(_MESSAGE_FETCH_FROM_SHOP_FLOOR))
        task.schedule(self.fetch_vpd)

    def fetch_vpd(self):
        self.vpd.update(shopfloor.get_vpd())
        if self.registration_code_map is not None:
            self.registration_code_map.update(
                shopfloor.get_registration_code_map())
        self.stop()


class factory_VPD(test.test):
    version = 5

    SERIAL_TASK_NAME = 'serial'
    REGION_TASK_NAME = 'region'

    def run_once(self, override_vpd=None,
                 store_registration_codes=False,
                 task_list=[SERIAL_TASK_NAME, REGION_TASK_NAME]):
        factory.log('%s run_once' % self.__class__)
        self.tasks = []
        self.vpd = override_vpd or {'ro': {}, 'rw': {}}
        self.registration_code_map = {} if store_registration_codes else None

        if not override_vpd:
            if shopfloor.is_enabled():
                self.tasks += [
                    ShopFloorVpdTask(self.vpd, self.registration_code_map)]
            else:
                if self.SERIAL_TASK_NAME in task_list:
                    self.tasks += [serial_task.SerialNumberTask(self.vpd)]
                if self.REGION_TASK_NAME in task_list:
                    self.tasks += [region_task.SelectRegionTask(self.vpd)]
        self.tasks += [WriteVpdTask(self.vpd, self.registration_code_map)]
        task.run_factory_tasks(self.job, self.tasks)

        factory.log('%s run_once finished' % repr(self.__class__))
