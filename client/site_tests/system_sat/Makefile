# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

CFLAGS = -DHAVE_CONFIG_H -DNDEBUG -DCHECKOPTS -O2
LIBS = -lpthread

OBJS = \
	adler32memcpy.o \
	disk_blocks.o \
	error_diag.o \
	finelock_queue.o \
	logger.o \
	main.o \
	os.o \
	os_factory.o \
	pattern.o \
	queue.o \
	sat.o \
	sat_factory.o \
	worker.o

TARGET = stressapptest


all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $^ $(LIBS) -o $@

%.o: %.cc
	$(CXX) -c $(CFLAGS) $^ -o $@

clean:
	$(RM) $(TARGET) $(OBJS)
