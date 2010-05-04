// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <stdio.h>
#include <sys/types.h>
#include <unistd.h>

// Checks that getpid() returns 1.  If this process has its own PID namespace,
// then it should have a PID of 1.
void CheckProcessIdIsOne() {
  pid_t pid;
  if ((pid = getpid()) == (static_cast<pid_t>(1))) {
    printf("SUCCEED: Process ID is 1\n");
  } else {
    printf("FAIL: Process ID is %d\n", pid);
  }
}

int main(int argc, const char* argv[]) {
  CheckProcessIdIsOne();

  return 0;
}
