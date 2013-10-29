/*
 * Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */

#define _GNU_SOURCE /* for RTLD_NEXT in dlfcn.h */

#include <glib.h>
#include <glib-object.h>
#include <gudev/gudev.h>

#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/*
 * The purpose of this library is to override libgudev to return
 * arbitrary results for selected devices, generally for the purposes
 * of testing. Adding the library file to LD_PRELOAD is the general
 * way to accomplish this. The arbitrary results to return are
 * specified in the environment variable GUDEV_PRELOAD as follows:
 *
 * FAKEGUDEV_DEVICES=<name1>=value1:<property_name2>=<value2>::<name3>=<value3>
 *
 * Here, <name1> etc are the names of GUdevDevice properties, and <value1> etc
 * are the associated values.
 *  - '::' is used the separate devices
 *  - ':' is used to separate properties of a device
 *  - <name> can not contain the special character ':'
 *  - <value> can contain ':', but it must be escaped with '\'
 *  - property_<name> are the special GUdevDevice properties that can be obtain
 *    with a call to g_udev_get_property
 *
 * e.g.
 * FAKEGUDEV_DEVICES=device_file=/dev/pts/1:subsystem=tty:name=pts/1:\
 * parent=/dev/pts:property_DEVICE_PROPERTY=123::device_file=/dev/pts/2:\
 * subsystem=tty:sysfs_path=/sys/bus/usb/devices/1-2.0\:5
 *
 * The "parent" property on a device specifies a device path that will be looked
 * up with g_udev_client_query_by_device_file() to find a parent device. This
 * may be a real device that the real libgudev will return a device for, or it
 * may be another fake device handled by this library.
 *
 * Unspecified properties/attributes will be returned as NULL.
 *
 * Setting the environment variable FAKEGUDEV_BLOCK_REAL causes this
 * library to prevent real devices from being iterated over with
 * g_udev_query_by_subsystem().
 */

#ifdef FAKE_G_UDEV_DEBUG
static const char *k_tmp_logging_file_full_path = "/tmp/fakegudev.dbg";
static FILE *debug_file;

#define fake_g_udev_debug_init() \
  debug_file = fopen (k_tmp_logging_file_full_path, "w")

#define fake_g_udev_debug(...) \
  do { \
    if (debug_file) { \
      fprintf (debug_file, __VA_ARGS__); \
      fprintf (debug_file, "\n"); \
    } \
  } while (0)

#define fake_g_udev_debug_finish() \
  do { \
    if (debug_file) { \
      fclose (debug_file); \
      debug_file = NULL; \
    } \
  } while (0)

#else  /* FAKE_G_UDEV_DEBUG */
#define fake_g_udev_debug_init()
#define fake_g_udev_debug(...)
#define fake_g_udev_debug_finish()
#endif  /* FAKE_G_UDEV_DEBUG */


typedef struct _FakeGUdevDeviceClass FakeGUdevDeviceClass;
typedef struct _FakeGUdevDevice FakeGUdevDevice;
typedef struct _FakeGUdevDevicePrivate FakeGUdevDevicePrivate;

#define FAKE_G_UDEV_TYPE_DEVICE (fake_g_udev_device_get_type ())
#define FAKE_G_UDEV_DEVICE(obj) \
    (G_TYPE_CHECK_INSTANCE_CAST ((obj), \
                                 FAKE_G_UDEV_TYPE_DEVICE, \
                                 FakeGUdevDevice))
#define FAKE_G_UDEV_IS_DEVICE(obj) \
    (G_TYPE_CHECK_INSTANCE_TYPE ((obj), \
                                 FAKE_G_UDEV_TYPE_DEVICE))
#define FAKE_G_UDEV_DEVICE_CLASS(klass) \
    (G_TYPE_CHECK_CLASS_CAST ((klass), \
                              FAKE_G_UDEV_TYPE_DEVICE, \
                              FakeGUdevDeviceClass))
