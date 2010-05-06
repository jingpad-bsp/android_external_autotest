// Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

int fibbomb(int n) {
  if (n < 2) {
    *(char*)0 = 0;
    return 1;
  }
  return fibbomb(n - 2) + fibbomb(n - 1);
}

int main(int argc, char *argv[]) {
  return fibbomb(20);
}
