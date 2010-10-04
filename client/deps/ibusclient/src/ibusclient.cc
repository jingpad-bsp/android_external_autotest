// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <assert.h>
#include <glib.h>
#include <ibus.h>
#include <stdio.h>
#include <stdlib.h>
#include <string>

namespace {

const gchar kDummySection[] = "aaa/bbb";
const gchar kDummyConfigName[] = "ccc";

const gboolean kDummyValueBoolean = TRUE;
const gint kDummyValueInt = 12345;
const gdouble kDummyValueDouble = 2345.5432;
const gchar kDummyValueString[] = "dummy value";

const size_t kArraySize = 3;
const gboolean kDummyValueBooleanArray[kArraySize] = { FALSE, TRUE, FALSE };
const gint kDummyValueIntArray[kArraySize] = { 123, 234, 345 };
const gdouble kDummyValueDoubleArray[kArraySize] = { 111.22, 333.44, 555.66 };
const gchar* kDummyValueStringArray[kArraySize] = {
  "DUMMY_VALUE 1", "DUMMY_VALUE 2", "DUMMY_VALUE 3",
};

const char kGeneralSectionName[] = "general";
const char kPreloadEnginesConfigName[] = "preload_engines";

// Converts |list_type_string| into its element type (e.g. "int_list" to "int").
std::string GetElementType(const std::string& list_type_string) {
  const std::string suffix = "_list";
  if (list_type_string.length() > suffix.length()) {
    return list_type_string.substr(
        0, list_type_string.length() - suffix.length());
  }
  return list_type_string;
}

// Converts |type_string| into GType.
GType GetGValueTypeFromStringOrDie(const std::string& type_string) {
  if (type_string == "boolean") {
    return G_TYPE_BOOLEAN;
  } else if (type_string == "int") {
    return G_TYPE_INT;
  } else if (type_string == "double") {
    return G_TYPE_DOUBLE;
  } else if (type_string == "string") {
    return G_TYPE_STRING;
  } else if (GetElementType(type_string) != type_string) {
    return G_TYPE_VALUE_ARRAY;
  }
  printf("FAIL (unknown type: %s)\n", type_string.c_str());
  abort();
}

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

