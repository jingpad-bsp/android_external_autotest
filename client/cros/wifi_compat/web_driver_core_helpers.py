# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'deps',
                             'pyauto_dep', 'test_src', 'third_party',
                             'webdriver', 'pylib'))

try:
  from selenium import webdriver
except ImportError:
  raise ImportError('Could not locate the webdriver package.  Did you build? '
                    'Are you using a prebuilt autotest package?')

from selenium.common.exceptions import TimeoutException as \
    SeleniumTimeoutException
from selenium.webdriver.support.ui import WebDriverWait


class WebDriverCoreHelpers(object):
    """Base class for manipulating web pages using webdriver."""

    def __init__(self):
        super(WebDriverCoreHelpers, self).__init__()
        self.driver = None
        self.wait = None

    def click_button_by_id(self, element_id):
        """Clicks a button by id.

        Args:
          element_id: the id of the button
        """
        xpath = 'id("%s")' % element_id
        return self.click_button_by_xpath(xpath)

    def click_button_by_xpath(self, xpath):
        """Clicks a button by xpath.

        Args:
          xpath: the xpath of the button
        """
        button = self.wait_for_object_by_xpath(xpath)
        button.click()

    def wait_for_object_by_id(self, element_id):
        """Waits for an element to become available; returns a reference to it.

        Args:
          element_id: the id of the element to wait for

        Returns:
          Reference to the element if found before a timeout.
        """
        xpath = 'id("%s")' % element_id
        return self.wait_for_object_by_xpath(xpath)

    def wait_for_object_by_xpath(self, xpath):
        """Waits for an element to become available; returns a reference to it.

        Args:
          xpath: the xpath of the element to wait for

        Returns:
          Reference to the element if found before a timeout.
        """
        try:
            self.wait.until(lambda _: self.driver.find_element_by_xpath(xpath))
        except SeleniumTimeoutException, e:
            raise SeleniumTimeoutException('Unable to find the object by '
                                           'xpath: %s\n WebDriver exception: '
                                           '%s' % (xpath, str(e)))
        return self.driver.find_element_by_xpath(xpath)

    def select_item_from_popup_by_id(self, item, element_id,
                                     wait_for_xpath=None):
        """Selects an item from a popup, by passing the element ID.

        Args:
          item: the string of the item to select from the popup
          element_id: the html ID of the item
          wait_for_xpath: an item to wait for before returning, if not specified
                          the method does not wait.
        """
        xpath = 'id("%s")' % element_id
        self.select_item_from_popup_by_xpath(item, xpath, wait_for_xpath)

    def select_item_from_popup_by_xpath(self, item, xpath, wait_for_xpath=None):
        """Selects an item from a popup, by passing the xpath of the popup.

        Args:
          item: the string of the item to select from the popup
          xpath: the xpath of the popup
          wait_for_xpath: an item to wait for before returning, if not specified
                          the method does not wait.
        """
        popup = self.driver.find_element_by_xpath(xpath)
        try:
            self.wait.until(lambda _:
                            len(popup.find_elements_by_tag_name('option')))
        except SeleniumTimeoutException, e:
            raise SeleniumTimeoutException('The popup at xpath %s has no items.'
                                           '\n WebDriver exception: %s', xpath,
                                           str(e))
        for option in popup.find_elements_by_tag_name('option'):
            if option.text == item:
                option.click()
                break
        if wait_for_xpath:
            self.wait_for_object_by_xpath(wait_for_xpath)

    def set_content_of_text_field_by_id(self, content, text_field_id,
                                        wait_for_xpath=None):
        """Sets the content of a textfield, by passing the element ID.

        Args:
          content: the content to apply to the textfield
          text_field_id: the html ID of the textfield
          wait_for_xpath: an item to wait for before returning, if not specified
                          the method does not wait.
        """
        xpath = 'id("%s")' % text_field_id
        self.set_content_of_text_field_by_xpath(content, xpath, wait_for_xpath)

    def set_content_of_text_field_by_xpath(self, content, xpath,
                                           wait_for_xpath=None,
                                           abort_check=False):
        """Sets the content of a textfield, by passing the xpath.

        Args:
          content: the content to apply to the textfield
          xpath: the xpath of the textfield
          wait_for_xpath: an item to wait for before returning, if not specified
                          the method does not wait.
          abort_check: do not attempt to get the current value before setting
        """
        # When we can get the value we know the text field is ready.
        text_field = self.driver.find_element_by_xpath(xpath)
        if text_field.get_attribute('type') != 'password' and not abort_check:
            try:
                self.wait.until(lambda _: text_field.get_attribute('value'))
            except SeleniumTimeoutException, e:
                raise SeleniumTimeoutException('Unable to obtain the value of '
                                               'the text field %s.\nWebDriver '
                                               'exception:%s' % (xpath, str(e)))
        text_field = self.driver.find_element_by_xpath(xpath)
        text_field.clear()
        text_field.send_keys(content)
        if wait_for_xpath: self.wait_for_object_by_xpath(wait_for_xpath)

    def set_check_box_selected_by_id(self, check_box_id, selected=True,
                                     wait_for_xpath=None):
        """Sets the state of a checkbox, by passing the ID.

        Args:
          check_box_id: the html id of the checkbox
          selected: True to check the checkbox; False to uncheck it
          wait_for_xpath: an item to wait for before returning, if not specified
                          the method does not wait.
        """
        xpath = 'id("%s")' % check_box_id
        self.set_check_box_selected_by_xpath(xpath, selected, wait_for_xpath)

    def set_check_box_selected_by_xpath(self, xpath, selected=True,
                                        wait_for_xpath=None):
        """Sets the state of a checkbox, by passing the xpath.

        Args:
          xpath: the xpath of the checkbox
          selected: True to check the checkbox; False to uncheck it
          wait_for_xpath: an item to wait for before returning, if not specified
                          the method does not wait.
        """
        check_box = self.wait_for_object_by_xpath(xpath)
        value = check_box.get_attribute('value')
        if (value == '1' and not selected) or (value == '0' and selected):
            check_box.click()
        if wait_for_xpath:
            self.wait_for_object_by_xpath(wait_for_xpath)
