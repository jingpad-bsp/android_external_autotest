# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

CXXFLAGS = -g -Wall -Werror \
	   -I$(SYSROOT)/usr/include/dbus-1.0 \
	   -I$(SYSROOT)/usr/include/glib-2.0 \
	   -I$(SYSROOT)/usr/include/ibus-1.0 \
	   -I$(SYSROOT)/usr/lib/dbus-1.0/include \
	   -I$(SYSROOT)/usr/lib/glib-2.0/include \

LDFLAGS = -L$(SYSROOT)/usr/lib \
	  -libus -lgobject-2.0 -ldbus-1 -lpthread -lrt -lglib-2.0

ibusclient: ibusclient.cc
	$(CXX) $(LDFLAGS) $(CXXFLAGS) $^ -o ../$@
