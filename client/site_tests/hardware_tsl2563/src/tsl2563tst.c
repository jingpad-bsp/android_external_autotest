// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
 * TSL2563 light sensor functional test
 *
 * When I spoof an I2C device on i2c adapter 0, I see these files show
 * up in /sys/devices/pci0000:00/0000:00:02.0/i2c-0/0-0029/iio/device0:
 *  -r--r--r-- 1 root root 4096 Mar 25 17:21 adc0
 *  -r--r--r-- 1 root root 4096 Mar 25 17:21 adc1
 *  -rw-r--r-- 1 root root 4096 Mar 25 17:21 calib0
 *  -rw-r--r-- 1 root root 4096 Mar 25 17:21 calib1
 *  lrwxrwxrwx 1 root root    0 Mar 25 17:21 device -> ../../../0-0029
 *  -r--r--r-- 1 root root 4096 Mar 25 17:21 lux
 *  drwxr-xr-x 2 root root    0 Mar 25 17:21 power
 *  lrwxrwxrwx 1 root root    0 Mar 25 17:21 subsystem -> ../../../../../../../class/iio
 *  -rw-r--r-- 1 root root 4096 Mar 25 17:21 uevent
 * This is done with:
 *   echo tsl2563 0x29 > /sys/class/i2c-adapter/i2c-0/new_device
 *
 * Raw and calibrated ADC data come from adc{0|1} and calib{0|1}, but
 * it is probably best to use the lux file because it gives the calibrated
 * ADC translated to luminescence.
 */

#include <stdio.h>
#include <stdlib.h>

#define _GNU_SOURCE
#include <getopt.h>


/*
 * The "lux" sysfs file gives luminescence data with a "%d" printf.
 * I do not yet know the range of expected values.
 */
int lux_read(FILE *lux_fp, int *luxp)
{
  int rval;

  rval = fscanf(lux_fp, "%d", luxp);
  
  if (rval != 1) {
    printf("Failed to read an integer from the lux file.\n");
    return -1;
  }
  return 0;
}

void repeated_lux_read(FILE *lux_fp, int us_period)
{
  int lux;

  while (lux_read(lux_fp, &lux) == 0) {
    printf("lux: %d\n", lux);
    usleep(us_period);
  }
}

struct option long_options[] = {
  {"file", 1, 0, 'f'},
  {"repeat", 0, 0, 'r'},
  {"period", 1, 0, 'p'},
  {"help", 0, 0, 'h'},
  {0, 0, 0, 0}
};

int opt_repeat = 0;
int opt_period_usecs = 500000;
char *opt_file = "/sys/devices/pci0000:00/0000:00:02.0/i2c-0/0-0029/iio/device0/lux";

void print_help(void)
{
  printf("Usage: tsl2563tst [options]\n");
  printf("       will read the tsl2563 light sensor sysfs file.\n");
  printf("  options:\n");
  printf("  --file <file>: explicitly specify the sysfs light sensor file\n");
  printf("  --repeat: repeatedly read light sensor data\n");
  printf("  --period <usecs>: set the period between repeated reads\n");
  printf("  --help: print this help message\n");
}


int main(int argc, char *argv[])
{
  int c;

  while ((c = getopt_long(argc, argv, "hf:p:r", long_options, NULL)) != -1) {
    switch (c) {
    case 'h':
      print_help();
      exit(0);
    case 'f':
      opt_file = optarg;
      break;
    case 'p':
      opt_period_usecs = atoi(optarg);
      break;
    case 'r':
      opt_repeat = 1;
      break;
    case '?':
      print_help();
      exit(1);
    default:
      printf("Unknown parameter 0x%x.\n", c);
      exit(1);
    }
  }

  FILE *lux_fp;
  lux_fp = fopen(opt_file, "r");
  if (lux_fp == NULL) {
    perror("open device file");
    fprintf(stderr, "Cannot open %s.\n", opt_file);
    fprintf(stderr, "Perhaps the tsl2563 module is not loaded.\n"
      "Or perhaps the kernel needs to be told where to find the device.\n"
        "(eg, 'echo tsl2563 0x29 > /sys/class/i2c-adapter/i2c-0/new_device'\n");
    exit(1);
  }

  if (opt_repeat) {
    repeated_lux_read(lux_fp, opt_period_usecs);
  } else {
    int lux;
    if (lux_read(lux_fp, &lux) != 0)
      exit(1);
    printf("lux: %d\n", lux);
  }
  return 0;
}
