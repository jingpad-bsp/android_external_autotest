/*
 * Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */

#define _GNU_SOURCE /* for RTLD_NEXT in dlfcn.h */

#include <glib.h>
#include <glib-object.h>

#include <dlfcn.h>
#include <stdlib.h>
#include <string.h>

/*
 * This purpose of this library is to override libgudev to return
 * arbitrary results for selected devices, generally for the purposes
 * of testing. Adding the library file to LD_PRELOAD is the general
 * way to accomplish this. The arbitrary results to return are
 * specified in the environment variable GUDEV_PRELOAD as follows:
 *
 * FAKEGUDEV_DEVICES=device_file=/dev/pts/1:subsystem=tty:name=pts/1:\
 * parent=/dev/pts:property_DEVICE_PROPERTY=123
 *
 * Multiple devices may be specified; each device_file entry starts a
 * new device.  The "parent" property on a device specifies a device
 * path that will be looked up with
 * g_udev_client_query_by_device_file() to find a parent device. This
 * may be a real device that the real libgudev will return a device
 * for, or it may be another fake device handled by this library.
 *
 * Unspecified properties/attributes will be returned as NULL.
 *
 * No mechanism currently exists to escape : and = characters in property names.
 *
 * Setting the environment variable FAKEGUDEV_BLOCK_REAL causes this
 * library to prevent real devices from being iterated over with
 * g_udev_query_by_subsystem().
 */

struct GUdevClient;
typedef struct GUdevClient GUdevClient;

typedef struct _FakeGUdevDevice
{
  GObject             parent;

  /*< private >*/
  GHashTable *properties;
  GUdevClient *client;
  const gchar **propkeys;
} FakeGUdevDevice;

typedef struct _FakeGUdevDeviceClass
{
  GObjectClass parent_class;
} FakeGUdevDeviceClass;

GType g_udev_device_get_type (void) G_GNUC_CONST;


#define FAKE_G_UDEV_TYPE_DEVICE         (fake_g_udev_device_get_type ())
#define FAKE_G_UDEV_DEVICE(o)           \
   (G_TYPE_CHECK_INSTANCE_CAST ((o), FAKE_G_UDEV_TYPE_DEVICE, FakeGUdevDevice))

G_DEFINE_TYPE (FakeGUdevDevice, fake_g_udev_device, G_TYPE_OBJECT)

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
static const char *k_delims = ":=";
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


/* TODO(njw): set up a _fini() routine to free allocated memory */

static void
g_udev_preload_init ()
{
  const char *orig_ev;
  char *ev, *saveptr, *name, *value;
  FakeGUdevDevice *device;

  /* global tables */
  devices_by_path = g_hash_table_new (g_str_hash, g_str_equal);
  devices_by_syspath = g_hash_table_new (g_str_hash, g_str_equal);
  devices_by_ptr = g_hash_table_new (NULL, NULL);

  orig_ev = getenv (k_env_devices);
  if (orig_ev == NULL)
    orig_ev = "";
  ev = g_strdup (orig_ev);

  name = strtok_r (ev, k_delims, &saveptr);
  value = strtok_r (NULL, k_delims, &saveptr);
  device = NULL;

  while (name != NULL && value != NULL) {
    if (strcmp (name, k_prop_device_file) == 0) {
      device = FAKE_G_UDEV_DEVICE (g_object_new (FAKE_G_UDEV_TYPE_DEVICE,
                                                 NULL));
      g_hash_table_insert (devices_by_path, g_strdup (value), device);
      g_hash_table_insert (devices_by_ptr, device, NULL);
    }
    if (device != NULL) {
      g_hash_table_insert (device->properties, g_strdup (name),
                           g_strdup (value));

      if (strcmp (name, k_prop_sysfs_path) == 0)
        g_hash_table_insert (devices_by_syspath, g_strdup (value), device);
    }

    name = strtok_r (NULL, k_delims, &saveptr);
    value = strtok_r (NULL, k_delims, &saveptr);
  }
  g_free (ev);

  if (getenv (k_env_block_real))
    block_real = TRUE;
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
    FakeGUdevDevice *device = value;
    gchar *dev_subsystem =
        (gchar *)g_hash_table_lookup (device->properties, k_prop_subsystem);
    if (strcmp (subsystem, dev_subsystem) == 0)
      list = g_list_append (list, device);
  }

  if (!block_real) {
    if (realfunc == NULL)
      realfunc = (GList *(*)()) dlsym (RTLD_NEXT, k_func_q_by_subsystem);
    reallist = realfunc (client, subsystem);
    list = g_list_concat (list, reallist);
    g_list_free (reallist);
  }

  return list;
}

