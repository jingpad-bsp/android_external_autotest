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
].sort((x, y) => y.w - x.w);  // Ensure sorted in descending order to
                              // conveniently request the highest
                              // resolution first through GUM later.

function createMediaConstraints(widthAndHeight) {
  const constraint = {
    width: {exact: widthAndHeight.w},
    height: {exact: widthAndHeight.h}
  };
  return {
    audio: true,
    video: constraint
  };
}

class PeerConnection {
  constructor(videoElement) {
    this.localConnection = null;
    this.remoteConnection = null;
    this.remoteView = videoElement;
    this.streams = [];
  }

  start() {
    // getUserMedia fails if we first request a low resolution and
    // later a higher one. Hence, sort RESOLUTIONS above and
    // start with the highest resolution here.
    const promises = RESOLUTIONS.map((resolution) => {
      const constraints = createMediaConstraints(resolution);
      return navigator.mediaDevices
        .getUserMedia(constraints)
        .then((stream) => this.streams.push(stream));
    });
    return Promise.all(promises).then(
        // Start with the smallest video to not overload the machine instantly.
        () =>
            this.onGetUserMediaSuccess(this.streams[this.streams.length - 1]));
  };

  onGetUserMediaSuccess(stream) {
    this.localConnection = new RTCPeerConnection(null);
    this.localConnection.onicecandidate = (event) => {
      this.onIceCandidate(this.remoteConnection, event);
    };

    this.remoteConnection = new RTCPeerConnection(null);
    this.remoteConnection.onicecandidate = (event) => {
      this.onIceCandidate(this.localConnection, event);
    };
    this.remoteConnection.onaddstream = (e) => {
      this.remoteView.srcObject = e.stream;
    };
    this.addStream(stream);
  };

  switchToRandomStream() {
    const localStreams = this.localConnection.getLocalStreams();
    const track = localStreams[0];
    if (track != null) {
      this.localConnection.removeStream(track);
      const index = Math.floor(Math.random() * this.streams.length);
      this.addStream(this.streams[index]);
    }
  }

  addStream(stream) {
    this.localConnection.addStream(stream);
    this.localConnection
        .createOffer({offerToReceiveAudio: 1, offerToReceiveVideo: 1})
        .then((desc) => this.onCreateOfferSuccess(desc), logError);
  }

  onCreateOfferSuccess(desc) {
    this.localConnection.setLocalDescription(desc);
    this.remoteConnection.setRemoteDescription(desc);
    this.remoteConnection.createAnswer().then(
        (desc) => this.onCreateAnswerSuccess(desc), logError);
  };

  onCreateAnswerSuccess(desc) {
    this.remoteConnection.setLocalDescription(desc);
    this.localConnection.setRemoteDescription(desc);
  };

  onIceCandidate(connection, event) {
    if (event.candidate) {
      connection.addIceCandidate(new RTCIceCandidate(event.candidate));
    }
  };
}

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
    this.peerConnections.push(new PeerConnection(videoElement));
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
    const minResolution = RESOLUTIONS[RESOLUTIONS.length - 1];
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
