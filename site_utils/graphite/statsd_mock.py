#pylint: disable-msg=C0111

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class Connection:
    """Mock class for statsd.Connection"""
    def __init__(self, host, port):
        pass


    @classmethod
    def set_defaults(cls, host, port):
        pass


class statsd_mock_base(object):
    """Base class for a mock statsd class."""
    def __init__(self, name, bare=False):
        pass


    def __getattribute__(self, name):
        def any_call(*args, **kwargs):
            pass

        def decorate(f):
            return f

        if name == 'decorate':
            return decorate

        return any_call


class Average(statsd_mock_base):
    """Mock class for statsd.Average."""


class Counter(statsd_mock_base):
    """Mock class for statsd.Counter."""


class Gauge(statsd_mock_base):
    """Mock class for statsd.Gauge."""


class Timer(statsd_mock_base):
    """Mock class for statsd.Timer."""


    def __enter__(self):
        pass


    def __exit__(self):
        pass


class Raw(statsd_mock_base):
    """Mock class for statsd.Raw."""
