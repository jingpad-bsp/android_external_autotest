window.onkeydown = function(event) {
  if (event.keyCode == 83) {
    test.sendTestEvent("init_audio_server",{});
    window.onkeydown = null;
  }
}

function setMessage(msg) {
  document.getElementById("message").innerHTML = msg;
}

function commandEntered(event) {
  if (event.keyCode == 13) {
    alert(document.getElementById("command").value);
    test.sendTestEvent("test_command",
        {"cmd": document.getElementById("command").value});
  }
}
