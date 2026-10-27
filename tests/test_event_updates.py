import asyncio
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from Modules import AccountProcess as stock
from Modules import PaymentOrder as storage
from Modules.pay import check_payment_status
from cogs.orders import OrdersCog
from ui.views import AccountView


class StockTests(unittest.TestCase):
    def test_count_cache_and_file_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'stock.txt')
            Path(path).write_text('a\n\nb\n', encoding='utf-8')
            self.assertEqual(stock.get_acc_count(path), 2)
            with patch('builtins.open', side_effect=AssertionError('cache should avoid read')):
                self.assertEqual(stock.get_acc_count(path), 2)
            Path(path).write_text('a\nb\nc\n', encoding='utf-8')
            self.assertEqual(stock.get_acc_count(path), 3)

    def test_delivery_streams_and_insufficient_stock_keeps_original(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'stock.txt')
            Path(path).write_text('a\nb\nc\n', encoding='utf-8')
            with patch.object(stock, 'get_account_file_path', return_value=path):
                self.assertEqual(stock.get_random_acc('test', 4), [])
                self.assertEqual(Path(path).read_text(), 'a\nb\nc\n')
                self.assertEqual(stock.get_random_acc('test', 2), ['a', 'b'])
                self.assertEqual(stock.get_acc_count(path), 1)
                self.assertEqual(Path(path).read_text(), 'c\n')

    def test_shared_history_never_fetches_again(self):
        with patch('Modules.pay._fetch_history', side_effect=AssertionError('unexpected network')):
            self.assertFalse(check_payment_status({'order_code': 'ABC'}, {}))
            history = {'status': True, 'data': [{'description': 'ACC-ABC', 'creditAmount': '5,000'}]}
            self.assertTrue(check_payment_status({'order_code': 'ABC', 'amount': 5000}, history))
            self.assertFalse(check_payment_status({'order_code': 'ABC', 'amount': 6000}, history))


