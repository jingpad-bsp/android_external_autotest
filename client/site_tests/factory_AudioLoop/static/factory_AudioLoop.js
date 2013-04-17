init = function(autostart) {
  if (autostart) {
    document.getElementById("message").innerHTML = "";
    test.sendTestEvent("start_run_test", {});
  } else {
    window.onkeydown = function(event) {
      if (event.keyCode == 83) {
        test.sendTestEvent("start_run_test", {});
        window.onkeydown = null;
      }
    }
  }
}

createLabel = function(enMsg, zhMsg) {
  var enSpan = document.createElement("span");
  enSpan.className = "goofy-label-en";
  enSpan.innerText = enMsg;

  var zhSpan = document.createElement("span");
  zhSpan.className = "goofy-label-zh";
  zhSpan.innerText = zhMsg;

  var finalDiv = document.createElement("div");
  finalDiv.appendChild(enSpan);
  finalDiv.appendChild(zhSpan);

  return finalDiv;
}

testInProgress = function(success_rate) {
  var msgs = document.getElementById("message");
  msgs.innerHTML = "";
  msgs.appendChild(createLabel(
    "Loopback testing...\nSuccess Rate: " + success_rate,
    "音源回放测试中...\n成功率: " + success_rate));
}

testFailResult = function(success_rate) {
  var msgs = document.getElementById("message");
  msgs.innerHTML = "";
  msgs.appendChild(createLabel(
    "Testing Result: Fail\nSuccess Rate : " + success_rate,
    "测试结果: 失败\n成功率: " + success_rate));
}

testPassResult = function(success_rate) {
  var msgs = document.getElementById("message");
  msgs.innerHTML = "";
  msgs.appendChild(createLabel(
    "Testing Result: Success!",
    "测试结果: 成功!"));
}