/*
 * This is our hook. We look for a particular device path
 * and return a special pointer.
 */
FakeGUdevDevice*
g_udev_client_query_by_device_file (GUdevClient *client,
                                    const gchar *device_file)
{
  static FakeGUdevDevice* (*realfunc)();
  FakeGUdevDevice *device;

  if (devices_by_path == NULL)
    g_udev_preload_init ();

  if (g_hash_table_lookup_extended (devices_by_path, device_file, NULL,
                                    (gpointer *)&device)) {
    /* Stash the client pointer for later use in _get_parent() */
    device->client = client;
    return g_object_ref (device);
  }

  if (realfunc == NULL)
    realfunc = (FakeGUdevDevice *(*)()) dlsym (RTLD_NEXT, k_func_q_device_file);
  return realfunc (client, device_file);
}

FakeGUdevDevice*
g_udev_client_query_by_sysfs_path (GUdevClient *client,
                                    const gchar *sysfs_path)
{
  static FakeGUdevDevice* (*realfunc)();
  FakeGUdevDevice *device;

  if (devices_by_path == NULL)
    g_udev_preload_init ();

  if (g_hash_table_lookup_extended (devices_by_syspath, sysfs_path, NULL,
                                    (gpointer *)&device)) {
    /* Stash the client pointer for later use in _get_parent() */
    device->client = client;
    return g_object_ref (device);
  }

  if (realfunc == NULL)
    realfunc = (FakeGUdevDevice *(*)()) dlsym (RTLD_NEXT, k_func_q_sysfs_path);
  return realfunc (client, sysfs_path);
}


