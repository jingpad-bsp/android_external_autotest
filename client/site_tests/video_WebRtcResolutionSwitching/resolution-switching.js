/*
 * Copyright 2017 The Chromium Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */
/*jshint esversion: 6 */

'use strict';

const $ = document.getElementById.bind(document);

function logError(err) {
  console.error(err);
}

// Available resolutions to switch between. These are 4:3 resolutions chosen
// since they have significant distance between them and are quite common. E.g.
// they can be selected for youtube videos. We also avoid higher resolutions
// since they consume a lot of resources.
const RESOLUTIONS = [
  {w:320, h:240},
  {w:480, h:360},
  {w:640, h:480},
  {w:1280, h:720},
];

class TestRunner {
  constructor(runtimeSeconds, switchResolutionDelayMillis) {
    this.runtimeSeconds = runtimeSeconds;
    this.switchResolutionDelayMillis = switchResolutionDelayMillis;
    this.videoElements = [];
    this.peerConnections = [];
    this.numConnections = 0;
    this.iteration = 0;
    this.startTime = 0;  // initialized to dummy value
  }

  addPeerConnection() {
    const videoElement = document.createElement('video');
    videoElement.autoplay = true;
    $('body').appendChild(videoElement);
    this.videoElements.push(videoElement);
    this.peerConnections.push(new PeerConnection(videoElement, RESOLUTIONS));
  }

  startTest() {
    this.startTime = Date.now();
    const promises = testRunner.peerConnections.map((conn) => conn.start());
    Promise.all(promises)
        .then(() => {
          this.startTime = Date.now();
          // Use setTimeout to get initial promises some time to resolve.
          setTimeout(() => this.switchResolutionLoop(), 500);
        })
        .catch((e) => {throw e});
  }

  stopAll() {
    console.log("STOP ALL");
      this.videoElements.forEach((feed) => {
        feed.pause();
      });
  }

  switchResolutionLoop() {
    this.iteration++;
    const status = this.getStatus();
    $('status').textContent = status;
    this.peerConnections.forEach((pc) => {
      pc.switchToRandomStream();
    });
    if (status != 'ok-done') {
      setTimeout(
          () => this.switchResolutionLoop(), this.switchResolutionDelayMillis);
    } else {  // We're done. Pause all feeds.
      this.videoElements.forEach((feed) => {
        feed.pause();
      });
    }
  }

  getStatus() {
    if (this.iteration == 0) {
      return 'not-started';
    }
    if (this.isVideoBroken()) {
      return 'video-broken';
    }
    const timeSpent = Date.now() - this.startTime;
    if (timeSpent >= this.runtimeSeconds * 1000) {
      return 'ok-done';
    } else {
      return `running, iteration: ${this.iteration}`;
    }
  }

  isVideoBroken() {
    // Check if any video element is smaller than the minimum resolution we set
    // it to. If so, we might have encountered something like
    // https://crbug.com/758850.
    const minResolution = RESOLUTIONS[0];
    const minWidth = minResolution.w;
    const minHeight = minResolution.h;
    return this.videoElements.find(
        (el) => el.videoWidth < minWidth || el.videoHeight < minHeight);
  }
}

let testRunner;

function startTest(
    runtimeSeconds, numPeerConnections, switchResolutionDelayMillis) {
  testRunner = new TestRunner(runtimeSeconds, switchResolutionDelayMillis);
  for (let i = 0; i < numPeerConnections; i++) {
    testRunner.addPeerConnection();
  }
  testRunner.startTest();
}
