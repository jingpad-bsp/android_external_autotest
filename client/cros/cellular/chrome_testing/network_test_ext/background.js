// Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

function ChromeTesting() {
  this.foundNetworks = null;
}

ChromeTesting.prototype.findNetworks = function(type) {
  this.foundNetworks = null;
  var self = this;
  chrome.networkingPrivate.getVisibleNetworks(type, function(networks) {
    self.foundNetworks = networks;
  });
};

var chromeTesting = new ChromeTesting();
