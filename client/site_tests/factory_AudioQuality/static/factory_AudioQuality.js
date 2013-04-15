window.onkeydown = function(event) {
  if (event.keyCode == 83) {
    test.sendTestEvent("init_audio_server",{});
    window.onkeydown = null;
  }
}

var active = 'loop_0';
var display_fa_utility = false;

function setMessage(msg) {
  document.getElementById("message").innerHTML = msg;
}

function testCommand(cmd) {
  if (active.length != 0)
    document.getElementById(active).checked = false;
  test.sendTestEvent("test_command", {"cmd": cmd});
  active = cmd;
}

function restore() {
  if (active.length != 0)
    document.getElementById(active).checked = false;
  testCommand('loop_0');
  document.getElementById('loop_0').checked = true;
}

function toggleFAUtility() {
  if (display_fa_utility) {
    document.getElementById('fa-utility').style.display = 'none';
    display_fa_utility = false;
  } else {
    document.getElementById('fa-utility').style.display = 'block';
    display_fa_utility = true;
  }
}
