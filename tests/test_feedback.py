import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from utils.warranty import WarrantyStore, WarrantyError
from ui.feedback import FeedbackModal, FeedbackButton, reserve_feedback


class FeedbackTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = WarrantyStore(Path(self.tmp.name) / 'db')
        self.store.record_delivery(dict(order_code='TEST', user_id=123, account_type='5k', quantity=1, test_order=True), ['private:secret'])
        self.store.mark_delivered('TEST')

    def test_owner_rating_and_duplicate_checks_survive_restart(self):
        for buyer, rating in [(456, 5), (123, 0), (123, 6)]:
            with self.assertRaises(WarrantyError):
                reserve_feedback(self.store, 'TEST', buyer, rating, 'Good', 7)
        reserve_feedback(self.store, 'TEST', 123, 4, 'Good', 7)
        reopened = WarrantyStore(self.store.path)
        with self.assertRaises(WarrantyError):
            reserve_feedback(reopened, 'TEST', 123, 5, 'Again', 7)

    async def test_publish_failure_retry_and_no_credentials(self):
        channel = SimpleNamespace(send=AsyncMock(side_effect=[RuntimeError('offline'), SimpleNamespace(id=9)]))
        interaction = SimpleNamespace(
            user=SimpleNamespace(id=123, display_name='Buyer'),
            client=SimpleNamespace(warranty_store=self.store, get_channel=lambda _: channel),
            response=SimpleNamespace(defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
        )
        modal = FeedbackModal('TEST')
        modal.rating._value = '5'
        modal.comment._value = 'Good'
        with patch('ui.feedback.get_feedback_channel_id', return_value=7):
            with self.assertLogs('ui.feedback', level='ERROR'):
                await modal.on_submit(interaction)
            await modal.on_submit(interaction)
            await modal.on_submit(interaction)
        self.assertEqual(channel.send.await_count, 2)
        embed = channel.send.call_args.kwargs['embed'].to_dict()
        self.assertNotIn('private', str(embed))
        self.assertNotIn('secret', str(embed))
        self.assertIn('thử nghiệm', embed['footer']['text'])
        self.assertNotIn('TEST', str(embed))
        with self.store.connection() as db:
            self.assertEqual(db.execute('SELECT message_id FROM feedback').fetchone()[0], 9)
        self.assertTrue(FeedbackButton('TEST').is_persistent())
        modal.stop()
