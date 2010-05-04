// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <string.h>
#include <sys/capability.h>

#include "base/command_line.h"

// Checks that the capabilities mask of the current process is as expected.
// It mirrors the minijail code in considering CAP_SETPCAP acceptable
// regardless of the mask passed into the function.
void CheckRootCaps(uint64_t effective_capmask) {
  cap_t caps = cap_get_proc();
  if(!caps) {
    printf("ERROR: Could not get process capabilities\n");
    return;
  }
  for(cap_value_t cap = 0;
      cap < static_cast<cap_value_t>(sizeof(effective_capmask) * 8)
      && cap_valid(cap); cap++) {
    if(cap != CAP_SETPCAP && !(effective_capmask & (1 << cap))) {
      cap_flag_value_t value = static_cast<cap_flag_value_t>(0);
      if(cap_get_flag(caps, cap, CAP_EFFECTIVE, &value) != 0) {
        printf("ERROR: Could not get effective capability flag\n");
      }
      if(value != 0) {
        printf("FAIL: Process has extra effective capability: 0x%x\n", cap);
        return;
      }
      value = static_cast<cap_flag_value_t>(0);
      if(cap_get_flag(caps, cap, CAP_PERMITTED, &value) != 0) {
        printf("ERROR: Could not get permitted capability flag\n");
      }
      if(value != 0) {
        printf("FAIL: Process has extra permitted capability: 0x%x\n", cap);
        return;
      }
      value = static_cast<cap_flag_value_t>(0);
      if(cap_get_flag(caps, cap, CAP_INHERITABLE, &value) != 0) {
        printf("ERROR: Could not get inheritable capability flag\n");
      }
      if(value != 0) {
        printf("FAIL: Process has extra inheritable capability: 0x%x\n", cap);
        return;
      }
    }
  }
  printf("SUCCEED: Process had at most the capabilities specified\n");
}

int main(int argc, const char* argv[]) {
  CommandLine::Init(argc, argv);

  const CommandLine* cmd_line = CommandLine::ForCurrentProcess();

  if(cmd_line->HasSwitch("checkRootCaps")) {
    uint64_t caps =
        atol(cmd_line->GetSwitchValueASCII("checkRootCaps").c_str());
    CheckRootCaps(caps);
  }

  return 0;
}
