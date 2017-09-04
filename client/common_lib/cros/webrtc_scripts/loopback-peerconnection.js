/*
 * Copyright 2017 The Chromium Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */
/*jshint esversion: 6 */

/**
 * A loopback peer connection with one or more streams.
 */
class PeerConnection {
  /**
   * Creates a loopback peer connection. One stream per supplied resolution is
   * created.
   * @param {!Element} videoElement the video element to render the feed on.
   * @param {!Array<!{x: number, y: number}>} resolutions. A width of -1 will
   *     result in disabled video for that stream.
   */
  constructor(videoElement, resolutions) {
    this.localConnection = null;
    this.remoteConnection = null;
    this.remoteView = videoElement;
    this.streams = [];
    // Ensure sorted in descending order to conveniently request the highest
    // resolution first through GUM later.
    this.resolutions = resolutions.slice().sort((x, y) => y.w - x.w);
  }

  /**
   * Starts the connections. Triggers GetUserMedia and starts
   * to render the video on {@code this.videoElement}.
   * @return {!Promise} a Promise that resolves when everything is initalized.
   */
  start() {
    // getUserMedia fails if we first request a low resolution and
    // later a higher one. Hence, sort resolutions above and
    // start with the highest resolution here.
    const promises = this.resolutions.map((resolution) => {
      const constraints = createMediaConstraints(resolution);
      return navigator.mediaDevices
        .getUserMedia(constraints)
        .then((stream) => this.streams.push(stream));
    });
    return Promise.all(promises).then(
        // Start with the smallest video to not overload the machine instantly.
        () =>
            this.onGetUserMediaSuccess_(this.streams[this.streams.length - 1]));
  };

  /**
   * Switches to a random stream, i.e., use a random resolution of the
   * resolutions provided to the constructor.
   * @return {!Promise} A promise that resolved when everything is initialized.
   */
  switchToRandomStream() {
    const localStreams = this.localConnection.getLocalStreams();
    const track = localStreams[0];
    if (track != null) {
      this.localConnection.removeStream(track);
      const index = Math.floor(Math.random() * this.streams.length);
      return this.addStream_(this.streams[index]);
    } else {
      return Promise.resolve();
    }
  }

  onGetUserMediaSuccess_(stream) {
    this.localConnection = new RTCPeerConnection(null);
    this.localConnection.onicecandidate = (event) => {
      this.onIceCandidate_(this.remoteConnection, event);
    };

    this.remoteConnection = new RTCPeerConnection(null);
    this.remoteConnection.onicecandidate = (event) => {
      this.onIceCandidate_(this.localConnection, event);
    };
    this.remoteConnection.onaddstream = (e) => {
      this.remoteView.srcObject = e.stream;
    };
    return this.addStream_(stream);
  };

  addStream_(stream) {
    this.localConnection.addStream(stream);
    return this.localConnection
        .createOffer({offerToReceiveAudio: 1, offerToReceiveVideo: 1})
        .then((desc) => this.onCreateOfferSuccess_(desc), logError);
  }

  onCreateOfferSuccess_(desc) {
    this.localConnection.setLocalDescription(desc);
    this.remoteConnection.setRemoteDescription(desc);
    return this.remoteConnection.createAnswer().then(
        (desc) => this.onCreateAnswerSuccess_(desc), logError);
  };

  onCreateAnswerSuccess_(desc) {
    this.remoteConnection.setLocalDescription(desc);
    this.localConnection.setRemoteDescription(desc);
  };

  onIceCandidate_(connection, event) {
    if (event.candidate) {
      connection.addIceCandidate(new RTCIceCandidate(event.candidate));
    }
  };
}

/**
 * Creates constraints for use with GetUserMedia.
 * @param {!{x: number, y: number}} widthAndHeight Video resolution.
 */
function createMediaConstraints(widthAndHeight) {
  let constraint;
  if (widthAndHeight.w < 0) {
    constraint = false;
  } else {
    constraint = {
      width: {exact: widthAndHeight.w},
      height: {exact: widthAndHeight.h}
    };
  }
  return {
    audio: true,
    video: constraint
  };
}

function logError(err) {
  console.error(err);
}

