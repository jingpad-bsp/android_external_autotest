# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import abc
import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import file_utils
from autotest_lib.client.cros.image_comparison import image_comparison_factory


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
    REMOTE_DIR = 'http://storage.googleapis.com/chromiumos-test-assets-public'
    AUTOTEST_CROS_UI_DIR = '/usr/local/autotest/cros/ui'
    IMG_COMP_CONF_FILE = 'image_comparison.conf'

    version = 2


    def run_screenshot_comparison_test(self):
        """
        Template method to run screenshot comparison tests for ui pieces.

        1. Set up test dirs.
        2. Create bp project name.
        3. Download golden image.
        4. Capture test image.
        5. Compare images locally, if FAIL upload to bp for analysis later.
        6. Clean up test dirs.

        """

        img_comp_conf_path = os.path.join(ui_TestBase.AUTOTEST_CROS_UI_DIR,
                                          ui_TestBase.IMG_COMP_CONF_FILE)

        img_comp_factory = image_comparison_factory.ImageComparisonFactory(
                img_comp_conf_path)

        project_specs = [img_comp_factory.bp_base_projname,
                         utils.get_current_board(),
                         utils.get_chromeos_release_version().replace('.', '_'),
                         self.test_area]

        project_name = '.'.join(project_specs)

        golden_image_local_dir = os.path.join(ui_TestBase.WORKING_DIR,
                                              'golden_images')

        file_utils.make_leaf_dir(golden_image_local_dir)

        filename = '%s.png' % self.test_area

        golden_image_remote_path = os.path.join(
                ui_TestBase.REMOTE_DIR,
                'ui',
                self.test_area,
                filename)

        golden_image_local_path = os.path.join(golden_image_local_dir, filename)

        test_image_filepath = os.path.join(ui_TestBase.WORKING_DIR, filename)

        file_utils.download_file(golden_image_remote_path,
                                 golden_image_local_path)

        self.capture_screenshot(test_image_filepath)

        comparer = img_comp_factory.make_upload_on_fail_comparer(project_name)

        verifier = img_comp_factory.make_image_verifier(comparer)

        verifier.verify(golden_image_local_path, test_image_filepath)

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
