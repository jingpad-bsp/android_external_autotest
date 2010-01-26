// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <stdio.h>
#include <time.h>

// Small wrapper around clock_gettime to read the clock from the hwclock
int main(int argc, char **argv) {
  struct timespec tp;
  double time = 0;
  clock_gettime(CLOCK_REALTIME, &tp);
  time = (int)tp.tv_sec + ((double)tp.tv_nsec) / 1000000000;
  printf("%f\n", time);
  return 0;
}
