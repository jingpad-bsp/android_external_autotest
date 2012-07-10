# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import logging.handlers
import socket
import time

from config import rpm_config

LOGGING_FORMAT = rpm_config.get('GENERAL', 'logging_format')
SUBJECT_LINE_FORMAT = rpm_config.get('GENERAL', 'email_subject_line_format')


def set_up_logging(log_filename_format):
    """
    Correctly set up logging to have the correct format/level, log to a file,
    and send out email notifications in case of error level messages.
    """
    log_filename = time.strftime(log_filename_format)
    logging.basicConfig(filename=log_filename, level=logging.INFO,
                        format=LOGGING_FORMAT)
    if rpm_config.getboolean('GENERAL', 'debug'):
        logging.getLogger().setLevel(logging.DEBUG)
    receivers = rpm_config.get('RPM_INFRASTRUCTURE',
                               'email_notification_recipients').split(',')
    subject_line = SUBJECT_LINE_FORMAT % socket.gethostname()
    email_handler = logging.handlers.SMTPHandler('localhost', 'rpm@google.com',
                                                 receivers, subject_line, None)
    email_handler.setLevel(logging.ERROR)
    email_handler.setFormatter(logging.Formatter(LOGGING_FORMAT))
    logging.getLogger('').addHandler(email_handler)