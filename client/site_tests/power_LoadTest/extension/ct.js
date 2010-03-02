// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

request = {action: "should_scroll"}
chrome.extension.sendRequest(request, function(response) {
  if (response.should_scroll) {
    lastOffset = window.pageYOffset;
    function smoothScrollDown()
    {
      window.scrollBy(0,1);
      if (window.pageYOffset != lastOffset)
      {
        lastOffset = window.pageYOffset;
        setTimeout(smoothScrollDown, 15);
      }
      else
      {
        setTimeout(smoothScrollUp, 5000);
      }
    }
    function smoothScrollUp()
    {
      window.scrollBy(0,-1);
      if (window.pageYOffset != lastOffset)
      {
        lastOffset = window.pageYOffset;
        setTimeout(smoothScrollUp, 15);
      }
    }
    setTimeout(smoothScrollDown, 10000);
  }
});