#define FAKE_G_UDEV_IS_DEVICE_CLASS(klass) \
    (G_TYPE_CHECK_CLASS_TYPE ((klass), \
                              FAKE_G_UDEV_TYPE_DEVICE))
#define FAKE_G_UDEV_DEVICE_GET_CLASS(obj) \
    (G_TYPE_INSTANCE_GET_CLASS ((obj), \
                                FAKE_G_UDEV_TYPE_DEVICE, \
                                FakeGUdevDeviceClass))

struct _FakeGUdevDevice
{
  GUdevDevice parent;
  FakeGUdevDevicePrivate *priv;
};

struct _FakeGUdevDeviceClass
{
  GUdevDeviceClass parent_class;
};

GType fake_g_udev_device_get_type (void) G_GNUC_CONST;

/* end header */

struct _FakeGUdevDevicePrivate
{
  GHashTable *properties;
  GUdevClient *client;
  const gchar **propkeys;
};

G_DEFINE_TYPE (FakeGUdevDevice, fake_g_udev_device, G_UDEV_TYPE_DEVICE)


/* Map from device paths (/dev/pts/1) to FakeGUdevDevice objects */
static GHashTable *devices_by_path;

/* Map from sysfs paths (/sys/devices/blah) to FakeGUdevDevice objects */
static GHashTable *devices_by_syspath;

/* Map which acts as a set of FakeGUdevDevice objects */
static GHashTable *devices_by_ptr;

/* Prevent subsystem query from listing devices */
static gboolean block_real = FALSE;

static const char *k_env_devices = "FAKEGUDEV_DEVICES";
static const char *k_env_block_real = "FAKEGUDEV_BLOCK_REAL";
static const char *k_prop_device_file = "device_file";
static const char *k_prop_devtype = "devtype";
static const char *k_prop_driver = "driver";
static const char *k_prop_name = "name";
static const char *k_prop_parent = "parent";
static const char *k_prop_subsystem = "subsystem";
static const char *k_prop_sysfs_path = "sysfs_path";
static const char *k_property_prefix = "property_";
static const char *k_sysfs_attr_prefix = "sysfs_attr_";

static const char *k_func_q_device_file = "g_udev_client_query_by_device_file";
static const char *k_func_q_sysfs_path = "g_udev_client_query_by_sysfs_path";
static const char *k_func_q_by_subsystem = "g_udev_client_query_by_subsystem";
static const char *k_func_q_by_subsystem_and_name =
    "g_udev_client_query_by_subsystem_and_name";
static const char *k_func_get_device_file = "g_udev_device_get_device_file";
static const char *k_func_get_devtype = "g_udev_device_get_devtype";
static const char *k_func_get_driver = "g_udev_device_get_driver";
static const char *k_func_get_name = "g_udev_device_get_name";
static const char *k_func_get_parent = "g_udev_device_get_parent";
static const char *k_func_get_property = "g_udev_device_get_property";
static const char *k_func_get_property_keys = "g_udev_device_get_property_keys";
static const char *k_func_get_subsystem = "g_udev_device_get_subsystem";
static const char *k_func_get_sysfs_path = "g_udev_device_get_sysfs_path";
static const char *k_func_get_sysfs_attr = "g_udev_device_get_sysfs_attr";

static void
abort_on_error (GError *error) {
  if (!error)
    return;

  fake_g_udev_debug ("Aborting on error: |%s|\n", error->message);
  fake_g_udev_debug_finish ();
  g_assert (0);
}

