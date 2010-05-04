// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include <string>

#include "base/file_path.h"
#include "base/file_util.h"
#include "base/string_util.h"

// Reads the current log level from /proc/sys/kernel/printk
bool GetCurrentLogLevel(std::string* log_level) {
  std::string level;
  if (!file_util::ReadFileToString(FilePath("/proc/sys/kernel/printk"),
                                   &level)) {
    return false;
  }

  std::vector<std::string> levels;
  SplitString(level, '\t', &levels);
  if (levels.size() != 4) {
    return false;
  }

  *log_level = levels[0];
  return true;
}

// Writes a log level to /proc/sys/kernel/printk
bool SetCurrentLogLevel(const std::string& log_level) {
  return file_util::WriteFile(FilePath("/proc/sys/kernel/printk"),
                              log_level.c_str(),
                              log_level.length());
}

// Attempts to open /proc/sys/kernel/printk for write.  A jailed process with
// /proc mounted read-only should not be able to open anything in /proc with
// write access.
void CheckProcIsReadOnly() {
  if(getuid() != 0) {
    printf("ERROR: Not running as root\n");
    return;
  }

  std::string log_level;
  if (!GetCurrentLogLevel(&log_level)) {
    printf("ERROR: Couldn't get the current log level\n");
    return;
  }

  printf("INFO: Current verbosity level: %s\n", log_level.c_str());

  if(!SetCurrentLogLevel("8")) {
    printf("SUCCEED: Write to printk failed (errno: %d).\n", errno);
  } else {
    std::string new_log_level;
    // Read the level back, but we've already confirmed we can write
    GetCurrentLogLevel(&new_log_level);
    printf("FAIL: Write to printk succeded, new level: %s.\n",
           new_log_level.c_str());
    // Set the level back to the original
    SetCurrentLogLevel(log_level);
  }
}

int main(int argc, const char* argv[]) {
  CheckProcIsReadOnly();

  return 0;
}
