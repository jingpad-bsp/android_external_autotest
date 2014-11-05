#!/usr/bin/env python

import sys

if len(sys.argv) < 2:
    print "Usage: %s <path>" % sys.argv[0]
    print "For example: $ %s /tmp/screenshot.png" % sys.argv[0]
    print "I can output PNG, JPEG, GIF, and other PIL-supported formats."
    sys.exit(1)

path = sys.argv[1]

# Do some evil.
sys.path.insert(0, "/usr/local/autotest")

from cros.graphics.drm import screenshot

image = screenshot()
image.save(path)
