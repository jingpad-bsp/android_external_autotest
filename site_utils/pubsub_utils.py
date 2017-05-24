# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Script to archive old Autotest results to Google Storage.

Uses gsutil to archive files to the configured Google Storage bucket.
Upon successful copy, the local results directory is deleted.
"""

import logging
import os

from apiclient import discovery
from oauth2client.client import ApplicationDefaultCredentialsError
from oauth2client.client import GoogleCredentials
from autotest_lib.server.hosts import moblab_host

import common

# Cloud service
# TODO(ntang): move this to config.
CLOUD_SERVICE_ACCOUNT_FILE = moblab_host.MOBLAB_SERVICE_ACCOUNT_LOCATION
PUBSUB_SERVICE_NAME = 'pubsub'
PUBSUB_VERSION = 'v1beta2'
PUBSUB_SCOPES = ['https://www.googleapis.com/auth/pubsub']
# number of retry to publish an event.
_PUBSUB_NUM_RETRIES = 3

class PubSubException(Exception):
    """Exception to be raised when the test to push to prod failed."""
    pass


class PubSubClient(object):
    """A generic pubsub client. """
    def __init__(self, credential_file=CLOUD_SERVICE_ACCOUNT_FILE):
        """Constructor for PubSubClient.

        @param credential_file: The credential filename.
        @raises PubSubException if the credential file does not exist or
            corrupted.
        """
        self.credential_file = credential_file
        self.credential = self._get_credential()

    def _get_credential(self):
        """Gets the pubsub service api handle."""
        if not os.path.isfile(self.credential_file):
            logging.error('No credential file found')
            raise PubSubException("Credential file does not exists:"
                    + self.credential_file)
        try:
            credential = GoogleCredentials.from_stream(self.credential_file)
            if credential.create_scoped_required():
                credential = credential.create_scoped(PUBSUB_SCOPES)
            return credential
        except ApplicationDefaultCredentialsError as ex:
            logging.error('Failed to get credential.')
        except:
            logging.error('Failed to get the pubsub service handle.')

        raise PubSubException("Credential file does not exists:"
                + self.credential_file)

    def _get_pubsub_service(self):
        try:
            return discovery.build(PUBSUB_SERVICE_NAME, PUBSUB_VERSION,
                                   credentials=self.credential)
        except:
            logging.error('Failed to get pubsub resource object.')
            raise PubSubException("Failed to get pubsub resource object")

    def publish_notifications(self, topic, messages=[]):
        """Publishes a test result notification to a given pubsub topic.

        @param topic: The Cloud pubsub topic.
        @param messages: A list of notification messages.

        @returns A list of pubsub message ids, and empty if fails.

        @raises PubSubException if failed to publish the notification.
        """
        pubsub = self._get_pubsub_service()
        try:
            body = {'messages': messages}
            resp = pubsub.projects().topics().publish(topic=topic,
                    body=body).execute(num_retries=_PUBSUB_NUM_RETRIES)
            if resp:
                msgIds = resp.get('messageIds')
                if msgIds:
                    logging.debug('Published notification message')
                    return msgIds
        except:
            logging.error('Failed to publish test result notifiation.')
            raise PubSubException("Failed to publish the notifiation.")
