function alloc(sizeMB) {
  var FLOAT64_BYTES = 8;
  var MB = 1024 * 1024;
  var count = sizeMB* MB / FLOAT64_BYTES;
  // Random content is uncompressable.
  var content = new Float64Array(count);
  for (var i = 0; i < content.length; i++) {
    content[i] = Math.random();
  }
  return content;
  document.out = arr;
}
$(document).ready(function() {
  var url = new URL(window.location.href);
  var allocMB = parseInt(url.searchParams.get("alloc"));
  if (isNaN(allocMB))
    allocMB = 800;

  var startTime = new Date();
  // Assigns the content to docuement to avoid optimization of unused data.
  document.out = alloc(allocMB);
  var ellapse = (new Date() - startTime) / 1000;
  // Shows the loading time for manual test.
  $("#display").text(`Allocating ${allocMB} MB takes ${ellapse} seconds`);
});
