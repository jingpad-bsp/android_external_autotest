// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <errno.h>
#include <stdio.h>
#include <unistd.h>

#include "base/command_line.h"

// Verifies that the process group id is what is expected.
void CheckGid(uid_t gid) {
  uid_t rgid;
  uid_t egid;
  uid_t sgid;
  if (getresgid(&rgid, &egid, &sgid) != 0) {
    printf("ERROR: call to getresgid() failed: %d\n", errno);
  }
  if (rgid == gid && egid == gid && sgid == gid) {
    printf("SUCCEED: Real, Effective, and Saved Group IDs are %d\n", gid);
  } else {
    printf("FAIL: Group IDs: Real %d, Effective %d, Saved %d (Expected %d)\n",
           rgid, egid, sgid, gid);
  }
}

// Verifies that the process user id is what is expected.
void CheckUid(uid_t uid) {
  uid_t ruid;
  uid_t euid;
  uid_t suid;
  if (getresuid(&ruid, &euid, &suid) != 0) {
    printf("ERROR: call to getresuid() failed: %d\n", errno);
  }
  if (ruid == uid && euid == uid && suid == uid) {
    printf("SUCCEED: Real, Effective, and Saved User IDs are %d\n", uid);
  } else {
    printf("FAIL: User IDs: Real %d, Effective %d, Saved %d (Expected %d)\n",
           ruid, euid, suid, uid);
  }
}

int main(int argc, const char* argv[]) {
  CommandLine::Init(argc, argv);

  const CommandLine* cmd_line = CommandLine::ForCurrentProcess();

  if(cmd_line->HasSwitch("checkUid")) {
    int uid = atoi(cmd_line->GetSwitchValueASCII("checkUid").c_str());
    CheckUid(static_cast<uid_t>(uid));
  }

  if(cmd_line->HasSwitch("checkGid")) {
    int gid = atoi(cmd_line->GetSwitchValueASCII("checkGid").c_str());
    CheckGid(static_cast<uid_t>(gid));
  }

  return 0;
}
