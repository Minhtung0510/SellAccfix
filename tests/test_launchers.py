import os
import unittest
from unittest.mock import Mock, patch

from main import run_bot


class LauncherTests(unittest.TestCase):
    def launch(self, test_mode, env):
        with patch.dict(os.environ, env, clear=True), \
             patch('main.load_dotenv'), patch('Modules.pay.load_config'), \
             patch('core.bot.Bot') as bot:
            run_bot(test_mode=test_mode)
            bot.return_value.run.assert_called_once_with('dummy')
            return os.environ['PAYMENT_TEST_MODE']

    def test_test_launcher_needs_no_bank(self):
        self.assertEqual(self.launch(True, {'DISCORD_TOKEN': 'dummy', 'PAYMENT_TEST_MODE': 'false'}), 'true')

    def test_live_launcher_overrides_stale_test_setting(self):
        env = dict.fromkeys(('BANK_CODE', 'ACCOUNT_NO', 'ACCOUNT_NAME', 'WEB2M_PASSWORD', 'WEB2M_TOKEN'), 'dummy')
        env.update(DISCORD_TOKEN='dummy', PAYMENT_TEST_MODE='true')
        self.assertEqual(self.launch(False, env), 'false')

    def test_live_launcher_requires_bank(self):
        with patch.dict(os.environ, {'DISCORD_TOKEN': 'dummy'}, clear=True), patch('main.load_dotenv'):
            with self.assertRaisesRegex(RuntimeError, 'python test_bot.py'):
                run_bot()

    def test_test_launcher_still_requires_discord_token(self):
        with patch.dict(os.environ, {}, clear=True), patch('main.load_dotenv'):
            with self.assertRaisesRegex(RuntimeError, 'DISCORD_TOKEN'):
                run_bot(test_mode=True)
