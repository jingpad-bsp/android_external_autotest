#!/usr/bin/python
#
# Copyright (c) 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import common
from autotest_lib.server.cros import provision


class LabelFromStrTestCase(unittest.TestCase):
    """label_from_str() test case."""

    def test_fallback_label_unchanged(self):
        """Test that Label doesn't change str value."""
        label_str = 'dummy_label'
        got = provision.label_from_str(label_str)
        self.assertEqual(got, label_str)

    def test_fallback_label_type(self):
        """Test that label_from_str() falls back to Label."""
        label_str = 'dummy_label'
        got = provision.label_from_str(label_str)
        self.assertIsInstance(got, provision.Label)

    def test_fallback_namespace_unchanged(self):
        """Test that NamespaceLabel doesn't change str value."""
        label_str = 'dummy-namespace:value'
        got = provision.label_from_str(label_str)
        self.assertEqual(got, label_str)

    def test_fallback_namespace_label_type(self):
        """Test that label_from_str() falls back to NamespaceLabel."""
        label_str = 'dummy-namespace:value'
        got = provision.label_from_str(label_str)
        self.assertIsInstance(got, provision.NamespaceLabel)

    def test_cros_version_unchanged(self):
        """Test that CrosVersionLabel doesn't change str value."""
        label_str = 'cros-version:value'
        got = provision.label_from_str(label_str)
        self.assertEqual(got, label_str)

    def test_cros_version_label_type(self):
        """Test that label_from_str() detects cros-version."""
        label_str = 'cros-version:value'
        got = provision.label_from_str(label_str)
        self.assertIsInstance(got, provision.CrosVersionLabel)

    def test_fwrw_version_label_type(self):
        """Test that label_from_str() detects fwrw-version."""
        label_str = 'fwrw-version:value'
        got = provision.label_from_str(label_str)
        self.assertIsInstance(got, provision.FWRWVersionLabel)

    def test_fwro_version_label_type(self):
        """Test that label_from_str() detects fwro-version."""
        label_str = 'fwro-version:value'
        got = provision.label_from_str(label_str)
        self.assertIsInstance(got, provision.FWROVersionLabel)


class LabelTestCase(unittest.TestCase):
    """Label test case."""

    def test_label_repr(self):
        """Test that Label repr works."""
        label = provision.Label('dummy_label')
        self.assertEqual(repr(label), "Label('dummy_label')")

    def test_label_eq_str(self):
        """Test that Label equals its string value."""
        label = provision.Label('dummy_label')
        self.assertEqual(label, 'dummy_label')

    def test_get_action(self):
        """Test Label action property."""
        action = provision.Label('dummy_label').action
        self.assertEqual(action, provision.Action('dummy_label', ''))


class NamespaceLabelTestCase(unittest.TestCase):
    """NamespaceLabel test case."""

    def test_get_namespace(self):
        """Test NamespaceLabel namespace property."""
        label = provision.NamespaceLabel('ns', 'value')
        self.assertEqual(label.namespace, 'ns')

    def test_get_value(self):
        """Test NamespaceLabel value property."""
        label = provision.NamespaceLabel('ns', 'value')
        self.assertEqual(label.value, 'value')

    def test_from_str_identity(self):
        """Test NamespaceLabel.from_str() result equals argument."""
        label = provision.NamespaceLabel.from_str('ns:value')
        self.assertEqual(label, 'ns:value')

    def test_namespace_with_multiple_colons(self):
        """Test NamespaceLabel.from_str() on argument with multiple colons."""
        label = provision.NamespaceLabel.from_str('ns:value:value2')
        self.assertEqual(label.namespace, 'ns')
        self.assertEqual(label.value, 'value:value2')

    def test_get_action(self):
        """Test Label action property."""
        action = provision.NamespaceLabel('cros-version', 'foo').action
        self.assertEqual(action, provision.Action('cros-version', 'foo'))


class CrosVersionLabelTestCase(unittest.TestCase):
    """CrosVersionLabel test case."""

    def test_value_is_cros_image(self):
        """Test that value is CrosVersion type."""
        label = provision.CrosVersionLabel('lumpy-release/R27-3773.0.0')
        self.assertIsInstance(label.value, provision.CrosVersion)


class CrosVersionTestCase(unittest.TestCase):
    """CrosVersion test case."""

    def test_cros_image_identity(self):
        """Test that CrosVersion doesn't change string value."""
        cros_image = provision.CrosVersion('lumpy-release/R27-3773.0.0')
        self.assertEqual(cros_image, 'lumpy-release/R27-3773.0.0')

    def test_cros_image_group(self):
        """Test CrosVersion group property."""
        cros_image = provision.CrosVersion('lumpy-release/R27-3773.0.0')
        self.assertEqual(cros_image.group, 'lumpy-release')

    def test_cros_image_group_na(self):
        """Test invalid CrosVersion group property."""
        cros_image = provision.CrosVersion('foo')
        self.assertEqual(cros_image.group, cros_image.INVALID_STR)

    def test_cros_image_milestone(self):
        """Test CrosVersion milestone property."""
        cros_image = provision.CrosVersion('lumpy-release/R27-3773.0.0')
        self.assertEqual(cros_image.milestone, 'R27')

    def test_cros_image_milestone_na(self):
        """Test invalid CrosVersion milestone property."""
        cros_image = provision.CrosVersion('foo')
        self.assertEqual(cros_image.milestone, cros_image.INVALID_STR)

    def test_cros_image_milestone_latest(self):
        """Test that LATEST milestone isn't recognized."""
        cros_image = provision.CrosVersion('lumpy-release/LATEST-3773.0.0')
        self.assertEqual(cros_image.milestone, cros_image.INVALID_STR)

    def test_cros_image_version(self):
        """Test CrosVersion image property."""
        cros_image = provision.CrosVersion('lumpy-release/R27-3773.0.0')
        self.assertEqual(cros_image.version, '3773.0.0')

    def test_cros_image_version_na(self):
        """Test invalid CrosVersion version property."""
        cros_image = provision.CrosVersion('foo')
        self.assertEqual(cros_image.version, cros_image.INVALID_STR)

    def test_cros_image_rc(self):
        """Test CrosVersion rc property."""
        cros_image = provision.CrosVersion('lumpy-release/R27-3773.0.0-rc2')
        self.assertEqual(cros_image.rc, 'rc2')

    def test_cros_image_rc_na(self):
        """Test invalid CrosVersion rc property."""
        cros_image = provision.CrosVersion('foo')
        self.assertEqual(cros_image.rc, cros_image.INVALID_STR)

    def test_cros_image_repr(self):
        """Test CrosVersion.__repr__ works."""
        cros_image = provision.CrosVersion('lumpy-release/R27-3773.0.0-rc2')
        self.assertEqual(repr(cros_image),
                         "CrosVersion('lumpy-release/R27-3773.0.0-rc2')")


if __name__ == '__main__':
    unittest.main()
