// This is a javascript file for both mp4video.html and webmvideo.html.

var videoAtStart = false;
var testvideo = document.getElementById('testvideo');

function playAndReload() {
  // Reload video after playing for several seconds.
  testvideo.addEventListener("timeupdate", function() {
      if (testvideo.currentTime > 3) {
        location.reload();
  }});

  testvideo.play();
  videoAtStart = false;
}

function contentLoaded() {
  var videoLoaded = false;
  testvideo.addEventListener("loadeddata", function() { videoLoaded = true; });
  testvideo.addEventListener("timeupdate", function() {
      if (videoLoaded && testvideo.currentTime == 0) videoAtStart = true; });
}

document.addEventListener("DOMContentLoaded", contentLoaded);
