# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import abc
import os
import time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import file_utils
from autotest_lib.client.cros.video import bp_image_comparer


class ui_TestBase(test.test):
    """ Encapsulates steps needed to collect screenshots for ui pieces.

    Each child class must implement:
    1. Abstract method capture_screenshot()
    Each child class will define its own custom way of capturing the screenshot
    of the piece it cares about.

    E.g Child class ui_SystemTray will capture system tray screenshot,
    ui_SettingsPage for the Chrome Settings page, etc.

    2. Abstract property test_area:
    This will get appended to screenshot file names so we know what image it is,
    it will also get appended to to Biopic project names so that screenshots
    from the same area collect nicely in biopic webview.

    Flow at runtime:
    At run time, autotest will call run_once() method on a particular child
    class object, call it Y.

    Say X is a parent of Y.

    Y.run_once() will save any values passed from control file so as to use them
    later.

    Y.run_once() will then call the parent's X.run_screenshot_comparison_test()

    This is the template algorithm for collecting screenshots.

    Y.run_screenshot_comparison_test will execute its steps. It will then call
    X.test_area to get custom string to use for project name and filename.

     It will execute more steps and then call capture_screenshot(). X doesn't
     implement that, but Y does, so the method will get called on Y to produce
     Y's custom behavior.

     Control will be returned to Y run_screenshot_comparison_test() which will
     execute remainder steps.

    """

    __metaclass__ = abc.ABCMeta

    WORKING_DIR = '/tmp/test'
    BIOPIC_PROJECT_NAME_PREFIX = 'chromeos.test.ui.'
    # TODO: Set up an alias so that anyone can monitor results.
    BIOPIC_CONTACT_EMAIL = 'mussa@google.com'
    BIOPIC_TIMEOUT_S = 1

    version = 2

    def run_screenshot_comparison_test(self):
        """
        Template method to run screenshot comparison tests for ui pieces.

        Right now it will only collect images for us to look at later.

        """

        file_utils.make_leaf_dir(ui_TestBase.WORKING_DIR)

        timestamp = time.strftime('%Y_%m_%d_%H%M', time.localtime())

        filename = '%s_%s_%s_%s_%s.png' % (timestamp,
                                           'ui',
                                           self.test_area,
                                           utils.get_current_board(),
                                           utils.get_chromeos_release_version())

        filepath = os.path.join(ui_TestBase.WORKING_DIR, filename)

        project_name = ui_TestBase.BIOPIC_PROJECT_NAME_PREFIX + self.test_area

        self.capture_screenshot(filepath)

        with bp_image_comparer.BpImageComparer(
                project_name,
                ui_TestBase.BIOPIC_CONTACT_EMAIL,
                ui_TestBase.BIOPIC_TIMEOUT_S) as comparer:
            # We just care about storing these images for we can look at them
            # later. We don't wish to compare images right now.
            # Make reference images same as test image!
            comparer.compare(filepath, filepath)

        file_utils.rm_dir_if_exists(ui_TestBase.WORKING_DIR)


    @abc.abstractmethod
    def capture_screenshot(self, filepath):
        """
        Abstract method to capture a screenshot.
        Child classes must implement a custom way to take screenshots.
        This is because each will want to crop to different areas of the screen.

        @param filepath: string, complete path to save the screenshot.

        """
        pass


    @abc.abstractproperty
    def test_area(self):
        """
        Abstract property that gets the name of the test area.
        e.g. SystemTray, SettingsPage
        Each child class must implement this so as to identify what test the
        child class is doing.

        """
        pass