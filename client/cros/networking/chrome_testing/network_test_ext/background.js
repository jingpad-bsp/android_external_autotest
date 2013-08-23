// Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// chromeTesting.Networking provides wrappers around chrome.networkingPrivate
// functions. The result of each asynchronous call can be accessed through
// chromeTesting.networking.callStatus, which is a dictionary of the form:
//    {
//      <function name>: {
//        "status": <STATUS_PENDING|STATUS_SUCCESS|STATUS_FAILURE>,
//        "result": <Return value or null>,
//        "error": <Error message or null>,
//      },
//      ...
//    }

function Networking() {
  this.callStatus = {};
}

// Returns false if a call |function_name| is pending, otherwise sets up
// the function dictionary and sets the status to STATUS_PENDING.
Networking.prototype._setupFunctionCall = function(function_name) {
  if (this.callStatus[function_name] == null)
    this.callStatus[function_name] = {};
  if (this.callStatus[function_name].status == chromeTesting.STATUS_PENDING)
    return false;
  this.callStatus[function_name].status = chromeTesting.STATUS_PENDING;
  return true;
};

Networking.prototype._setResult = function(function_name, result_value) {
  var error = chrome.runtime.lastError;
  if (error) {
    this.callStatus[function_name].status = chromeTesting.STATUS_FAILURE;
    this.callStatus[function_name].result = null;
    this.callStatus[function_name].error = error.message;
  } else {
    this.callStatus[function_name].status = chromeTesting.STATUS_SUCCESS;
    this.callStatus[function_name].result = result_value;
    this.callStatus[function_name].error = null;
  }
};

Networking.prototype.createNetwork = function(shared, properties) {
  if (!this._setupFunctionCall("createNetwork"))
    return;
  var self = this;
  chrome.networkingPrivate.createNetwork(shared, properties, function(guid) {
    self._setResult("createNetwork", guid);
  });
};

Networking.prototype.findNetworks = function(type) {
  if (!this._setupFunctionCall("findNetworks"))
    return;
  var self = this;
  chrome.networkingPrivate.getVisibleNetworks(type, function(networks) {
    self._setResult("findNetworks", networks);
  });
};

Networking.prototype.getNetworkInfo = function(networkId) {
  if (!this._setupFunctionCall("getNetworkInfo"))
    return;
  var self = this;
  chrome.networkingPrivate.getProperties(networkId, function(networkInfo) {
    self._setResult("getNetworkInfo", networkInfo);
  });
};

Networking.prototype.connectToNetwork = function(networkId) {
  if (!this._setupFunctionCall("connectToNetwork"))
    return;
  var self = this;
  chrome.networkingPrivate.startConnect(networkId, function() {
    self._setResult("connectToNetwork", null);
  });
};

Networking.prototype.disconnectFromNetwork = function(networkId) {
  if (!this._setupFunctionCall("disconnectFromNetwork"))
    return;
  var self = this;
  chrome.networkingPrivate.startDisconnect(networkId, function() {
    self._setResult("disconnectFromNetwork", null);
  });
};

var chromeTesting = {
  STATUS_PENDING: "chrome-test-call-status-pending",
  STATUS_SUCCESS: "chrome-test-call-status-success",
  STATUS_FAILURE: "chrome-test-call-status-failure",
  networking: new Networking()
};
