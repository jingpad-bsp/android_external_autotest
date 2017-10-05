# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections


# Message types.
ACK = 'ack'
ECHO = 'echo'
SHUTDOWN = 'shutdown'

# Message type for container pool communication.
Message = collections.namedtuple('Message', ['type', 'args'])


def ack():
    """Creates a message of type ACK.

    ACK messages are returned by the server to acknowledge receipt and confirm
    that requested operations have taken place.
    """
    return Message(ACK, {})


def echo(msg):
    """Creates an echo message.

    ECHO messages are mainly for testing.  They verify that the service is up
    and running.

    @param msg: An optional string that can be attached to the message.
    """
    return Message(ECHO, {'msg': msg})


def shutdown():
    """Creates a service shutdown message.

    SHUTDOWN messages cause the service to shut down.  See Service.stop().
    """
    return Message(SHUTDOWN, {})