  const GType gtype = GetGValueTypeFromStringOrDie(type_string);
  g_value_init(&gvalue, gtype);
  if (gtype == G_TYPE_BOOLEAN) {
    g_value_set_boolean(&gvalue, kDummyValueBoolean);
  } else if (gtype == G_TYPE_INT) {
    g_value_set_int(&gvalue, kDummyValueInt);
  } else if (gtype == G_TYPE_DOUBLE) {
    g_value_set_double(&gvalue, kDummyValueDouble);
  } else if (gtype == G_TYPE_STRING) {
    g_value_set_string(&gvalue, kDummyValueString);
  } else if (gtype == G_TYPE_VALUE_ARRAY) {
    // Process list types.
    GValueArray* array = g_value_array_new(kArraySize);

    const GType element_gtype
        = GetGValueTypeFromStringOrDie(GetElementType(type_string));
    g_assert(element_gtype != G_TYPE_VALUE_ARRAY);

    for (size_t i = 0; i < kArraySize; ++i) {
      GValue tmp = {0};
      g_value_init(&tmp, element_gtype);
      if (element_gtype ==  G_TYPE_BOOLEAN) {
        g_value_set_boolean(&tmp, kDummyValueBooleanArray[i]);
      } else if (element_gtype == G_TYPE_INT) {
        g_value_set_int(&tmp, kDummyValueIntArray[i]);
      } else if (element_gtype == G_TYPE_DOUBLE) {
        g_value_set_double(&tmp, kDummyValueDoubleArray[i]);
      } else if (element_gtype == G_TYPE_STRING) {
        g_value_set_string(&tmp, kDummyValueStringArray[i]);
      }
      g_value_array_append(array, &tmp);
    }

    g_value_take_boxed(&gvalue, array);
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

  const GType gtype = GetGValueTypeFromStringOrDie(type_string);
  if (G_VALUE_TYPE(&gvalue) != gtype) {
    printf("FAIL (type mismatch)\n");
    return;
  }

  if (gtype== G_TYPE_BOOLEAN) {
    if (g_value_get_boolean(&gvalue) != kDummyValueBoolean) {
      printf("FAIL (value mismatch)\n");
      return;
    }
  } else if (gtype == G_TYPE_INT) {
    if (g_value_get_int(&gvalue) != kDummyValueInt) {
      printf("FAIL (value mismatch)\n");
      return;
    }
  } else if (gtype == G_TYPE_DOUBLE) {
    if (g_value_get_double(&gvalue) != kDummyValueDouble) {
      // Note: ibus-gconf does not pass this test since it converts a double
      // value into string to store it on GConf storage. If you want to use
      // desktopui_IBusTest against ibus-gconf, you have to rewrite the
      // condition to allow errors.
      printf("FAIL (value mismatch)\n");
      return;
    }
  } else if (gtype == G_TYPE_STRING) {
    if (g_value_get_string(&gvalue) != std::string(kDummyValueString)) {
      printf("FAIL (value mismatch)\n");
      return;
    }
  } else if (gtype == G_TYPE_VALUE_ARRAY) {
    // Process list types
    GValueArray* array
        = reinterpret_cast<GValueArray*>(g_value_get_boxed(&gvalue));
    if (!array || (array->n_values != kArraySize)) {
      printf("FAIL (invalid array)\n");
      return;
    }

    const GType element_gtype
        = GetGValueTypeFromStringOrDie(GetElementType(type_string));
    g_assert(element_gtype != G_TYPE_VALUE_ARRAY);

    for (size_t i = 0; i < kArraySize; ++i) {
      const GValue* element = &(array->values[i]);
      if (G_VALUE_TYPE(element) != element_gtype) {
        printf("FAIL (list type mismatch)\n");
        return;
      }
      bool match = false;
      if ((element_gtype ==  G_TYPE_BOOLEAN) &&
          (g_value_get_boolean(element) == kDummyValueBooleanArray[i])) {
        match = true;
      } else if ((element_gtype == G_TYPE_INT) &&
                 (g_value_get_int(element) == kDummyValueIntArray[i])) {
        match = true;
      } else if ((element_gtype == G_TYPE_DOUBLE) &&
                 (g_value_get_double(element) == kDummyValueDoubleArray[i])) {
        // See my comment about ibus-gconf above.
        match = true;
      } else if ((element_gtype == G_TYPE_STRING) &&
                 (g_value_get_string(element)
                  == std::string(kDummyValueStringArray[i]))) {
        match = true;
      }
      if (!match) {
        printf("FAIL (value mismatch)\n");
        return;
      }
    }
  }

  printf("OK\n");
}

// Prints out the array held in gvalue.  It is assumed that the array contains
// G_TYPE_STRING values.
// On success, returns true
// On failure, prints out "FAIL (error message)" and returns false
bool PrintArray(GValue* gvalue) {
  GValueArray* array =
      reinterpret_cast<GValueArray*>(g_value_get_boxed(gvalue));
  for (guint i = 0; array && (i < array->n_values); ++i) {
    const GType element_type = G_VALUE_TYPE(&(array->values[i]));
    if (element_type != G_TYPE_STRING) {
      printf("FAIL (Array element type is not STRING)\n");
      return false;
    }
    const char* value = g_value_get_string(&(array->values[i]));
    if (!value) {
      printf("FAIL (Array element type is NULL)\n");
      return false;
    }
    printf("%s\n", value);
  }
  return true;
}

// Print out the list of unused config variables from ibus.
// On failure, prints out "FAIL (error message)" instead.
void PrintUnused(IBusConfig* ibus_config) {
  GValue unread = {0};
  GValue unwritten = {0};
  if (!ibus_config_get_unused(ibus_config, &unread, &unwritten)) {
    printf("FAIL (get_unused failed)\n");
    return;
  }

  if (G_VALUE_TYPE(&unread) != G_TYPE_VALUE_ARRAY) {
    printf("FAIL (unread is not an array)\n");
    return;
  }

  if (G_VALUE_TYPE(&unwritten) != G_TYPE_VALUE_ARRAY) {
    printf("FAIL (unwritten is not an array)\n");
    return;
  }

  printf("Unread:\n");
  if (!PrintArray(&unread)) {
    g_value_unset(&unread);
    g_value_unset(&unwritten);
    return;
  }

  printf("Unwritten:\n");
  if (!PrintArray(&unwritten)) {
    g_value_unset(&unread);
    g_value_unset(&unwritten);
    return;
  }

  g_value_unset(&unread);
  g_value_unset(&unwritten);
  return;
}

// Set the preload engines to those named in the array |engines| of size
// |num_engines| and prints the result.
//
// Note that this only fails if it can't set the config value; it does not check
// that the names of the engines are valid.
void PreloadEnginesAndPrintResult(IBusConfig* ibus_config, int num_engines,
                                  char** engines) {
  GValue gvalue = {0};
  g_value_init(&gvalue, G_TYPE_VALUE_ARRAY);
  GValueArray* array = g_value_array_new(num_engines);
  for (int i = 0; i < num_engines; ++i) {
    GValue array_element = {0};
    g_value_init(&array_element, G_TYPE_STRING);
    g_value_set_string(&array_element, engines[i]);
    g_value_array_append(array, &array_element);
  }
  g_value_take_boxed(&gvalue, array);

  if (ibus_config_set_value(ibus_config, kGeneralSectionName,
                            kPreloadEnginesConfigName, &gvalue)) {
    printf("OK\n");
  } else {
    printf("FAIL\n");
  }

  g_value_unset(&gvalue);
}

// Sets |engine_name| as the active IME engine.
void ActivateEngineAndPrintResult(IBusBus* ibus, const char* engine_name) {
  if (!ibus_bus_set_global_engine(ibus, engine_name)) {
    printf("FAIL (could not start engine)\n");
  } else {
    printf("OK\n");
  }
}

// Prints the name of the active IME engine.
void PrintActiveEngine(IBusBus* ibus) {
  IBusEngineDesc* engine_desc = ibus_bus_get_global_engine(ibus);
  if (engine_desc) {
    printf("%s\n", engine_desc->name);
    g_object_unref(engine_desc);
  } else {
    printf("FAIL (Could not get active engine)\n");
  }
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
  // TODO(yusukes): Add 2 parameters, config_key and config_value, to
  // set_config and get_config commands.
  printf("set_config (boolean|int|double|string|\n"
         "            boolean_list|int_list|double_list|string_list)\n"
         "                     Set a dummy value to ibus config service\n");
  printf("get_config (boolean|int|double|string\n"
         "            boolean_list|int_list|double_list|string_list)\n"
         "                     Get a dummy value from ibus config service\n");
  // TODO(yusukes): Add config_key parameter to unset_config.
  printf("unset_config         Unset a dummy value from ibus config service\n");
  printf("get_unused           List all keys that never were used.\n");
  printf("preload_engines      Preload the listed engines.\n");
  printf("activate_engine      Activate the specified engine.\n");
  printf("get_active_engine    Print the name of the current active engine.\n");
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
  } else if (command == "get_unused") {
    PrintUnused(ibus_config);
  } else if (command == "preload_engines") {
    if (argc < 3) {
      PrintUsage(argv[0]);
      return 1;
    }
    PreloadEnginesAndPrintResult(ibus_config, argc-2, &(argv[2]));
  } else if (command == "activate_engine") {
    if (argc != 3) {
      PrintUsage(argv[0]);
      return 1;
    }
    ActivateEngineAndPrintResult(ibus, argv[2]);
  } else if (command == "get_active_engine") {
    PrintActiveEngine(ibus);
  } else {
    PrintUsage(argv[0]);
    return 1;
  }

  return 0;
}
