// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <sys/mount.h>
#include <sys/types.h>
#include <unistd.h>

#include <iostream>
#include <sstream>
#include <string>

#include "base/command_line.h"

// Writes this process' PID
void WritePid() {
  std::cout << getpid() << std::endl;
}

// Checks that the file to check is accessible.  This is called from the loop
// handler when the program is run in checker mode.  The idea is that if this
// process is in the same namespace as the mounting process, then the file
// should be visible to this process via the mount point.  If it is in another
// namespace, it will not be visible because the mount should not propagate to
// this namespace.
bool CheckFileExists(const std::string& file_path) {
  int fd = open(file_path.c_str(), O_RDONLY);
  if (fd != -1) {
    close(fd);
    std::cout << "FAIL: Open of " << file_path << " succeeded." << std::endl;
    return true;
  } else {
    std::cout << "SUCCEED: Open of " << file_path << " failed." << std::endl;
    return false;
  }
}

// Main loop for waiting for the check file command when the program is in
// checker mode.
void CheckFileHandler(const std::string& file_path) {
  fd_set fds;
  FD_ZERO(&fds);
  FD_SET(0, &fds);

  struct timeval tv;
  tv.tv_sec = 60;
  tv.tv_usec = 0;

  while (select(1, &fds, NULL, NULL, &tv) > 0) {
    std::string line;
    getline(std::cin, line);
    if(line.compare("CHECK") == 0) {
      CheckFileExists(file_path);
      std::cout << "DONE_CMD: CHECK" << std::endl;
    } else if(line.compare("EXIT") == 0) {
      break;
    }
    FD_ZERO(&fds);
    FD_SET(0, &fds);
    tv.tv_sec = 60;
    tv.tv_usec = 0;
  }
}

// Deletes the test file and unmounts the bind mount.  Called when the program
// is in mounter mode.
void UnmountAndDeleteFile(const std::string& to_dir,
                          const std::string& file_to_test) {
  unlink((to_dir + "/" + file_to_test).c_str());
  umount(to_dir.c_str());
}

// Does a bind mount from one directory to another and creates a file in the
// target.  Called when the program is in mounter mode.
void MountAndCreateFile(const std::string& from_dir,
                        const std::string& to_dir,
                        const std::string& file_to_test) {
  if (mount(from_dir.c_str(), to_dir.c_str(), NULL,
            ((MS_MGC_VAL << 16) | MS_BIND), NULL) != 0) {
    std::cout << "ERROR: Fail on mount, err: " << errno << std::endl;
    return;
  }
  int fd = open((to_dir + "/" + file_to_test).c_str(), O_RDWR | O_CREAT,
                O_WRONLY);
  if (fd == -1) {
    std::cout << "ERROR: Fail on file create, err: " << errno << std::endl;
    UnmountAndDeleteFile(to_dir, file_to_test);
    return;
  }
  int written = write(fd, "MountedFile", 11);
  if(written != 11) {
    std::cout << "ERROR: Fail on file write, err: " << errno << std::endl;
    close(fd);
    UnmountAndDeleteFile(to_dir, file_to_test);
    return;
  }
  close(fd);
}

// Main loop for waiting for the mount/unmount commands when in mounter mode.
void GetReadyToMount(const std::string& from_dir, const std::string& to_dir,
                        const std::string& file_to_test) {
  fd_set fds;
  FD_ZERO(&fds);
  FD_SET(0, &fds);

  struct timeval tv;
  tv.tv_sec = 60;
  tv.tv_usec = 0;

  while (select(1, &fds, NULL, NULL, &tv) > 0) {
    std::string line;
    getline(std::cin, line);
    if(line.compare("MOUNT") == 0) {
      MountAndCreateFile(from_dir, to_dir, file_to_test);
      std::cout << "DONE_CMD: MOUNT" << std::endl;
    } else if(line.compare("UMOUNT") == 0) {
      UnmountAndDeleteFile(to_dir, file_to_test);
      std::cout << "DONE_CMD: UMOUNT" << std::endl;
    } else if(line.compare("EXIT") == 0) {
      break;
    }
    FD_ZERO(&fds);
    FD_SET(0, &fds);
    tv.tv_sec = 60;
    tv.tv_usec = 0;
  }
}

int main(int argc, const char* argv[]) {
  CommandLine::Init(argc, argv);

  const CommandLine* cmd_line = CommandLine::ForCurrentProcess();

  if(cmd_line->HasSwitch("checkMountOnSignal") &&
     cmd_line->HasSwitch("filePath")) {
    const std::string file_to_test =
        cmd_line->GetSwitchValueASCII("filePath");
    WritePid();
    CheckFileHandler(file_to_test);
  }

  if(cmd_line->HasSwitch("doMountOnSignal") && cmd_line->HasSwitch("fromDir")
     && cmd_line->HasSwitch("toDir") && cmd_line->HasSwitch("fileName")) {
    const std::string from_dir = cmd_line->GetSwitchValueASCII("fromDir");
    const std::string to_dir = cmd_line->GetSwitchValueASCII("toDir");
    const std::string file_to_test =
        cmd_line->GetSwitchValueASCII("fileName");
    WritePid();
    GetReadyToMount(from_dir, to_dir, file_to_test);
  }

  return 0;
}
