// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <sys/ptrace.h>
#include <sys/types.h>
#include <unistd.h>

// Calls fork() and sees if it can do a PTRACE_ATTACH on the parent.  A properly
// jailed process should not be ptrace-able by another process.
void CheckPtraceDisabled() {
  pid_t parent_pid = getpid();
  if (fork() == 0) {
    if (ptrace(PTRACE_ATTACH, parent_pid, NULL, NULL) != -1) {
      printf("FAIL: ptrace attach of %d succeded.\n", parent_pid);
      ptrace(PTRACE_DETACH, parent_pid, NULL, NULL);
    } else {
      printf("SUCCEED: ptrace attach of %d failed (errno %d).\n", parent_pid,
             errno);
    }
    kill(parent_pid, SIGKILL);
  } else {
    sleep(10000);
  }
}

int main(int argc, const char* argv[]) {
  CheckPtraceDisabled();

  return 0;
}
