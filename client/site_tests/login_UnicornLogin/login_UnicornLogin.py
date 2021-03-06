# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.cros import cryptohome
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome


class login_UnicornLogin(test.test):
  """Sign into a unicorn account."""
  version = 1


  def run_once(self, child_user, child_pass, parent_user, parent_pass):
    """Test function body."""
    if not (child_user and child_pass and parent_user and parent_pass):
      raise error.TestFail('Credentials not set.')

    with chrome.Chrome(auto_login=False) as cr:
      cr.browser.oobe.NavigateUnicornLogin(
          child_user=child_user, child_pass=child_pass,
          parent_user=parent_user, parent_pass=parent_pass)
      if not cryptohome.is_vault_mounted(
          user=chrome.NormalizeEmail(child_user)):
        raise error.TestFail('Expected to find a mounted vault for %s'
                             % child_user)
      tab = cr.browser.tabs.New()
      # TODO(achuith): Use a better signal of being logged in, instead of
      # parsing accounts.google.com.
      tab.Navigate('http://accounts.google.com')
      tab.WaitForDocumentReadyStateToBeComplete()
      res = tab.EvaluateJavaScript( '''
          var res = '',
          divs = document.getElementsByTagName('div');
          for (var i = 0; i < divs.length; i++) {
            res = divs[i].textContent;
            if (res.search('%s') > 1) {
              break;
            }
          }
          res;
      ''' % child_user)
      if not res:
        raise error.TestFail('No references to %s on accounts page.'
                             % child_user)
      tab.Close()
