// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <assert.h>
#include <ibus.h>

int main(int argc, char **argv) {
  ibus_init();
  IBusBus* ibus = ibus_bus_new();
  assert(ibus);
  // This fails if ibus daemon is not running.
  assert(ibus_bus_is_connected(ibus));
  // TODO(satorux): Add more tests.
  return 0;
}
