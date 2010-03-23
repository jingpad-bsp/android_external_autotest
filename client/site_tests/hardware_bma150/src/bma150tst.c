// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
 * BMA150 functional test
 *
 * /dev/bma150 provides a readable and ioctlable interface.
 * read(fd, buf, 6) gives an array of 3 shorts: x, y and z, each in the
 * 10bit range of -512 to 511.
 *
 * There are also about 46 commands available via the ioctl interface.
 * One of them is READ_ACCEL_XYZ which gives the same 6 byte structure
 * as that given with read(), but this ioctl also returns error info,
 * presumably if the I2C transaction fails (though I see that i2c_bus_read()
 * returns -1 on error which just looks like EPERM.
 *
 * By the way, EC changes in revC, and the SMBus address in the datasheets
 * look a bit different.  So... different adapter drivers.
 */

#include <stdio.h>
#include <errno.h>
#include <unistd.h>
#include <stdlib.h>

#define _GNU_SOURCE
#include <getopt.h>

#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>


/*
 * /dev/bma150 provides a readable and ioctlable interface.
 * read(fd, buf, 6) gives an array of 3 shorts: x, y and z, each in the
 * 10bit range of -512 to 511.
 */
struct accel_data {
  short x, y, z;
};

int accel_read(int bfd, struct accel_data *adp)
{
  int rval;

  rval = read(bfd, adp, sizeof *adp);
  if (rval < 0) {
    perror("read device file");
  } else if (rval != sizeof *adp) {
    printf("device file: read %d instead of %d bytes.\n", rval, sizeof *adp);
  } else {
    return 0;
  }
  return -1;
}

void print_ad(struct accel_data *adp)
{
  /* For now, just print values. */
  printf("x y z: %10d %10d %10d\n", adp->x, adp->y, adp->z);
}

void repeated_accel_read(int bfd)
{
  struct accel_data ad;

  while (accel_read(bfd, &ad) == 0) {
    print_ad(&ad);
    usleep(500000);
  }
}

struct option long_options[] = {
  {"repeat", 0, 0, 'r'},
  {"period", 1, 0, 'p'},
  {"help", 0, 0, 'h'},
  {0, 0, 0, 0}
};

int opt_repeat = 0;
int opt_period_usecs = 500000;

void print_help(void)
{
  printf("Usage: bma150tst [options]\n");
  printf("       will read the BMA150 accelerometer device file.\n");
  printf("  options:\n");
  printf("  --repeat: repeatedly read accelerometer data\n");
  printf("  --period: set the period (usecs) between repeated reads\n");
  printf("  --help: print this help message\n");
}


int main(int argc, char *argv[])
{
  int c;

  while ((c = getopt_long(argc, argv, "hp:r", long_options, NULL)) != -1) {
    switch (c) {
    case 'h':
      print_help();
      exit(0);
    case 'p':
      opt_period_usecs = atoi(optarg);
      break;
    case 'r':
      opt_repeat = 1;
      break;
    case '?':
      break;
    default:
      printf("Unknown parameter 0x%x.\n", c);
    }
  }

  int bfd;
  bfd = open("/dev/bma150", O_RDONLY);
  if (bfd < 0) {
    perror("open device file");
    fprintf(stderr, "Perhaps the bma150 module is not loaded.\n");
    exit(1);
  }

  if (opt_repeat) {
    repeated_accel_read(bfd);
  } else {
    struct accel_data ad;
    if (accel_read(bfd, &ad) != 0)
      exit(1);
    print_ad(&ad);
  }
  return 0;
}
