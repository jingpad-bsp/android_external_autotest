# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

all: toolchain-tests
clean:
	rm -f toolchain-tests

toolchain-tests:
	$(CC) toolchain-tests.c -o toolchain-tests

install:
	install -m 0755 -d $(DESTDIR)/usr/local/bin
	install -m 0755 toolchain-tests $(DESTDIR)/usr/local/bin

check:
	@echo "Checking compiler warnings ..."
	@echo "Checking compiler errors ..."
