// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <stdio.h>

// Echos the command line passed in, with delimiters so that it is easy for a
// script wrapper to pull just the command line.
void EchoCmdLine(int argc, const char* argv[]) {
  printf("__CMD_LINE__\n%s", argv[0]);
  for (int i = 1; i < argc; i++) {
    printf(" %s", argv[i]);
  }
  printf("\n__CMD_LINE__\n");
}

int main(int argc, const char* argv[]) {
  EchoCmdLine(argc, argv);

  return 0;
}