static void
parse_fake_devices (const char *orig_ev)
{
  gchar **devices, **device_iter;
  gchar *buf;

  GRegex *device_delimiter, *property_delimiter, *key_value_delimiter;
  GRegex *escaped_colon;
  GError *error = NULL;

  fake_g_udev_debug ("devices_string: |%s|\n", orig_ev);

  device_delimiter = g_regex_new ("(?:([^\\\\])::)|(?:^::)", 0, 0, &error);
  abort_on_error (error);
  property_delimiter = g_regex_new ("(?:([^\\\\]):)|(?:^:)", 0, 0, &error);
  abort_on_error (error);
  key_value_delimiter = g_regex_new ("=", 0, 0, &error);
  abort_on_error (error);
  escaped_colon = g_regex_new ("(?:([^\\\\])(\\\\:))|(?:^\\\\:)", 0, 0, &error);
  abort_on_error (error);

  buf = g_regex_replace (device_delimiter, orig_ev, -1, 0, "\\1;", 0, &error);
  abort_on_error (error);
  devices = g_strsplit (buf, ";", 0);
  g_free (buf);

  for (device_iter = devices; *device_iter; ++device_iter) {
    FakeGUdevDevice *fake_device;
    gchar **properties, **properties_iter;

    fake_g_udev_debug ("Parsing device: |%s|\n", *device_iter);
    if (strlen (*device_iter) == 0)
      continue;

    fake_device = FAKE_G_UDEV_DEVICE (g_object_new (FAKE_G_UDEV_TYPE_DEVICE,
                                                    NULL));
    g_hash_table_insert (devices_by_ptr, g_object_ref (fake_device), NULL);

    buf = g_regex_replace (property_delimiter, *device_iter, -1, 0, "\\1;", 0,
                           &error);
    properties = g_strsplit (buf, ";", 0);
    abort_on_error (error);
    g_free (buf);

    for (properties_iter = properties; *properties_iter; ++properties_iter) {
      gchar **parts;
      gchar *name, *value;

      fake_g_udev_debug ("Parsing property: |%s|\n", *properties_iter);
      if (strlen (*properties_iter) == 0)
        continue;

      parts = g_regex_split (key_value_delimiter, *properties_iter, 0);
      if (g_strv_length (parts) != 2) {
        fake_g_udev_debug ("Error parsing device.\n");
        fake_g_udev_debug ("Failed to parse property: |%s|\n",
                           *properties_iter);
        fake_g_udev_debug ("From the device: |%s|\n", *device_iter);
        g_strfreev (parts);
        continue;
      }

      name = parts[0];
      /* Any ':' in |value| has to be escaped with a '\' to allow for ':' and
       * '::' to act as delimiters.
       * Clean away the '\' before storing the property.
       */
      value = g_regex_replace (escaped_colon, parts[1], -1, 0, "\\1:", 0,
                               &error);
      abort_on_error (error);
      fake_g_udev_debug ("Sanitized property: |%s|\n",
                         value);

      g_hash_table_insert (fake_device->priv->properties, g_strdup (name),
                           g_strdup (value));
      if (g_strcmp0 (name, k_prop_device_file) == 0) {
        g_hash_table_insert (devices_by_path,
                             g_strdup (value),
                             g_object_ref (fake_device));
      }
      if (g_strcmp0 (name, k_prop_sysfs_path) == 0) {
        g_hash_table_insert (devices_by_syspath,
                             g_strdup (value),
                             g_object_ref (fake_device));
      }

      g_free (value);
      g_strfreev (parts);
    }

    g_strfreev (properties);
  }

  g_strfreev (devices);
  g_regex_unref (device_delimiter);
  g_regex_unref (property_delimiter);
  g_regex_unref (key_value_delimiter);
  g_regex_unref (escaped_colon);
}

/*
 * Don't initialize the global data in this library using the library
 * constructor. GLib may not be setup when this library is loaded.
 */
static void
g_udev_preload_init (void)
{
  const char *orig_ev;

  /* global tables */
  devices_by_path = g_hash_table_new_full (g_str_hash, g_str_equal,
                                           g_free, g_object_unref);
  devices_by_syspath = g_hash_table_new_full (g_str_hash, g_str_equal,
                                              g_free, g_object_unref);
  devices_by_ptr = g_hash_table_new_full (NULL, NULL, g_object_unref, NULL);

  orig_ev = getenv (k_env_devices);
  if (orig_ev == NULL)
    orig_ev = "";
  parse_fake_devices (orig_ev);

  if (getenv (k_env_block_real))
    block_real = TRUE;
}

