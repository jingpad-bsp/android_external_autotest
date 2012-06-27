# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import select_task

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.cros import factory_setup_modules
from cros.factory.test import factory
from cros.factory.test import gooftools
from cros.factory.test import shopfloor
from cros.factory.test import task
from cros.factory.test import ui

_MESSAGE_FETCH_FROM_SHOP_FLOOR = "Fetching HWID from shop floor server..."
_MESSAGE_WRITING = "Writing HWID:"


class WriteHwidTask(task.FactoryTask):

    def __init__(self, data):
        self.data = data

    def write_hwid(self):
        # TODO(hungte) Support partial matching by gooftools or hwid_tool.
        # When the input is not a complete HWID (i.e., BOM-VARIANT pair), select
        # and derive the complete ID from active HWIDs in current database.
        # Ex: input="BLUE A" => matched to "MARIO BLUE A-B 6868".
        hwid = self.data['hwid']
        assert hwid
        gooftools.run("gooftool write_hwid '%s'" % hwid)
        self.stop()

    def start(self):
        assert 'hwid' in self.data, "Missing HWID in data."
        hwid = self.data.get('hwid', None)

        if not hwid:
            raise ValueError("Invalid empty HWID")
        self.add_widget(ui.make_label("%s\n%s" % (_MESSAGE_WRITING, hwid)))
        task.schedule(self.write_hwid)


class ShopFloorHwidTask(task.FactoryTask):

    def __init__(self, data):
        self.data = data

    def start(self):
        self.add_widget(ui.make_label(_MESSAGE_FETCH_FROM_SHOP_FLOOR))
        task.schedule(self.fetch_hwid)

    def fetch_hwid(self):
        self.data['hwid'] = shopfloor.get_hwid()
        self.stop()


class factory_HWID(test.test):
    version = 3

    def run_once(self, override_hwid=None):
        factory.log('%s run_once' % self.__class__)

        self.data = {'hwid': override_hwid}
        self.tasks = [WriteHwidTask(self.data)]
        if not override_hwid:
            self.tasks.insert(0,
                              ShopFloorHwidTask(self.data)
                              if shopfloor.is_enabled()
                              else select_task.SelectHwidTask(self.data))
        task.run_factory_tasks(self.job, self.tasks)

        factory.log('%s run_once finished' % repr(self.__class__))
