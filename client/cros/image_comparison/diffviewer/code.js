$(document).ready(function() {
  $(".thumb").click(function() {
    $("#fullsizeimage").attr("src", $(this).attr("src"));
  });
});