FakeGUdevDevice *
g_udev_client_query_by_subsystem_and_name (GUdevClient *client,
                                           const gchar *subsystem,
                                           const gchar *name)
{
  static FakeGUdevDevice* (*realfunc)();
  GHashTableIter iter;
  gpointer key, value;

  if (devices_by_path == NULL)
    g_udev_preload_init ();

  g_hash_table_iter_init (&iter, devices_by_path);
  while (g_hash_table_iter_next (&iter, &key, &value)) {
    FakeGUdevDevice *device = value;
    gchar *dev_subsystem =
        (gchar *)g_hash_table_lookup (device->properties, k_prop_subsystem);
    gchar *dev_name =
        (gchar *)g_hash_table_lookup (device->properties, k_prop_name);
    if (dev_subsystem && dev_name &&
        (strcmp (subsystem, dev_subsystem) == 0) &&
        (strcmp (name, dev_name) == 0)) {
      device->client = client;
      return g_object_ref (device);
    }
  }

  if (realfunc == NULL)
    realfunc = (FakeGUdevDevice *(*)()) dlsym (RTLD_NEXT,
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
g_udev_device_get_device_file (FakeGUdevDevice *device)
{
  static const gchar* (*realfunc)();

  if (devices_by_ptr == NULL)
    g_udev_preload_init ();

  if (g_hash_table_lookup_extended (devices_by_ptr, device, NULL, NULL))
    return (gchar *)g_hash_table_lookup (device->properties,
                                         k_prop_device_file);

  if (realfunc == NULL)
    realfunc = (const gchar *(*)()) dlsym (RTLD_NEXT, k_func_get_device_file);
  return realfunc (device);
}

const gchar *
g_udev_device_get_devtype (FakeGUdevDevice *device)
{
  static const gchar* (*realfunc)();

  if (devices_by_ptr == NULL)
    g_udev_preload_init ();

  if (g_hash_table_lookup_extended (devices_by_ptr, device, NULL, NULL))
    return (gchar *)g_hash_table_lookup (device->properties, k_prop_devtype);

  if (realfunc == NULL)
    realfunc = (const gchar *(*)()) dlsym (RTLD_NEXT, k_func_get_devtype);
  return realfunc (device);
}

const gchar *
g_udev_device_get_driver (FakeGUdevDevice *device)
{
  static const gchar* (*realfunc)();

  if (devices_by_ptr == NULL)
    g_udev_preload_init ();

  if (g_hash_table_lookup_extended (devices_by_ptr, device, NULL, NULL))
    return (gchar *)g_hash_table_lookup (device->properties, k_prop_driver);

  if (realfunc == NULL)
    realfunc = (const gchar *(*)()) dlsym (RTLD_NEXT, k_func_get_driver);
  return realfunc (device);
}

const gchar *
g_udev_device_get_name (FakeGUdevDevice *device)
{
  static const gchar* (*realfunc)();

  if (devices_by_ptr == NULL)
    g_udev_preload_init ();

  if (g_hash_table_lookup_extended (devices_by_ptr, device, NULL, NULL))
    return (gchar *)g_hash_table_lookup (device->properties, k_prop_name);

  if (realfunc == NULL)
    realfunc = (const gchar *(*)()) dlsym (RTLD_NEXT, k_func_get_name);
  return realfunc (device);
}

const FakeGUdevDevice *
g_udev_device_get_parent (FakeGUdevDevice *device)
{
  static const FakeGUdevDevice* (*realfunc)();

  if (devices_by_ptr == NULL)
    g_udev_preload_init ();

  if (g_hash_table_lookup_extended (devices_by_ptr, device, NULL, NULL)) {
    gchar *parent = (gchar *)g_hash_table_lookup (device->properties,
                                                  k_prop_parent);
    if (parent == NULL)
      return NULL;
    return g_udev_client_query_by_device_file (device->client, parent);
  }

  if (realfunc == NULL)
    realfunc = (const FakeGUdevDevice *(*)()) dlsym (RTLD_NEXT,
                                                     k_func_get_parent);
  return realfunc (device);

  return NULL;
}

const gchar *
g_udev_device_get_property (FakeGUdevDevice *device,
                            const gchar *key)
{
  static const gchar* (*realfunc)();

  if (devices_by_ptr == NULL)
    g_udev_preload_init ();

  if (g_hash_table_lookup_extended (devices_by_ptr, device, NULL, NULL)) {
    gchar *propkey = g_strconcat (k_property_prefix, key, NULL);
    const gchar *result = (gchar *)g_hash_table_lookup (device->properties,
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
 * ideally shouldn't need to implement them ourselves, as the real
 * udev will start by calling into our version of
 * g_udev_device_get_property().
 *
 * However, that doesn't work. The _as_SOMETYPE () functions validate
 * the device pointer first (via G_TYPE_CHECK_INSTANCE_TYPE), which
 * segfaults on our non-GObject device pointers. We'd have to fake
 * that out more thoroughly in order to pass.
 */
gboolean
g_udev_device_get_property_as_boolean (FakeGUdevDevice *device,
                                       const gchar *key)
{
  static gboolean (*realfunc)();

  if (devices_by_ptr == NULL)
    g_udev_preload_init ();

  if (g_hash_table_lookup_extended (devices_by_ptr, device, NULL, NULL)) {
    gchar *propkey = g_strconcat (k_property_prefix, key, NULL);
    const gchar *result = (gchar *)g_hash_table_lookup (device->properties,
                                                        propkey);
    g_free (propkey);

    if (result &&
        (strcmp (result, "1") == 0 || g_ascii_strcasecmp (result, "true") == 0))
      return TRUE;
    else
      return FALSE;
  }

  if (realfunc == NULL)
    realfunc = (gboolean (*)()) dlsym (RTLD_NEXT, k_func_get_property);
  return realfunc (device, key);
}

gint
g_udev_device_get_property_as_int (FakeGUdevDevice *device,
                                   const gchar *key)
{
  static gint (*realfunc)();

  if (devices_by_ptr == NULL)
    g_udev_preload_init ();

  if (g_hash_table_lookup_extended (devices_by_ptr, device, NULL, NULL)) {
    gchar *propkey = g_strconcat (k_property_prefix, key, NULL);
    const gchar *result = (gchar *)g_hash_table_lookup (device->properties,
                                                        propkey);
    g_free (propkey);

    return strtol (result, NULL, 0);
  }

  if (realfunc == NULL)
    realfunc = (gint (*)()) dlsym (RTLD_NEXT, k_func_get_property);
  return realfunc (device, key);
}

#if 0
/* Not implemented yet */
guint64 g_udev_device_get_property_as_uint64 (FakeGUdevDevice *device,
                                              const gchar  *key);
gdouble g_udev_device_get_property_as_double (FakeGUdevDevice *device,
                                              const gchar  *key);

const gchar* const *g_udev_device_get_property_as_strv (FakeGUdevDevice *device,
                                                        const gchar  *key);

#endif

const gchar * const *
g_udev_device_get_property_keys (FakeGUdevDevice *device)
{
  static const gchar* const* (*realfunc)();

  if (devices_by_ptr == NULL)
    g_udev_preload_init ();

  if (g_hash_table_lookup_extended (devices_by_ptr, device, NULL, NULL)) {
    const gchar **keys;
    if (device->propkeys)
      return device->propkeys;

    GList *keylist = g_hash_table_get_keys(device->properties);
    GList *key, *prop, *proplist = NULL;
    guint propcount = 0;
    for (key = keylist; key != NULL ; key = key->next) {
      if (strncmp ((char *)key->data, k_property_prefix,
                   strlen (k_property_prefix)) == 0) {
        proplist = g_list_prepend (proplist, key->data +
                                   strlen (k_property_prefix));
        propcount++;
      }
    }
    keys = g_malloc ((propcount + 1) * sizeof(*keys));
    keys[propcount] = NULL;
    for (prop = proplist; prop != NULL ; prop = prop->next)
      keys[--propcount] = g_strdup (prop->data);
    g_list_free (proplist);

    device->propkeys = keys;

    return keys;
  }

  if (realfunc == NULL)
    realfunc = (const gchar * const*(*)()) dlsym (RTLD_NEXT,
                                                  k_func_get_property_keys);
  return realfunc (device);
}


const gchar *
g_udev_device_get_subsystem (FakeGUdevDevice *device)
{
  static const gchar* (*realfunc)();

  if (devices_by_ptr == NULL)
    g_udev_preload_init ();

  if (g_hash_table_lookup_extended (devices_by_ptr, device, NULL, NULL))
    return (gchar *)g_hash_table_lookup (device->properties, k_prop_subsystem);

  if (realfunc == NULL)
    realfunc = (const gchar *(*)()) dlsym (RTLD_NEXT, k_func_get_subsystem);
  return realfunc (device);
}

const gchar *
g_udev_device_get_sysfs_attr (FakeGUdevDevice *device, const gchar *name)
{
  static const gchar* (*realfunc)();

  if (devices_by_ptr == NULL)
    g_udev_preload_init ();

  if (g_hash_table_lookup_extended (devices_by_ptr, device, NULL, NULL)) {
    gchar *attrkey = g_strconcat (k_sysfs_attr_prefix, name, NULL);
    const gchar *result = (gchar *)g_hash_table_lookup (device->properties,
                                                        attrkey);
    g_free (attrkey);
    return result;
  }

  if (realfunc == NULL)
    realfunc = (const gchar *(*)()) dlsym (RTLD_NEXT, k_func_get_sysfs_attr);
  return realfunc (device, name);
}

/*
 * The get_sysfs_attr_as_SOMETYPE() functions have the same problem as
 * the get_property_as_SOMETYPE() functions described above.
 */

const gchar *
g_udev_device_get_sysfs_path (FakeGUdevDevice *device)
{
  static const gchar* (*realfunc)();

  if (devices_by_ptr == NULL)
    g_udev_preload_init ();

  if (g_hash_table_lookup_extended (devices_by_ptr, device, NULL, NULL)) {
    return (gchar *)g_hash_table_lookup (device->properties, k_prop_sysfs_path);
  }

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
  device->properties = g_hash_table_new_full (g_str_hash, g_str_equal,
                                              g_free, g_free);
  device->propkeys = NULL;
  device->client = NULL;
}

static void
fake_g_udev_device_finalize (GObject *object)
{
  FakeGUdevDevice *device = FAKE_G_UDEV_DEVICE (object);

  g_hash_table_unref (device->properties);
}

static void
fake_g_udev_device_class_init (FakeGUdevDeviceClass *klass)
{
  GObjectClass *gobject_class = (GObjectClass *) klass;

  gobject_class->finalize = fake_g_udev_device_finalize;
}