/* If |device| is a FakeGUdevDevice registered earlier with the libarary, cast
 * |device| into a FakeGUdevDevice, otherwise return NULL
 */
static FakeGUdevDevice *
get_fake_g_udev_device (GUdevDevice *device)
{
  FakeGUdevDevice *fake_device;

  if (devices_by_ptr == NULL)
    g_udev_preload_init ();

  if (!FAKE_G_UDEV_IS_DEVICE (device))
    return NULL;
  fake_device = FAKE_G_UDEV_DEVICE (device);

  g_return_val_if_fail (
      g_hash_table_lookup_extended (devices_by_ptr, fake_device, NULL, NULL),
      NULL);
  return fake_device;
}

void __attribute__ ((constructor))
fake_g_udev_init (void)
{
  fake_g_udev_debug_init ();
  fake_g_udev_debug ("Initialized FakeGUdev library.\n");
}

void __attribute__ ((destructor))
fake_g_udev_fini (void)
{
  if (devices_by_path)
    g_hash_table_unref (devices_by_path);
  if (devices_by_syspath)
    g_hash_table_unref (devices_by_syspath);
  if (devices_by_ptr)
    g_hash_table_unref (devices_by_ptr);
  fake_g_udev_debug ("Quit FakeGUdev library.\n");
  fake_g_udev_debug_finish ();
}

GList *
g_udev_client_query_by_subsystem (GUdevClient *client, const gchar *subsystem)
{
  static GList* (*realfunc)();
  GHashTableIter iter;
  gpointer key, value;
  GList *list, *reallist;

  if (devices_by_path == NULL)
    g_udev_preload_init ();

  list = NULL;
  g_hash_table_iter_init (&iter, devices_by_path);
  while (g_hash_table_iter_next (&iter, &key, &value)) {
    FakeGUdevDevice *fake_device = value;
    const gchar *dev_subsystem =
        (const gchar *)g_hash_table_lookup (fake_device->priv->properties,
                                            k_prop_subsystem);
    if (strcmp (subsystem, dev_subsystem) == 0)
      list = g_list_append (list, G_UDEV_DEVICE (fake_device));
  }

  if (!block_real) {
    if (realfunc == NULL)
      realfunc = (GList *(*)()) dlsym (RTLD_NEXT, k_func_q_by_subsystem);
    reallist = realfunc (client, subsystem);
    list = g_list_concat (list, reallist);
  }

  return list;
}

/*
 * This is our hook. We look for a particular device path
 * and return a special pointer.
 */
GUdevDevice *
g_udev_client_query_by_device_file (GUdevClient *client,
                                    const gchar *device_file)
{
  static GUdevDevice* (*realfunc)();
  FakeGUdevDevice *fake_device;

  if (devices_by_path == NULL)
    g_udev_preload_init ();

  if (g_hash_table_lookup_extended (devices_by_path,
                                    device_file,
                                    NULL,
                                    (gpointer *)&fake_device)) {
    /* Stash the client pointer for later use in _get_parent() */
    fake_device->priv->client = client;
    return g_object_ref (G_UDEV_DEVICE (fake_device));
  }

  if (realfunc == NULL)
    realfunc = (GUdevDevice *(*)()) dlsym (RTLD_NEXT, k_func_q_device_file);
  return realfunc (client, device_file);
}

GUdevDevice *
g_udev_client_query_by_sysfs_path (GUdevClient *client,
                                   const gchar *sysfs_path)
{
  static GUdevDevice* (*realfunc)();
  FakeGUdevDevice *fake_device;

  if (devices_by_path == NULL)
    g_udev_preload_init ();

  if (g_hash_table_lookup_extended (devices_by_syspath, sysfs_path, NULL,
                                    (gpointer *)&fake_device)) {
    /* Stash the client pointer for later use in _get_parent() */
    fake_device->priv->client = client;
    return g_object_ref (G_UDEV_DEVICE (fake_device));
  }

  if (realfunc == NULL)
    realfunc = (GUdevDevice *(*)()) dlsym (RTLD_NEXT, k_func_q_sysfs_path);
  return realfunc (client, sysfs_path);
}


