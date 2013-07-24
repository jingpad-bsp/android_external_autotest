// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
"use strict";

(function() {
  window.__eventReporter = {};
  window.__testState = {};

  var video_format = 'video/mp4; codecs="avc1.640028"';
  var audio_format = 'audio/mp4; codecs="mp4a.40.2"';

  function createMediaSource() {
    return new WebKitMediaSource();
  }

  function createVideo() {
    return document.createElement('video');
  }

  function setupVideoAndMs(onSourceopen) {
    var temp_video = createVideo();
    var ms = createMediaSource();
    ms.addEventListener('webkitsourceopen', onSourceopen);
    var ms_url = window.URL.createObjectURL(ms);
    temp_video.src = ms_url;
    return {
      'video': temp_video,
      'ms': ms
    };
  }

  window.__testAttach = function() {
    var ms = createMediaSource();
    ms.addEventListener('webkitsourceopen', function() {
      window.__eventReporter['sourceopen'] = true;
    });

    var video = document.getElementById('main_player');
    video.src = window.URL.createObjectURL(ms);
    video.load();
  };

  window.__testAddSourceBuffer = function() {
    var vm = setupVideoAndMs(function() {
      try {
        var return_value = true;
        return_value = return_value && (vm.ms.sourceBuffers.length === 0);
        vm.ms.addSourceBuffer(audio_format);
        return_value = return_value && (vm.ms.sourceBuffers.length === 1);
        vm.ms.addSourceBuffer(video_format);
        return_value = return_value && (vm.ms.sourceBuffers.length === 2);

        window.__testState['addSourceBuffer'] = return_value;
      }
      catch (e) {
        window.__testState['addSourceBuffer'] = false;
      }
    });
  };

  window.__testAddSupportedFormats = function() {
    var formats = [
      audio_format,
      video_format,
    ];

    var vm = setupVideoAndMs(function() {
      for (var i = 0; i < formats.length; ++i) {
        try {
          vm.ms.addSourceBuffer(formats[i]);
        } catch (e) {
          window.__testState['addSupportedFormats'] = false;
          return;
        }
      }
      window.__testState['addSupportedFormats'] = true;
    });
  };

  window.__testAddSourceBufferException = function() {
    var vm = setupVideoAndMs(function() {
      try {
        vm.ms.addSourceBuffer('^^^');
        window.__testState['addSourceBufferException'] = false;
        return;
      }
      catch (e) {
        if (e.code !== DOMException.NOT_SUPPORTED_ERR) {
          window.__testState['addSourceBufferException'] = false;
          return;
        }
      }

      try {
        var temp_media_source = new WebKitMediaSource();
        temp_media_source.addSourceBuffer(audio_format);
        window.__testState['addSourceBufferException'] = false;
        return;
      }
      catch (e) {
        if (e.code !== DOMException.INVALID_STATE_ERR) {
          window.__testState['addSourceBufferException'] = false;
          return;
        }
      }
      window.__testState['addSourceBufferException'] = true;
    });
  };

  window.__testInitialVideoState = function() {
    var temp_video = createVideo();
    var test_result = true;

    test_result = test_result && isNaN(temp_video.duration);
    test_result = test_result && (temp_video.videoWidth === 0);
    test_result = test_result && (temp_video.videoHeight === 0);
    test_result = test_result &&
        (temp_video.readyState === HTMLMediaElement.HAVE_NOTHING);
    test_result = test_result && (temp_video.src === '');
    test_result = test_result && (temp_video.currentSrc === '');

    window.__testState['initialVideoState'] = test_result;
  };

  window.__testInitialMSState = function() {
    var vm = setupVideoAndMs(function() {
      var test_result = true;
      test_result = test_result && isNaN(vm.ms.duration);
      test_result = test_result && vm.ms.readyState === 'open';
      window.__testState['initialMSState'] = test_result;
    });
  };

  window.__testCanPlayClearKey = function() {
    var temp_video = createVideo();
    return temp_video.canPlayType('video/mp4; codecs="avc1.640028"',
                                  'webkit-org.w3.clearkey') === 'probably' &&
        temp_video.canPlayType('audio/mp4; codecs="mp4a.40.2"',
                               'webkit-org.w3.clearkey') === 'probably';
  };

  window.__testCanNotPlayPlayReady = function() {
    var temp_video = createVideo();
    return temp_video.canPlayType('video/mp4; codecs="avc1.640028"',
                                  'com.youtube.playready') !== 'probably' &&
        temp_video.canPlayType('audio/mp4; codecs="mp4a.40.2"',
                               'com.youtube.playready') !== 'probably';
  };
})();
