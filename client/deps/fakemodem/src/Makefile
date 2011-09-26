# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

PKGS := glib-2.0 dbus-glib-1
PKG_CFLAGS := $(shell pkg-config --cflags $(PKGS))
PKG_LIBS := $(shell pkg-config --libs $(PKGS))
WARN := -Werror -Wall
DEBUG := -g
OPT   := -O2

all: fakemodem fakenet
.PHONY: all clean install

fakemodem: fakemodem.c fakemodem-dbus.h
	$(CC) -o $@ $(WARN) $(OPT) $(DEBUG) $(PKG_CFLAGS) $< $(PKG_LIBS)

fakemodem-dbus.h: fakemodem-dbus.xml
	dbus-binding-tool --mode=glib-server --prefix=fakemodem \
		$< > $@.tmp
	mv $@.tmp $@

fakenet: fakenet.c
	$(CC) -o $@ $(WARN) $(OPT) $(DEBUG)  $<

install:
	install -m 0755 -d $(DESTDIR)/bin
	install -m 0755 fakemodem fakenet $(DESTDIR)/bin

clean:
	rm -f core fakemodem fakenet *.o *.so fakemodem-dbus.h