GUdevDevice *
g_udev_client_query_by_subsystem_and_name (GUdevClient *client,
                                           const gchar *subsystem,
                                           const gchar *name)
{
  static GUdevDevice* (*realfunc)();
  GHashTableIter iter;
  gpointer key, value;

  if (devices_by_path == NULL)
    g_udev_preload_init ();

  g_hash_table_iter_init (&iter, devices_by_path);
  while (g_hash_table_iter_next (&iter, &key, &value)) {
    FakeGUdevDevice *fake_device = value;
    const gchar *dev_subsystem =
        (const gchar *)g_hash_table_lookup (fake_device->priv->properties,
                                            k_prop_subsystem);
    const gchar *dev_name =
        (const gchar *)g_hash_table_lookup (fake_device->priv->properties,
                                            k_prop_name);
    if (dev_subsystem && dev_name &&
        (strcmp (subsystem, dev_subsystem) == 0) &&
        (strcmp (name, dev_name) == 0)) {
      fake_device->priv->client = client;
      return g_object_ref (G_UDEV_DEVICE (fake_device));
    }
  }

  if (realfunc == NULL)
    realfunc = (GUdevDevice *(*)()) dlsym (RTLD_NEXT,
                                           k_func_q_by_subsystem_and_name);
  return realfunc (client, subsystem, name);
}


/*
 * Our device data is a glib hash table with string keys and values;
 * the keys and values are owned by the hash table.
 */

/*
 * For g_udev_device_*() functions, the general drill is to check if
 * the device is "ours", and if not, delegate to the real library
 * method.
 */
const gchar *
g_udev_device_get_device_file (GUdevDevice *device)
{
  static const gchar* (*realfunc)();
  FakeGUdevDevice * fake_device;

  fake_device = get_fake_g_udev_device (device);
  if (fake_device)
    return (const gchar *)g_hash_table_lookup (fake_device->priv->properties,
                                               k_prop_device_file);

  if (realfunc == NULL)
    realfunc = (const gchar *(*)()) dlsym (RTLD_NEXT, k_func_get_device_file);
  return realfunc (device);
}

const gchar *
g_udev_device_get_devtype (GUdevDevice *device)
{
  static const gchar* (*realfunc)();
  FakeGUdevDevice * fake_device;

  fake_device = get_fake_g_udev_device (device);
  if (fake_device)
    return (const gchar *)g_hash_table_lookup (fake_device->priv->properties,
                                               k_prop_devtype);

  if (realfunc == NULL)
    realfunc = (const gchar *(*)()) dlsym (RTLD_NEXT, k_func_get_devtype);
  return realfunc (device);
}

const gchar *
g_udev_device_get_driver (GUdevDevice *device)
{
  static const gchar* (*realfunc)();
  FakeGUdevDevice * fake_device;

  fake_device = get_fake_g_udev_device (device);
  if (fake_device)
    return (const gchar *)g_hash_table_lookup (fake_device->priv->properties,
                                               k_prop_driver);

  if (realfunc == NULL)
    realfunc = (const gchar *(*)()) dlsym (RTLD_NEXT, k_func_get_driver);
  return realfunc (device);
}

const gchar *
g_udev_device_get_name (GUdevDevice *device)
{
  static const gchar* (*realfunc)();
  FakeGUdevDevice * fake_device;

  fake_device = get_fake_g_udev_device (device);
  if (fake_device)
    return (const gchar *)g_hash_table_lookup (fake_device->priv->properties,
                                               k_prop_name);

  if (realfunc == NULL)
    realfunc = (const gchar *(*)()) dlsym (RTLD_NEXT, k_func_get_name);
  return realfunc (device);
}

