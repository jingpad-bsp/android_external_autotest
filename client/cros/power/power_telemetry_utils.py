# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Helper class for power autotests requiring telemetry devices."""

import logging

CUSTOM_START = 'PowerTelemetryLogger custom start.'
CUSTOM_END = 'PowerTelemetryLogger custom end.'

def start_measurement():
    """Mark the start of power telemetry measurement.

    Optional. Use only once in the client side test that is wrapped in
    power_MeasurementWrapper to help pinpoint exactly where power telemetry
    data should start. PowerTelemetryLogger will trim off excess data before
    this point. If not used, power telemetry data will start right before the
    client side test.
    """
    logging.debug(CUSTOM_START)

def end_measurement():
    """Mark the end of power telemetry measurement.

    Optional. Use only once in the client side test that is wrapped in
    power_MeasurementWrapper to help pinpoint exactly where power telemetry
    data should end. PowerTelemetryLogger will trim off excess data after
    this point. If not used, power telemetry data will end right after the
    client side test.
    """
    logging.debug(CUSTOM_END)
