# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, string, time
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui, cros_ui_test

class desktopui_IBusTest(cros_ui_test.UITest):
    version = 1
    preserve_srcdir = True

    def setup(self):
        self._ibus_job = None
        self.job.setup_dep(['ibusclient'])


    def run_ibusclient(self, options):
        cmd = cros_ui.xcommand_as('%s %s' % (self.exefile, options), 'chronos')
        return utils.system_output(cmd, retain_output=True)


    def test_reachable(self):
        out = self.run_ibusclient('check_reachable')
        if not 'YES' in out:
            raise error.TestFail('ibus-daemon is not reachable')


    def test_supported_engines(self):
        out = self.run_ibusclient('list_engines')
        engine_names = out.splitlines()
        # We expect these engines to exist.
        expected_engine_names = ['mozc-chewing', 'mozc-hangul', 'pinyin',
                                 'm17n:ar:kbd']
        for expected_engine_name in expected_engine_names:
            if not expected_engine_name in engine_names:
                raise error.TestFail('Engine not found: ' +
                                     expected_engine_name)


    def test_config(self, type_name):
        wrong_type_name = 'string'
        if type_name == 'string':
            wrong_type_name = 'int'
        # First, write a dummy value which is not |type_name| type to make sure
        # the second set_config overwrites this |wrong_type_name| value.
        out = self.run_ibusclient('set_config %s' % wrong_type_name)
        if not 'OK' in out:
            raise error.TestFail('Failed to set %s value to '
                                 'the ibus config service' % wrong_type_name)
        # Then overwrite a value of |type_name| type.
        out = self.run_ibusclient('set_config %s' % type_name)
        if not 'OK' in out:
            raise error.TestFail('Failed to set %s value to '
                                 'the ibus config service' % type_name)
        out = self.run_ibusclient('get_config %s' % type_name)
        if not 'OK' in out:
            raise error.TestFail('Failed to get %s value from '
                                 'the ibus config service' % type_name)
        out = self.run_ibusclient('unset_config')
        if not 'OK' in out:
            raise error.TestFail('Failed to unset %s value from '
                                 'the ibus config service' % type_name)
        # TODO(yusukes): Add a get_config test here to make sure the value is
        # actually removed. See also http://crosbug.com/2801/.


    def test_check_unused_ibus_values(self):
        engine_list = ['mozc-hangul', 'pinyin', 'mozc', 'mozc-chewing']
        expected_unread = set(['engine/PinyinCorrectPinyin_UEN_UN',
                               'engine/PinyinFuzzyPinyin_Z_ZH',
                               'engine/PinyinFuzzyPinyin_CH_C',
                               'engine/PinyinFuzzyPinyin_S_SH',
                               'engine/PinyinFuzzyPinyin_EN_ENG',
                               'engine/PinyinFuzzyPinyin_AN_ANG',
                               'engine/PinyinFuzzyPinyin_IANG_IAN',
                               'engine/PinyinSpecialPhrases',
                               'engine/PinyinFuzzyPinyin_UAN_UANG',
                               'engine/PinyinFuzzyPinyin_IN_ING',
                               'engine/PinyinFuzzyPinyin_G_K',
                               'engine/PinyinCorrectPinyin_UEI_UI',
                               'engine/PinyinCorrectPinyin_UE_VE',
                               'engine/PinyinFuzzyPinyin_F_H',
                               'engine/PinyinFuzzyPinyin_SH_S',
                               'engine/PinyinIncompletePinyin',
                               'engine/PinyinFuzzyPinyin_L_R',
                               'engine/PinyinFuzzyPinyin_K_G',
                               'engine/PinyinFuzzyPinyin_ANG_AN',
                               'engine/PinyinFuzzyPinyin_C_CH',
                               'engine/PinyinCorrectPinyin_MG_NG',
                               'engine/PinyinLookupTableOrientation',
                               'engine/PinyinFuzzyPinyin_L_N',
                               'engine/PinyinFuzzyPinyin_ING_IN',
                               'engine/PinyinFuzzyPinyin_IAN_IANG',
                               'engine/PinyinFuzzyPinyin_N_L',
                               'engine/PinyinCorrectPinyin_IOU_IU',
                               'engine/PinyinFuzzyPinyin_ENG_EN',
                               'engine/PinyinCorrectPinyin_VE_UE',
                               'engine/PinyinCorrectPinyin_V_U',
                               'engine/PinyinFuzzyPinyin_UANG_UAN',
                               'engine/PinyinDoublePinyinShowRaw',
                               'engine/PinyinFuzzyPinyin_H_F',
                               'engine/PinyinFuzzyPinyin_ZH_Z',
                               'engine/PinyinFuzzyPinyin_R_L',

                               # TODO: Uncomment these when mozc loads config
                               # values from ibus.
                               'engine/Mozchistory_learning_level',
                               'engine/Mozcincognito_mode',
                               'engine/Mozcnumpad_character_form',
                               'engine/Mozcpreedit_method',
                               'engine/Mozcpunctuation_method',
                               'engine/Mozcsession_keymap',
                               'engine/Mozcshift_key_mode_switch',
                               'engine/Mozcspace_character_form',
                               'engine/Mozcsuggestions_size',
                               'engine/Mozcsymbol_method',
                               'engine/Mozcuse_auto_ime_turn_off',
                               'engine/Mozcuse_dictionary_suggest',
                               'engine/Mozcuse_history_suggest',
                               'engine/Mozcuse_number_conversion',
                               'engine/Mozcuse_single_kanji_conversion',
                               'engine/Mozcuse_symbol_conversion',
                               'engine/Mozcuse_date_conversion',

                               # These preferences are actually read, but
                               # ibus-daemon reads them before chrome connects,
                               # so they show up as a false failure.
                               'general/hotkeynext_engine_in_menu',
                               'general/hotkeyprevious_engine',
                               'generalglobal_engine',
                               'generalglobal_previous_engine'])

        expected_unwritten = set(['engine/ChewingsyncCapsLockLocal',
                                  'engine/ChewingnumpadAlwaysNumber',
                                  'engine/ChewinginputStyle',
                                  'engine/PinyinCorrectPinyin_GN_NG',
                                  'engine/PinyinCorrectPinyin_IOU_IU',
                                  'engine/PinyinCorrectPinyin_MG_NG',
                                  'engine/PinyinCorrectPinyin_UEN_UN',
                                  'engine/PinyinCorrectPinyin_UE_VE',
                                  'engine/PinyinCorrectPinyin_VE_UE',
                                  'engine/PinyinCorrectPinyin_V_U',
                                  'engine/PinyinDoublePinyinShowRaw',
                                  'engine/PinyinFuzzyPinyin_ANG_AN',
                                  'engine/PinyinFuzzyPinyin_AN_ANG',
                                  'engine/PinyinFuzzyPinyin_CH_C',
                                  'engine/PinyinFuzzyPinyin_C_CH',
                                  'engine/PinyinFuzzyPinyin_ENG_EN',
                                  'engine/PinyinFuzzyPinyin_EN_ENG',
                                  'engine/PinyinFuzzyPinyin_F_H',
                                  'engine/PinyinFuzzyPinyin_G_K',
                                  'engine/PinyinFuzzyPinyin_H_F',
                                  'engine/PinyinFuzzyPinyin_IANG_IAN',
                                  'engine/PinyinFuzzyPinyin_IAN_IANG',
                                  'engine/PinyinFuzzyPinyin_ING_IN',
                                  'engine/PinyinFuzzyPinyin_IN_ING',
                                  'engine/PinyinFuzzyPinyin_K_G',
                                  'engine/PinyinFuzzyPinyin_L_N',
                                  'engine/PinyinFuzzyPinyin_L_R',
                                  'engine/PinyinFuzzyPinyin_N_L',
                                  'engine/PinyinFuzzyPinyin_R_L',
                                  'engine/PinyinFuzzyPinyin_SH_S',
                                  'engine/PinyinFuzzyPinyin_S_SH',
                                  'engine/PinyinFuzzyPinyin_UANG_UAN',
                                  'engine/PinyinFuzzyPinyin_UAN_UANG',
                                  'engine/PinyinFuzzyPinyin_ZH_Z',
                                  'engine/PinyinFuzzyPinyin_Z_ZH',
                                  'engine/PinyinCorrectPinyin_UEI_UI',
                                  'engine/PinyinIncompletePinyin',
                                  'engine/PinyinLookupTableOrientation',
                                  'engine/PinyinSpecialPhrases',

                                  # We don't set these prefernces.
                                  'general/hotkeytrigger',
                                  'generalembed_preedit_text',
                                  'generalenable_by_default',
                                  'generalpreload_engines',
                                  'generaluse_global_engine',
                                  'generaluse_system_keyboard_layout'])

        # We ignore preload_engines since ibus-daemon in ibus-1.3 sometimes
        # reads it, but the daemon in ibus-1.4 does not. The preference is not
        # important for this test anyway.
        ignored_unread = set(['generalpreload_engines'])

        # These preferences are actually written, but due to a race condition
        # on startup, they can be read by ibus-daemon before chrome connects,
        # and so sometimes they show up as a false failure.
        ignored_unwritten = set(['general/hotkeynext_engine_in_menu',
                                 'general/hotkeyprevious_engine',
                                 'generalglobal_engine'])

        self.preload_engines(engine_list)

        # ibus takes some time to preload the engines, and they can't be
        # activated until they are done loading.  Since we don't get notified
        # when they are ready, we have to wait here to give them time.
        time.sleep(2)

        # Send a ctrl+l to enter a text field.
        ax = self.get_autox()
        ax.send_hotkey('Ctrl-l')

        for engine_name in engine_list:
            self.activate_engine(engine_name)

        out = self.run_ibusclient('get_unused')
        match = re.match(r"Unread:(.*)Unwritten:(.*)", out, re.DOTALL)
        if not match:
            raise error.TestFail('Could not read unused values from ibus')

        actual_unread = set(re.split('\n', match.group(1).strip()))
        actual_unwritten = set(re.split('\n', match.group(2).strip()))

        # Filter out any preferences we're ignoring
        actual_unread.difference_update(ignored_unread)
        actual_unwritten.difference_update(ignored_unwritten)

        new_unread = actual_unread.difference(expected_unread)
        now_read = expected_unread.difference(actual_unread)
        new_unwritten = actual_unwritten.difference(expected_unwritten)
        now_written = expected_unwritten.difference(actual_unwritten)

        if new_unread or now_read or new_unwritten or now_written:
            message = ['iBus config has changed:']
            if new_unread:
                message.append('New unread values:')
                for key in new_unread:
                    message.append(key)
            if now_read:
                message.append('No longer unread values:')
                for key in now_read:
                    message.append(key)
            if new_unwritten:
                message.append('New unwritten values:')
                for key in new_unwritten:
                    message.append(key)
            if now_written:
                message.append('No longer unwritten values:')
                for key in now_written:
                    message.append(key)
            raise error.TestFail(string.join(message, '\n'))


    def preload_engines(self, engine_list):
        engine_names = string.join(engine_list, " ")
        out = self.run_ibusclient('preload_engines %s' % engine_names)
        if not 'OK' in out:
            raise error.TestFail('Failed to preload engines: %s' % engine_names)


    def activate_engine(self, engine_name):
        out = self.run_ibusclient('activate_engine %s' % engine_name)
        if not 'OK' in out:
            raise error.TestFail('Failed to activate engine: %s' % engine_name)


    def run_once(self):
        self.start_ibus_daemon_or_die()
        dep = 'ibusclient'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)

        self.exefile = os.path.join(self.autodir,
                                    'deps/ibusclient/ibusclient')
        self.test_reachable()
        self.test_supported_engines()
        for type_name in ['boolean', 'int', 'double', 'string', 'boolean_list',
                          'int_list', 'double_list', 'string_list']:
            self.test_config(type_name)

        # TODO: re-enable this test.
        # Since the async changes to ibus, this has become less deterministic.
        # It is temporarily disabled to make the console more useful.
        # self.test_check_unused_ibus_values()
        self._ibus_job = None
        utils.system_output("kill -9 `pgrep ^ibus-daemon$`")


    def start_ibus_daemon_or_die(self, timeout=10):
        self._ibus_job = utils.BgJob(
            "su chronos -c '%s'" %
            "/usr/bin/ibus-daemon --panel=disable --cache=none --restart")
        time.sleep(2)
        start_time = time.time()
        while time.time() - start_time < timeout:
            if os.system('pgrep ^ibus-daemon$ >/dev/null') == 0:
                return
            time.sleep(1)
        raise error.TestFail('ibus-daemon is not running')
