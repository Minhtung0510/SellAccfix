import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from ui.views import AccountSelect


class SelectionResetTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_product_can_open_again_without_submitting_modal(self):
        with patch('ui.views.get_acc_count', return_value=10):
            select = AccountSelect()
            select._values = ['14k']
            interaction = SimpleNamespace(
                response=SimpleNamespace(send_modal=AsyncMock()),
                client=Mock(),
                message=SimpleNamespace(id=123, edit=AsyncMock()),
            )
            for _ in range(2):
                await select.callback(interaction)
                modal = interaction.response.send_modal.call_args.args[0]
                self.assertEqual(modal.selected_value, '14k')
                view = interaction.message.edit.call_args.kwargs['view']
                acc_select = next(c for c in view.children if isinstance(c, AccountSelect))
                self.assertTrue(all(not option.default for option in acc_select.options))
                self.assertTrue(view.is_finished())
                modal.stop()
            self.assertEqual(interaction.response.send_modal.await_count, 2)
            self.assertEqual(interaction.message.edit.await_count, 2)
