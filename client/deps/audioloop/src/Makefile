# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


LDFLAGS = -lasound -lcras -lm -lpthread -lrt \
	 -L$(SYSROOT)/lib \
	 -L$(SYSROOT)/usr/lib

CFLAGS = -Wall -Werror -O2 \
	 -I$(SYSROOT)/usr/include

OFILES += libaudiodev.o looptest.o

.PHONY: clean run all install

all: looptest loopback_latency

looptest: $(OFILES)

libaudiodev.o: libaudiodev.c libaudiodev.h

looptest.o: looptest.c libaudiodev.h

loopback_latency: loopback_latency.c

install: looptest
	install -m 0755 looptest $(SYSROOT)/usr/local/bin

run:
	./looptest

clean:
	rm -rf looptest loopback_latency $(OFILES)
