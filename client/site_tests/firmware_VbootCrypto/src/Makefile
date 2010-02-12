# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

VBOOT_REFERENCE_DIR = $(GCLIENT_ROOT)/src/platform/vboot_reference
BUILD_TEST_DIR = vboot_reference

all: 
        # Copy test sources into a temporary directory for building.
	rm -rf $(BUILD_TEST_DIR)
	cp -r $(VBOOT_REFERENCE_DIR) .
        # Always build from scratch.
	$(MAKE) -C $(BUILD_TEST_DIR) clean all
        # Move test binaries for use by the tests.
	mv $(BUILD_TEST_DIR)/tests/sha_tests ../sha_tests
        # Delete sources.
	rm -rf $(BUILD_TEST_DIR)

clean:
	rm -f ../sha_tests
