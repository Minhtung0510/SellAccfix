import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from Modules.pay import payment_test_mode
from ui.views import QuantityModal


class PaymentTestModeTests(unittest.IsolatedAsyncioTestCase):
    def test_mode_requires_explicit_enable(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(payment_test_mode())
        with patch.dict(os.environ, PAYMENT_TEST_MODE='false'):
            self.assertFalse(payment_test_mode())
        with patch.dict(os.environ, PAYMENT_TEST_MODE='true'):
            self.assertTrue(payment_test_mode())

    async def submit(self, enabled, admin):
        modal = QuantityModal('14k', 10)
        modal.quantity._value = '1'
        interaction = SimpleNamespace(
            user=SimpleNamespace(id=123, send=AsyncMock(return_value=SimpleNamespace(id=456))),
            channel=None,
            response=SimpleNamespace(send_message=AsyncMock(), defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
            client=Mock(),
        )
        with patch('ui.views.payment_test_mode', return_value=enabled), \
             patch('ui.views.load_admin_ids', return_value=[123] if admin else []), \
             patch('ui.views.get_acc_count', return_value=10), \
             patch('ui.views.add_order') as add, \
             patch('ui.views.build_payment_message', return_value=Mock()) as payment_card:
            await modal.on_submit(interaction)
        modal.stop()
        return interaction, add, payment_card

    async def test_admin_test_order_bypasses_payment(self):
        interaction, add, card = await self.submit(True, True)
        order = add.call_args.args[0]
        self.assertTrue(order['paid'])
        self.assertTrue(order['test_order'])
        card.assert_not_called()
        interaction.client.get_cog.return_value.notify_orders_changed.assert_called_once()

    async def test_non_admin_cannot_create_free_order(self):
        interaction, add, card = await self.submit(True, False)
        add.assert_not_called()
        interaction.user.send.assert_not_awaited()
        interaction.response.send_message.assert_awaited_once()

    async def test_live_order_still_requires_payment(self):
        interaction, add, card = await self.submit(False, False)
        self.assertFalse(add.call_args.args[0]['paid'])
        self.assertFalse(add.call_args.args[0]['test_order'])
        card.assert_called_once()
