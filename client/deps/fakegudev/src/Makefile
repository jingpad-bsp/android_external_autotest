# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

PKG_CONFIG ?= pkg-config
PKGS := gudev-1.0 glib-2.0
PKG_CFLAGS := $(shell ${PKG_CONFIG} --cflags $(PKGS))
PKG_LIBS := $(shell ${PKG_CONFIG} --libs $(PKGS))
WARN := -Werror -Wall
DEBUG := -g -DFAKE_G_UDEV_DEBUG
OPT := -O2

all: gudev-exercise libfakegudev.so
.PHONY: clean all install

gudev-exercise: gudev-exercise.c
	$(CC) -o $@ $(WARN) $(OPT) $(DEBUG) $(PKG_CFLAGS) $< $(PKG_LIBS)

libfakegudev.so: fakegudev.c
	$(CC) -fPIC -shared -o $@ $(WARN) $(OPT) $(DEBUG) $(PKG_CFLAGS) $< -ldl

install:
	install -m 0755 -d $(DESTDIR)/lib
	install -m 0755 libfakegudev.so $(DESTDIR)/lib

clean:
	rm -f core gudev-exercise *.o *.so
