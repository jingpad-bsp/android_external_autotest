window.onkeydown = function(event) {
  if (event.keyCode == 83) {
    test.sendTestEvent("start_run_test", {});
    window.onkeydown = null;
  }
}