GUdevDevice *
g_udev_device_get_parent (GUdevDevice *device)
{
  static GUdevDevice* (*realfunc)();
  FakeGUdevDevice * fake_device;

  fake_device = get_fake_g_udev_device (device);
  if (fake_device) {
    const gchar *parent =
        (const gchar *)g_hash_table_lookup (fake_device->priv->properties,
                                            k_prop_parent);
    if (parent == NULL)
      return NULL;
    return g_udev_client_query_by_device_file (fake_device->priv->client,
                                               parent);
  }

  if (realfunc == NULL)
    realfunc = (GUdevDevice *(*)()) dlsym (RTLD_NEXT, k_func_get_parent);
  return realfunc (device);
}

const gchar *
g_udev_device_get_property (GUdevDevice *device,
                            const gchar *key)
{
  static const gchar* (*realfunc)();
  FakeGUdevDevice * fake_device;

  fake_device = get_fake_g_udev_device (device);
  if (fake_device) {
    gchar *propkey = g_strconcat (k_property_prefix, key, NULL);
    const gchar *result =
        (const gchar *)g_hash_table_lookup (fake_device->priv->properties,
                                            propkey);
    g_free (propkey);
    return result;
  }

  if (realfunc == NULL)
    realfunc = (const gchar *(*)()) dlsym (RTLD_NEXT, k_func_get_property);
  return realfunc (device, key);
}

/*
 * All of the g_udev_device_get_property_as_SOMETYPE () functions call
 * g_udev_device_get_property() and then operate on the result, so we
 * don't  need to implement them ourselves, as the real udev will start by
 * calling into our version of g_udev_device_get_property().
  */
#if 0
gboolean
g_udev_device_get_property_as_boolean (GUdevDevice *device,
                                       const gchar *key);
gint
g_udev_device_get_property_as_int (GUdevDevice *device,
                                   const gchar *key);
guint64 g_udev_device_get_property_as_uint64 (FakeGUdevDevice *device,
                                              const gchar  *key);
gdouble g_udev_device_get_property_as_double (FakeGUdevDevice *device,
                                              const gchar  *key);

const gchar* const *g_udev_device_get_property_as_strv (FakeGUdevDevice *device,
                                                        const gchar  *key);
#endif

const gchar * const *
g_udev_device_get_property_keys (GUdevDevice *device)
{
  static const gchar* const* (*realfunc)();
  FakeGUdevDevice * fake_device;

  fake_device = get_fake_g_udev_device (device);
  if (fake_device) {
    const gchar **keys;
    if (fake_device->priv->propkeys)
      return fake_device->priv->propkeys;

    GList *keylist = g_hash_table_get_keys (fake_device->priv->properties);
    GList *key, *prop, *proplist = NULL;
    guint propcount = 0;
    for (key = keylist; key != NULL; key = key->next) {
      if (strncmp ((char *)key->data,
                   k_property_prefix,
                   strlen (k_property_prefix)) == 0) {
        proplist = g_list_prepend (proplist,
                                   key->data + strlen (k_property_prefix));
        propcount++;
      }
    }
    keys = g_malloc ((propcount + 1) * sizeof(*keys));
    keys[propcount] = NULL;
    for (prop = proplist; prop != NULL; prop = prop->next)
      keys[--propcount] = prop->data;
    g_list_free (proplist);
    fake_device->priv->propkeys = keys;

    return keys;
  }

  if (realfunc == NULL)
    realfunc = (const gchar * const*(*)()) dlsym (RTLD_NEXT,
                                                  k_func_get_property_keys);
  return realfunc (device);
}


const gchar *
g_udev_device_get_subsystem (GUdevDevice *device)
{
  static const gchar* (*realfunc)();
  FakeGUdevDevice * fake_device;

  fake_device = get_fake_g_udev_device (device);
  if (fake_device)
    return (const gchar *)g_hash_table_lookup (fake_device->priv->properties,
                                               k_prop_subsystem);

  if (realfunc == NULL)
    realfunc = (const gchar *(*)()) dlsym (RTLD_NEXT, k_func_get_subsystem);
  return realfunc (device);
}

