# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import serial_task
import region_task

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import shopfloor
from autotest_lib.client.cros.factory import task
from autotest_lib.client.cros.factory import ui

_MESSAGE_FETCH_FROM_SHOP_FLOOR = "Fetching VPD from shop floor server..."
_MESSAGE_WRITING = "Writing VPD:"


class WriteVpdTask(task.FactoryTask):

    def __init__(self, vpd):
        self.vpd = vpd

    def write_vpd(self):
        """Writes a VPD structure into system.

        @param vpd: A dictionary with 'ro' and 'rw' keys, each associated with a
          key-value VPD data set.
        """
        def shell(command):
            factory.log(command)
            utils.system(command)

        def format_vpd_parameter(vpd_dict):
            """Formats a key-value dictionary into VPD syntax."""
            # Writes in sorted ordering so the VPD structure will be more
            # deterministic.
            return ' '.join(('-s "%s"="%s"' % (key, vpd_dict[key])
                             for key in sorted(vpd_dict)))

        vpd = self.vpd
        VPD_LIST = (('RO_VPD', 'ro'), ('RW_VPD', 'rw'))
        for (section, vpd_type) in VPD_LIST:
            if not vpd.get(vpd_type, None):
                continue
            parameter = format_vpd_parameter(vpd[vpd_type])
            shell('vpd -i %s %s' % (section, parameter))
        self.stop()

    def start(self):
        # Flatten key-values in VPD dictionary.
        vpd = self.vpd
        vpd_list = []
        for vpd_type in ('ro', 'rw'):
            vpd_list += ['%s: %s = %s' % (vpd_type, key, vpd[vpd_type][key])
                         for key in sorted(vpd[vpd_type])]

        self.add_widget(ui.make_label("%s\n%s" % (_MESSAGE_WRITING,
                                                  '\n'.join(vpd_list))))
        task.schedule(self.write_vpd)


class ShopFloorVpdTask(task.FactoryTask):

    def __init__(self, vpd):
        self.vpd = vpd

    def start(self):
        self.add_widget(ui.make_label(_MESSAGE_FETCH_FROM_SHOP_FLOOR))
        task.schedule(self.fetch_vpd)

    def fetch_vpd(self):
        self.vpd.update(shopfloor.get_vpd())
        self.stop()


class factory_VPD(test.test):
    version = 5

    def run_once(self, override_vpd=None):
        factory.log('%s run_once' % self.__class__)
        self.tasks = []
        self.vpd = override_vpd or {'ro': {}, 'rw': {}}

        if not override_vpd:
            if shopfloor.is_enabled():
                self.tasks += [ShopFloorVpdTask(self.vpd)]
            else:
                self.tasks += [serial_task.SerialNumberTask(self.vpd),
                               region_task.SelectRegionTask(self.vpd)]
        self.tasks += [WriteVpdTask(self.vpd)]
        task.run_factory_tasks(self.job, self.tasks)

        factory.log('%s run_once finished' % repr(self.__class__))
