# -*- coding: utf-8 -*-
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import gooftools


class factory_VerifyComponents(test.test):
    version = 1
    def run_once(self,
                 component_classes=None):
        assert component_classes

        factory.log('%s run_once' % self.__class__)

        cmd = ('gooftool verify_components %s' %
               ' '.join(component_classes))
        gooftools.run(cmd)

        factory.log('%s run_once finished' % repr(self.__class__))
