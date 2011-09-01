/*
 * Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */

#include <stdio.h>
#include <string.h>

#include <glib.h>
#include <glib-object.h>

#define G_UDEV_API_IS_SUBJECT_TO_CHANGE
#include <gudev/gudev.h>

gboolean lookup (const gpointer data);

static GMainLoop* loop;

int
main (int argc, const char *argv[])
{
  int i;

  g_type_init ();

  loop = g_main_loop_new (NULL, FALSE);

  for (i = 1 ; i < argc ; i++)
    g_idle_add (lookup, (const gpointer)argv[i]);

  g_main_loop_run (loop);

  g_main_loop_unref (loop);

  return 0;
}

static void
print_device(GUdevDevice *device)
{
  printf (" Name:        %s\n", g_udev_device_get_name (device));
  printf (" Device file: %s\n", g_udev_device_get_device_file (device));
  printf (" Devtype:     %s\n", g_udev_device_get_devtype (device));
  printf (" Driver:      %s\n", g_udev_device_get_driver (device));
  printf (" Subsystem:   %s\n", g_udev_device_get_subsystem (device));
  printf (" Sysfs path:  %s\n", g_udev_device_get_sysfs_path (device));
  const gchar * const * keys = g_udev_device_get_property_keys (device);
  while (*keys) {
    printf("  Property %s: %s\n", *keys, g_udev_device_get_property (device,
                                                                     *keys));
    keys++;
  }
  /* sysfs attr? */
}

gboolean
lookup (const gpointer data)
{
  const char *path = data;

  GUdevClient *guclient = g_udev_client_new (NULL);
  GUdevDevice *device;

  if (path[0] == '=') {
    gchar **parts;
    parts = g_strsplit (path+1, ",", 2);
    printf ("Subsystem '%s', Name '%s'\n", parts[0], parts[1]);

    device = g_udev_client_query_by_subsystem_and_name (guclient, parts[0],
                                                        parts[1]);
    g_strfreev (parts);
  } else if (strncmp (path, "/sys/", 5) == 0) {
    printf ("Sysfs path '%s'\n", path);
    device = g_udev_client_query_by_sysfs_path (guclient, path);
  } else {
    printf ("Path '%s'\n", path);
    device = g_udev_client_query_by_device_file (guclient, path);
  }

  if (device) {
    print_device (device);
    if (1) {
      GUdevDevice *parent;
      parent = g_udev_device_get_parent (device);
      if (parent) {
        printf ("Parent device:\n");
        print_device (parent);
        g_object_unref (parent);
      }
    }
    g_object_unref (device);
  }
  printf("\n");

  g_object_unref (guclient);

  g_main_loop_quit (loop);

  return FALSE;
}
