# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Socket utilities for Recall server.

This module should not be imported directly, instead the public classes
are imported directly into the top-level recall package.
"""

__all__ = ["GetOriginalDestinationAddress"]

import socket
import struct


SO_ORIGINAL_DST = 80
SOCKADDR_IN = "!2xH4s8x"
SOCKADDR_IN_LEN = 16

def GetOriginalDestinationAddress(conn):
  """Get the original destination address of a connection.

  When connections undergo iptables redirection, the kernel stores the
  original destination address and port as a socket option. This method
  retrieves that.

  Args:
      conn: Socket to lookup.

  Returns:
      tuple of original address as string and port as integer
      or None if no original destination was found.
  """
  try:
    original_dst_addr \
        = conn.getsockopt(socket.SOL_IP, SO_ORIGINAL_DST, SOCKADDR_IN_LEN)
    original_port, original_in_addr \
        = struct.unpack(SOCKADDR_IN, original_dst_addr)
    original_addr = socket.inet_ntoa(original_in_addr)

    return original_addr, original_port
  except Exception, e:
    return None
