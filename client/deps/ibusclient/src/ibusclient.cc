// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <assert.h>
#include <glib.h>
#include <ibus.h>
#include <stdio.h>
#include <string>

// Prints the names of the given engines. Takes the ownership of |engines|.
void PrintEngineNames(GList* engines) {
  for (GList* cursor = engines; cursor; cursor = g_list_next(cursor)) {
    IBusEngineDesc* engine_desc = IBUS_ENGINE_DESC(cursor->data);
    assert(engine_desc);
    printf("%s\n", engine_desc->name);
    g_object_unref(IBUS_ENGINE_DESC(cursor->data));
  }
  g_list_free(engines);
}

int main(int argc, char **argv) {
  if (argc == 1) {
    printf("Usage: %s COMMAND\n", argv[0]);
    printf("check_reachable      Check if ibus-daemon is reachable\n");
    printf("list_engines         List engine names (all engines)\n");
    printf("list_active_engines  List active engine names\n");
    return 1;
  }

  ibus_init();
  bool connected = false;
  IBusBus* ibus = ibus_bus_new();
  if (ibus) {
    connected = ibus_bus_is_connected(ibus);
  }

  const std::string command = argv[1];
  if (command == "check_reachable") {
    printf("%s\n", connected ? "YES" : "NO");
  }

  // Other commands need the bus to be connected.
  assert(ibus);
  assert(connected);
  if (command == "list_engines") {
    PrintEngineNames(ibus_bus_list_engines(ibus));
  } else if (command == "list_active_engines") {
    PrintEngineNames(ibus_bus_list_active_engines(ibus));
  }

  return 0;
}
