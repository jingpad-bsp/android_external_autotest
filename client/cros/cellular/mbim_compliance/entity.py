# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class Entity(object):
    """
    A common base class for tests / sequences / assertions.

    This class serves as a common base class for all entities in the test. This
    allows us to filter out objects that are part of the tests easily. All
    tests, sequences and assertions should inherit from this class. They will
    likely do so by defining their own base class that inherits from this.

    """
    pass
