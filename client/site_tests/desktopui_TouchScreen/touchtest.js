// Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * @fileoverview This library implements a set of functions for HTML/JS tests
 * to use for interacting with the HTTP server spawned by desktopui_TouchScreen
 * test.
 *
 * The python side of the test directs the browser to open an HTML page. JS
 * code on the page asks the server to replay particular gestures by
 * calling replayGesture(), the last gesture will usually be 'click1' that will
 * replay a click in the upper left corner of the page (see tests/example.html)
 * After receiving the last click, JS code should decide on the outcome of
 * the test and send either 'PASS' or 'FAIL' back to the server using
 * reportStatus()
 *
 * Recording of new gestures is done on the device by running:
 * $ evemu-record /dev/input/event6 -1 > gestureName.dat
 * Ctrl-C to finish recording.
 *
 * Device name for touch screen may vary, look it up in /var/log/Xorg.0.log
 * and verify that some data comes out when you run "od /dev/input/eventN" and
 * touch the screen.
 */

/**
 * Wrap the xhr to send some info to HTTP server spawned by the python side.
 * @private
 * @param {string} url Request URL.
 * @param {Function} callback Function to be called on request completion.
 * @param {string} text The text to send. Usually series of name=value pairs.
 */
function sendPost(url, callback, text) {
  var xhr = new XMLHttpRequest();
  xhr.open('POST', url, true);
  xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
  if (callback) {
    xhr.onreadystatechange = function() {
        if (xhr.readyState == 4) {
          if (xhr.status == 200) {
            callback.apply(xhr, arguments);
          } else {
            debug('sendPost: Error communicating with the server, status=' +
                  xhr.status);
          }
        }
    } //closing callback wrapper
  }
  xhr.send(text);
}

/** Ask the server side to replay one or several gestures.
 * @param {string} gesture A white space separated list of gesture names.
 *     Gesture name + '.dat' is expected to be the file with raw gesture data.
 * @param {Function} onFinished Callback called by the xhr on completion.
 */
function replayGesture(gesture, onFinished) {
  sendPost('/replay', onFinished, 'gesture=' + encodeURI(gesture));
}

/** Report the test result back to the server.
 * @param {string} status Either 'PASS' or 'FAIL'.
 */
function reportStatus(status) {
  sendPost('/done', null, 'status=' + status);
}

/** Send any log message to the server.
 * @param {string} msg Any URL-encodable string.
 */
function sendLog(msg) {
  sendPost('/msg', null, 'msg=' + encodeURI(msg));
}

/**
 * Print a message to the browser JS console, and if present, a div
 * with id='console'.
 * @param {string} msg The message to send.
 */
function debug(msg) {
  if (!window.DEBUG) {
    return;
  }
  window.console.info(msg);
  var div = document.getElementById('console');
  if (div) {
    var span = document.createElement('span');
    // insert it first so XHTML knows the namespace
    div.appendChild(span);
    span.innerHTML = msg + '<br />';
  }
}