/*
 * The get_sysfs_attr_as_SOMETYPE() functions are also handled magically, as are
 * the get_property_as_SOMETYPE() functions described above.
 */
const gchar *
g_udev_device_get_sysfs_attr (GUdevDevice *device, const gchar *name)
{
  static const gchar* (*realfunc)();
  FakeGUdevDevice * fake_device;

  fake_device = get_fake_g_udev_device (device);
  if (fake_device) {
    gchar *attrkey = g_strconcat (k_sysfs_attr_prefix, name, NULL);
    const gchar *result =
        (const gchar *)g_hash_table_lookup (fake_device->priv->properties,
                                            attrkey);
    g_free (attrkey);
    return result;
  }

  if (realfunc == NULL)
    realfunc = (const gchar *(*)()) dlsym (RTLD_NEXT, k_func_get_sysfs_attr);
  return realfunc (device, name);
}


const gchar *
g_udev_device_get_sysfs_path (GUdevDevice *device)
{
  static const gchar* (*realfunc)();
  FakeGUdevDevice * fake_device;

  fake_device = get_fake_g_udev_device (device);
  if (fake_device)
    return (const gchar *)g_hash_table_lookup (fake_device->priv->properties,
                                               k_prop_sysfs_path);

  if (realfunc == NULL)
    realfunc = (const gchar *(*)()) dlsym (RTLD_NEXT, k_func_get_sysfs_path);
  return realfunc (device);
}

#if 0
/* Not implemented yet */
const gchar *g_udev_device_get_number (FakeGUdevDevice *device);
const gchar *g_udev_device_get_action (FakeGUdevDevice *device);
guint64 g_udev_device_get_seqnum (FakeGUdevDevice *device);
FakeGUdevDeviceType g_udev_device_get_device_type (FakeGUdevDevice *device);
FakeGUdevDeviceNumber g_udev_device_get_device_number (FakeGUdevDevice *device);
const gchar * const *
g_udev_device_get_device_file_symlinks (FakeGUdevDevice *device);
FakeGUdevDevice *
g_udev_device_get_parent_with_subsystem (FakeGUdevDevice *device,
                                         const gchar *subsystem,
                                         const gchar *devtype);
const gchar * const *g_udev_device_get_tags (FakeGUdevDevice *device);
gboolean g_udev_device_get_is_initialized (FakeGUdevDevice *device);
guint64 g_udev_device_get_usec_since_initialized (FakeGUdevDevice *device);
gboolean g_udev_device_has_property (FakeGUdevDevice *device, const gchar *key);
#endif

static void
fake_g_udev_device_init (FakeGUdevDevice *device)
{
  device->priv = G_TYPE_INSTANCE_GET_PRIVATE (device,
                                              FAKE_G_UDEV_TYPE_DEVICE,
                                              FakeGUdevDevicePrivate);

  device->priv->properties = g_hash_table_new_full (g_str_hash,
                                                    g_str_equal,
                                                    g_free,
                                                    g_free);
  device->priv->propkeys = NULL;
  device->priv->client = NULL;
}

static void
fake_g_udev_device_finalize (GObject *object)
{
  FakeGUdevDevice *device = FAKE_G_UDEV_DEVICE (object);

  if (device->priv->client)
    g_object_unref (device->priv->client);
  g_free (device->priv->propkeys);
  g_hash_table_unref (device->priv->properties);
}

static void
fake_g_udev_device_class_init (FakeGUdevDeviceClass *klass)
{
  GObjectClass *gobject_class = (GObjectClass *) klass;

  gobject_class->finalize = fake_g_udev_device_finalize;

  g_type_class_add_private (klass, sizeof (FakeGUdevDevicePrivate));
}
