/*
window.onkeydown = function(event) {
  if (event.keyCode == 83) {
    test.sendTestEvent("init_audio_server",{});
  }
}
*/

window.onload = function(event) {
  test.sendTestEvent("init_audio_server",{});
}

var active = 'loop_0';
var display_fa_utility = false;
var count = 3, count_timer = null, count_msg = '';

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
    test.sendTestEvent("init_audio_server",{});
  } else {
    document.getElementById('fa-utility').style.display = 'block';
    display_fa_utility = true;
    setMessage('');
    clearInterval(count_timer);
  }
}

function countdown() {
  setMessage(count_msg + ' ' + count);
  count = count - 1;
  if (count <= 0) {
     clearInterval(count_timer);
     test.sendTestEvent("init_audio_server",{});
  }
}

function start_countdown(msg, num) {
  count = num;
  count_msg = msg;
  count_timer = setInterval(countdown, 1000);
}
