// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <assert.h>
#include <glib.h>
#include <ibus.h>
#include <stdio.h>
#include <string>

namespace {

const gchar kDummySection[] = "aaa/bbb";
const gchar kDummyConfigName[] = "ccc";

const gboolean kDummyValueBoolean = TRUE;
const gint kDummyValueInt = 12345;
const gdouble kDummyValueDouble = 12345.54321;
const gchar kDummyValueString[] = "dummy value";

// Unsets a dummy value from ibus config service.
void UnsetConfigAndPrintResult(IBusConfig* ibus_config) {
  if (ibus_config_unset(ibus_config, kDummySection, kDummyConfigName)) {
    printf("OK\n");
  } else {
    printf("FAIL\n");
  }
}

// Sets a dummy value to ibus config service. You can specify a type of the
// dummy value by |type_string|. "boolean", "int", "double", or "string" are
// allowed.
void SetConfigAndPrintResult(
    IBusConfig* ibus_config, const std::string& type_string) {
  GValue gvalue = {0};

  if (type_string == "boolean") {
    g_value_init(&gvalue, G_TYPE_BOOLEAN);
    g_value_set_boolean(&gvalue, kDummyValueBoolean);
  } else if (type_string == "int") {
    g_value_init(&gvalue, G_TYPE_INT);
    g_value_set_int(&gvalue, kDummyValueInt);
  } else if (type_string == "double") {
    g_value_init(&gvalue, G_TYPE_DOUBLE);
    g_value_set_double(&gvalue, kDummyValueDouble);
  } else if (type_string == "string") {
    g_value_init(&gvalue, G_TYPE_STRING);
    g_value_set_string(&gvalue, kDummyValueString);
  } else {
    printf("FAIL (unknown type: %s)\n", type_string.c_str());
    return;
  }

  if (ibus_config_set_value(
          ibus_config, kDummySection, kDummyConfigName, &gvalue)) {
    printf("OK\n");
  } else {
    printf("FAIL\n");
  }
}

// Gets a dummy value from ibus config service. This function checks if the
// dummy value is |type_string| type.
void GetConfigAndPrintResult(
    IBusConfig* ibus_config, const std::string& type_string) {
  GValue gvalue = {0};
  if (!ibus_config_get_value(
          ibus_config, kDummySection, kDummyConfigName, &gvalue)) {
    printf("FAIL (not found)\n");
    return;
  }

  if (type_string == "boolean") {
    if ((G_VALUE_TYPE(&gvalue) != G_TYPE_BOOLEAN) ||
        (g_value_get_boolean(&gvalue) != kDummyValueBoolean)) {
      printf("FAIL (type/value mismatch)\n");
      return;
    }
  } else if (type_string == "int") {
    if ((G_VALUE_TYPE(&gvalue) != G_TYPE_INT) ||
        (g_value_get_int(&gvalue) != kDummyValueInt)) {
      printf("FAIL (type/value mismatch)\n");
      return;
    }
  } else if (type_string == "double") {
    if ((G_VALUE_TYPE(&gvalue) != G_TYPE_DOUBLE) ||
        // We allow errors for double values.
        (g_value_get_double(&gvalue) < kDummyValueDouble - 0.001) ||
        (g_value_get_double(&gvalue) > kDummyValueDouble + 0.001)) {
      printf("FAIL (type/value mismatch)\n");
      return;
    }
  } else if (type_string == "string") {
    if ((G_VALUE_TYPE(&gvalue) != G_TYPE_STRING) ||
        (g_value_get_string(&gvalue) != std::string(kDummyValueString))) {
      printf("FAIL (type/value mismatch)\n");
      return;
    }
  } else {
    printf("FAIL (unknown type: %s)\n", type_string.c_str());
    return;
  }

  printf("OK\n");
}

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

void PrintUsage(const char* argv0) {
  printf("Usage: %s COMMAND\n", argv0);
  printf("check_reachable      Check if ibus-daemon is reachable\n");
  printf("list_engines         List engine names (all engines)\n");
  printf("list_active_engines  List active engine names\n");
  // TODO(yusukes): Add tests for array of {bool, int, double, string}.
  // TODO(yusukes): Add 2 parameters, config_key and config_value, to
  // set_config and get_config commands.
  printf("set_config (boolean|int|double|string)\n"
         "                     Set a dummy value to ibus config service\n");
  printf("get_config (boolean|int|double|string)\n"
         "                     Get a dummy value from ibus config service\n");
  // TODO(yusukes): Add config_key parameter.
  printf("unset_config         Unset a dummy value from ibus config service\n");
}

}  // namespace

int main(int argc, char **argv) {
  if (argc == 1) {
    PrintUsage(argv[0]);
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
    return 0;
  }

  // Other commands need the bus to be connected.
  assert(ibus);
  assert(connected);
  IBusConnection* ibus_connection = ibus_bus_get_connection(ibus);
  assert(ibus_connection);
  IBusConfig* ibus_config = ibus_config_new(ibus_connection);
  assert(ibus_config);

  if (command == "list_engines") {
    PrintEngineNames(ibus_bus_list_engines(ibus));
  } else if (command == "list_active_engines") {
    PrintEngineNames(ibus_bus_list_active_engines(ibus));
  } else if (command == "set_config") {
    if (argc != 3) {
      PrintUsage(argv[0]);
      return 1;
    }
    SetConfigAndPrintResult(ibus_config, argv[2]);
  } else if (command == "get_config") {
    if (argc != 3) {
      PrintUsage(argv[0]);
      return 1;
    }
    GetConfigAndPrintResult(ibus_config, argv[2]);
  } else if (command == "unset_config") {
    UnsetConfigAndPrintResult(ibus_config);
  }

  return 0;
}
