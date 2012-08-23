# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, logging.handlers, socket
from autotest_lib.client.common_lib import global_config


class SeverityFilter(logging.Filter):
    """Filters out messages of anything other than self._level"""
    def __init__(self, level):
        self._level = level


    def filter(self, record):
        """Causes only messages of |self._level| severity to be logged."""
        return record.levelno == self._level


def create_smtp_handler(section, smtp_section, subject, level):
    """Creates an SMTPHandler for the logging module that will send emails
    of the specified severity to the destination specified in the config file.

    @param section The name of the section in global_config.ini that contains
                   the destination to which we should send email.
    @param smtp_section The name of the section in global_config.ini that
                        contains the SMTP server configuration.
    @param subject The line we should use to prefix the subject line of all
                   emails that are sent out with the returned handler.
    @param level Only send out emails of this severity.
    @return A handler that sends emails to be regestered with a logger.
    """
    hostname = socket.gethostname()
    # if the hostname is a fqdn, take only the first part
    from_address = hostname.partition('.')[0]

    notify_address = global_config.global_config.get_config_value(
            section, "notify_email")

    smtp_server = global_config.global_config.get_config_value(
            smtp_section, "smtp_server")

    smtp_port = global_config.global_config.get_config_value(
            smtp_section, "smtp_port")

    smtp_user = global_config.global_config.get_config_value(
            smtp_section, "smtp_user")

    smtp_password = global_config.global_config.get_config_value(
            smtp_section, "smtp_password")

    if not smtp_user or not smtp_password:
        creds = None
    else:
        creds = (smtp_user, smtp_password)
    if smtp_port:
        smtp_server = (smtp_server, smtp_port)

    handler = logging.handlers.SMTPHandler(smtp_server,
                                           from_address,
                                           [notify_address],
                                           subject,
                                           creds)
    handler.setLevel(level)
    # We want to send mail for the given level, and only the given level.
    # One can add more handlers to send messages for other levels.
    handler.addFilter(SeverityFilter(level))
    handler.setFormatter(
        logging.Formatter('%(asctime)s %(levelname)-5s %(message)s'))
    return handler