class EventTests(unittest.IsolatedAsyncioTestCase):
    def make_cog(self):
        bot = Mock()
        bot.wait_until_ready = AsyncMock()
        cog = OrdersCog(bot)
        # Most tests exercise UI behavior without writing runtime cooldown state.
        cog._defer_stock_edit = Mock()
        return cog

    async def test_stock_cooldown_survives_restart(self):
        from utils import storage as state
        with tempfile.TemporaryDirectory() as folder, patch.object(state, 'STOCK_STATE_FILE', str(Path(folder) / 'state.json')):
            first = self.make_cog()
            with patch('cogs.orders.time.time', return_value=1000):
                first._restore_stock_cooldown()
            self.assertEqual(first._stock_next_edit, 1600)
            second = self.make_cog()
            with patch('cogs.orders.time.time', return_value=1100):
                second._restore_stock_cooldown()
            self.assertEqual(second._stock_next_edit, 1600)
            with patch('cogs.orders.time.time', return_value=1700):
                OrdersCog._defer_stock_edit(second)
            self.assertEqual(state.load_stock_cooldown(1416059603996901427), 2300)

    async def test_stock_cooldown_prevents_early_rename(self):
        cog = self.make_cog()
        cog._stock_next_edit = time.time() + 600
        channel = SimpleNamespace(name='old', edit=AsyncMock())
        cog.bot.get_channel.return_value = channel
        with patch('cogs.orders.get_acc_count', return_value=2):
            await cog.update_stock_channel()
        channel.edit.assert_not_awaited()
        self.assertTrue(cog._stock_changed.is_set())

    async def test_stock_worker_resumes_automatically_after_cooldown(self):
        cog = self.make_cog()
        cog._stock_next_edit = time.time() + 0.08
        done = asyncio.Event()
        async def update():
            done.set()
        cog.update_stock_channel = AsyncMock(side_effect=update)
        with self.assertLogs('discord.stock', level='INFO') as logs:
            task = asyncio.create_task(cog._stock_worker())
            cog._stock_changed.set()
            try:
                await asyncio.wait_for(done.wait(), timeout=1)
                cog.update_stock_channel.assert_awaited_once()
                self.assertIn('1416059603996901427', logs.output[0])
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def test_stock_channel_counts_unique_files_and_skips_unchanged(self):
        cog = self.make_cog()
        channel = SimpleNamespace(name="old", edit=AsyncMock())
        cog.bot.get_channel.return_value = channel
        choices = [('a', 'a', 'one.txt', 0), ('b', 'b', 'one.txt', 0), ('c', 'c', 'two.txt', 0)]
        with patch('cogs.orders.ACCOUNT_CHOICES', choices), patch('cogs.orders.get_acc_count', return_value=5):
            await cog.update_stock_channel()
            await cog.update_stock_channel()
        channel.edit.assert_awaited_once()
        self.assertEqual(channel.edit.call_args.kwargs['name'], '🟢 CÒN 10 TÀI KHOẢN')
        cog.bot.get_channel.assert_called_once_with(1416059603996901427)

    async def test_stock_channel_updates_total_when_stock_changes(self):
        cog = self.make_cog()
        channel = SimpleNamespace(name="old", edit=AsyncMock())
        cog.bot.get_channel.return_value = channel
        choices = [('a', '5k', 'one', 0), ('b', '40koff', 'two', 0)]
        with patch('cogs.orders.ACCOUNT_CHOICES', choices), patch('cogs.orders.get_acc_count', side_effect=[12, 0, 0, 3]):
            await cog.update_stock_channel()
            self.assertEqual(channel.edit.call_args.kwargs['name'], '🟢 CÒN 12 TÀI KHOẢN')
            await cog.update_stock_channel()
            self.assertEqual(channel.edit.call_args.kwargs['name'], '🟢 CÒN 3 TÀI KHOẢN')

    async def test_stock_channel_zero_and_existing_name(self):
        cog = self.make_cog()
        channel = SimpleNamespace(name='🔴 HẾT TÀI KHOẢN', edit=AsyncMock())
        cog.bot.get_channel.return_value = channel
        with patch('cogs.orders.get_acc_count', return_value=0):
            await cog.update_stock_channel()
        channel.edit.assert_not_awaited()
        self.assertEqual(cog._stock_name, channel.name)

    async def test_stock_worker_idle_and_refresh_signal(self):
        cog = self.make_cog()
        cog.update_stock_channel = AsyncMock()
        task = asyncio.create_task(cog._stock_worker())
        await asyncio.sleep(0.02)
        cog.update_stock_channel.assert_not_awaited()
        cog.request_menu_refresh()
        await asyncio.sleep(0.6)
        cog.update_stock_channel.assert_awaited_once()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def test_idle_worker_does_not_poll_files_or_bank(self):
        cog = self.make_cog()
        with patch('cogs.orders.load_orders', return_value=[]) as load, patch('cogs.orders._fetch_history') as fetch:
            task = asyncio.create_task(cog._order_worker())
            await asyncio.sleep(0.02)
            self.assertEqual(load.call_count, 1)
            fetch.assert_not_called()
            cog.notify_orders_changed()
            await asyncio.sleep(0.02)
            self.assertEqual(load.call_count, 2)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_batch_uses_single_bank_request(self):
        cog = self.make_cog()
        processed = asyncio.Event()
        async def process(order, history):
            if order['order_code'] == 'b':
                processed.set()
        cog._process_order = AsyncMock(side_effect=process)
        with patch('cogs.orders.load_orders', return_value=[{'order_code': 'a'}, {'order_code': 'b'}]), patch('cogs.orders._fetch_history', return_value={}) as fetch:
            task = asyncio.create_task(cog._order_worker())
            await asyncio.wait_for(processed.wait(), 1)
            fetch.assert_called_once()
            self.assertEqual(cog._process_order.await_count, 2)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_unchanged_menu_skips_edit_and_force_refreshes(self):
        cog = self.make_cog()
        message = SimpleNamespace(edit=AsyncMock())
        cog.bot.get_channel.return_value.get_partial_message.return_value = message
        with patch('cogs.orders.load_menus', return_value=[{'channel_id': 1, 'message_id': 2}]), patch('ui.views.get_acc_count', return_value=5):
            self.assertEqual(await cog.refresh_menus(), 1)
            self.assertEqual(await cog.refresh_menus(), 0)
            self.assertEqual(await cog.refresh_menus(force=True), 1)
            self.assertEqual(message.edit.await_count, 2)

    async def test_global_view_remains_after_temporary_view_removed(self):
        from discord.ui.view import ViewStore
        store = ViewStore(Mock())
        global_view = AccountView()
        local_view = AccountView()
        store.add_view(global_view)
        store.add_view(local_view, 123)
        local_view.stop()
        self.assertIn(None, store._views)
        self.assertNotIn(123, store._views)
        global_view.stop()

    async def test_failed_delivery_reuses_assigned_accounts(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(storage, 'ORDERS_FILE', str(Path(folder) / 'orders.json')):
            order = {'order_code': 'x', 'created_at': time.time(), 'user_id': 1, 'message_id': 2, 'account_type': '5k', 'quantity': 1}
            storage.add_order(order)
            cog = self.make_cog()
            destination = Mock()
            destination.send = AsyncMock(side_effect=[RuntimeError('offline'), None])
            destination.get_partial_message.return_value.delete = AsyncMock()
            cog._destination = AsyncMock(return_value=destination)
            with patch('cogs.orders.check_payment_status', return_value=True), patch('cogs.orders.get_random_acc', return_value=['account']) as take:
                with self.assertRaises(RuntimeError):
                    await cog._process_order(order, {})
                saved = storage.load_orders()[0]
                self.assertEqual(saved['delivery_accounts'], ['account'])
                await cog._process_order(saved, {})
                take.assert_called_once()
                self.assertEqual(storage.load_orders(), [])


if __name__ == '__main__':
    unittest.main()
