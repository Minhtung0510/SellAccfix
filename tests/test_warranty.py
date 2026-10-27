import asyncio
import hashlib
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from utils.warranty import WarrantyStore, WarrantyError
from ui.warranty import WarrantyPanel, EvidenceModal, WarrantyButton, save_evidence, send_claim_result


class WarrantyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = WarrantyStore(self.root / 'warranty.db', stock_path=lambda kind: str(self.root / (kind + '.txt')))
        self.order = dict(order_code='TEST', user_id=123, account_type='14k', quantity=100, amount=1400000)
        self.accounts = [f'old{i}:password' for i in range(100)]
        self.store.record_delivery(self.order, self.accounts)
        self.store.mark_delivered('TEST')
        (self.root / '14k.txt').write_text('new1:pass\nnew2:pass\nnew3:pass\n', encoding='utf-8')
        (self.root / '5k.txt').write_text('wrong-type:pass\n', encoding='utf-8')

    def evidence(self, key):
        path = self.root / (key + '.png')
        data = b'\x89PNG\r\n\x1a\n' + key.encode()
        path.write_bytes(data)
        return dict(path=str(path), hash=hashlib.sha256(data).hexdigest())

    def claim(self, positions, keys=None):
        return self.store.create_claim('TEST', 123, positions, [self.evidence(k) for k in (keys or [str(p) for p in positions])])

    def test_exact_type_count_and_idempotent_allocation(self):
        claim = self.claim([2, 99])
        self.assertEqual(self.store.allocate(claim, 123), ['new1:pass', 'new2:pass'])
        self.assertEqual(self.store.allocate(claim, 123), ['new1:pass', 'new2:pass'])
        self.assertEqual((self.root / '14k.txt').read_text(), 'new3:pass\n')
        self.assertEqual((self.root / '5k.txt').read_text(), 'wrong-type:pass\n')
        self.assertEqual(self.store.order('TEST', 123)['used'], {2, 99})

    def test_replacements_track_positions_and_third_attempt_requires_manual(self):
        first = self.claim([2, 1], ['first2', 'first1'])
        self.store.allocate_manual(first, ['replacement2:pass', 'replacement1:pass'])
        order = self.store.order('TEST', 123)
        self.assertEqual(order['current_accounts'][:2], ['replacement1:pass', 'replacement2:pass'])
        self.assertEqual(order['accounts'][:2], self.accounts[:2])
        second = self.claim([1], ['second'])
        self.store.allocate_manual(second, ['latest:pass'])
        third = self.claim([1], ['third'])
        with self.assertRaises(WarrantyError):
            self.store.allocate(third, 123)
        self.assertEqual(self.store.get_claim(third)['state'], 'pending')
        with self.assertRaises(WarrantyError):
            self.store.allocate_manual(third, ['extra:pass', 'extra2:pass'])
        self.store.allocate_manual(third, ['checked:pass'])
        self.assertEqual(self.store.order('TEST', 123)['current_accounts'][0], 'checked:pass')

    def test_limits_owner_duplicates_and_evidence_count(self):
        with self.assertRaises(WarrantyError):
            self.store.order('TEST', 456)
        with self.assertRaises(WarrantyError):
            self.store.create_claim('TEST', 456, [1], [self.evidence('a')])
        for positions in ([101], [0], [-1], [1, 1], list(range(1, 12))):
            with self.subTest(positions=positions), self.assertRaises(WarrantyError):
                self.claim(positions)
        with self.assertRaises(WarrantyError):
            self.store.create_claim('TEST', 123, [1, 2], [self.evidence('a')])
        self.claim([1], ['first'])
        with self.assertRaises(WarrantyError):
            self.claim([1], ['second'])
        with self.assertRaises(WarrantyError):
            self.claim([2], ['first'])
        self.assertEqual(self.store.order('TEST', 123)['used'], {1})

    def test_test_order_can_reuse_evidence_after_approval_but_not_while_pending(self):
        self.store.record_delivery(dict(self.order, order_code='SANDBOX', test_order=True), self.accounts)
        self.store.mark_delivered('SANDBOX')
        proof = self.evidence('reused')
        self.store.create_claim('TEST', 123, [1], [proof])
        for attempt in range(1, 4):
            claim = self.store.create_claim('SANDBOX', 123, [1], [proof])
            self.assertEqual(self.store.get_claim(claim)['attempt'], attempt)
            with self.assertRaises(WarrantyError):
                self.store.create_claim('SANDBOX', 123, [1], [proof])
            self.store.allocate_manual(claim, [f'replacement{attempt}:pass'])
        with self.assertRaises(WarrantyError):
            self.store.create_claim('SANDBOX', 123, [1], [proof])

    def test_legacy_evidence_schema_migration_preserves_claim(self):
        claim = self.claim([1])
        with self.store.connection() as db:
            db.execute('CREATE UNIQUE INDEX legacy_evidence_unique ON claim_items(evidence_hash)')
        reopened = WarrantyStore(self.store.path, stock_path=self.store.stock_path)
        self.assertEqual(reopened.get_claim(claim)['positions'], [1])
        with reopened.connection() as db:
            indexes = list(db.execute('PRAGMA index_list(claim_items)'))
        self.assertFalse(any(r['name'] == 'legacy_evidence_unique' for r in indexes))

    def test_two_hours_normal_five_hours_off_and_no_restart_extension(self):
        start = self.store.order('TEST', 123)
        self.assertEqual(start['expires_at'] - start['delivered_at'], 5 * 3600)
        normal = dict(self.order, order_code='NORMAL', account_type='5k')
        self.store.record_delivery(normal, self.accounts)
        self.store.mark_delivered('NORMAL')
        row = self.store.order('NORMAL', 123)
        self.assertEqual(row['expires_at'] - row['delivered_at'], 2 * 3600)
        self.store.record_delivery(self.order, self.accounts)
        self.store.mark_delivered('TEST')
        self.assertEqual(self.store.order('TEST', 123)['expires_at'], start['expires_at'])
        with patch('utils.warranty.time.time', return_value=start['expires_at'] + 1):
            with self.assertRaises(WarrantyError):
                self.claim([1])

    def test_wait_for_full_correct_stock_and_redeem_after_expiry(self):
        claim = self.claim([1, 2, 3, 4])
        self.assertEqual(self.store.allocate(claim, 123), [])
        self.assertEqual((self.root / '14k.txt').read_text(), 'new1:pass\nnew2:pass\nnew3:pass\n')
        with (self.root / '14k.txt').open('a') as target:
            target.write('new4:pass\n')
        with patch('utils.warranty.time.time', return_value=time.time() + 20000):
            self.assertEqual(len(self.store.allocate(claim, 123)), 4)

    def test_restart_after_file_replace_before_db_commit(self):
        claim = self.claim([1])
        real_replace = __import__('os').replace
        def interrupted(source, target):
            real_replace(source, target)
            raise OSError('simulate process interruption after replace')
        with patch('utils.warranty.os.replace', side_effect=interrupted):
            with self.assertRaises(OSError):
                self.store.allocate(claim, 123)
        restarted = WarrantyStore(self.store.path, stock_path=self.store.stock_path)
        self.assertEqual(restarted.allocate(claim, 123), ['new1:pass'])
        self.assertEqual((self.root / '14k.txt').read_text(), 'new2:pass\nnew3:pass\n')

    def test_restart_before_file_replace_and_inventory_conflict(self):
        claim = self.claim([1])
        with patch('utils.warranty.os.replace', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                self.store.allocate(claim, 123)
        (self.root / '14k.txt').write_text('external-edit:pass\n')
        with self.assertRaises(WarrantyError):
            self.store.recover_allocations()
        self.assertEqual((self.root / '14k.txt').read_text(), 'external-edit:pass\n')

    def test_simultaneous_submits_only_accept_one(self):
        from concurrent.futures import ThreadPoolExecutor
        evidence = [self.evidence('parallelA'), self.evidence('parallelB')]
        def submit(item):
            try:
                return self.store.create_claim('TEST', 123, [1], [item])
            except WarrantyError:
                return None
        with ThreadPoolExecutor(max_workers=2) as executor:
            accepted = list(executor.map(submit, evidence))
        self.assertEqual(sum(value is not None for value in accepted), 1)
        self.assertEqual(len(self.store.claims('TEST', 123)), 1)

    def test_recovery_before_replace_succeeds(self):
        claim = self.claim([1, 2])
        with patch('utils.warranty.os.replace', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                self.store.allocate(claim, 123)
        restarted = WarrantyStore(self.store.path, stock_path=self.store.stock_path)
        restarted.recover_allocations()
        self.assertEqual(restarted.allocate(claim, 123), ['new1:pass', 'new2:pass'])
        self.assertEqual((self.root / '14k.txt').read_text(), 'new3:pass\n')

    def test_reopen_ledger_preserves_claims_and_rejects_new_accounts(self):
        claim = self.claim([1])
        restarted = WarrantyStore(self.store.path, stock_path=self.store.stock_path)
        self.assertEqual(restarted.order('TEST', 123)['used'], {1})
        with self.assertRaises(WarrantyError):
            restarted.record_delivery(self.order, ['changed'] * 100)
        self.assertEqual(restarted.claims('TEST', 123)[0]['id'], claim)


class WarrantyUITests(unittest.IsolatedAsyncioTestCase):
    async def test_paging_hundred_accounts_and_modal_requires_exact_file_count(self):
        store = Mock()
        store.order.return_value = dict(accounts=[f'user{i}:secret' for i in range(100)], used=set(),
                                       account_type='14k', expires_at=time.time() + 18000)
        view = WarrantyPanel(store, 'TEST', 123)
        self.assertEqual(view.pages, 4)
        view.page = 3
        view.refresh()
        select = next(c for c in view.children if isinstance(c, __import__('discord').ui.Select))
        self.assertEqual(select.options[0].value, '76')
        self.assertEqual(select.options[-1].value, '100')
        self.assertTrue(all('secret' not in o.label for o in select.options))
        modal = EvidenceModal('TEST', 123, [1, 2, 3])
        self.assertEqual(modal.upload.min_values, 3)
        self.assertEqual(modal.upload.max_values, 3)
        self.assertTrue(modal.upload.required)
        self.assertEqual(len(modal.to_components()), 2)
        self.assertTrue(WarrantyButton('TEST').is_persistent())
        view.stop()
        modal.stop()

    async def test_replacement_check_button_uses_claim_accounts_and_survives_restart(self):
        from ui.check_acc import CheckAccButton, get_order_account_details
        from ui.warranty import delivery_warranty_view
        import re
        claim_id = 'a' * 32
        store = Mock()
        store.order.return_value = dict(accounts=['original:pass'], account_type='5k')
        store.get_claim.return_value = dict(code='TEST', buyer=123, state='approved', replacements=['replacement:pass'])
        with patch('ui.check_acc.find_account_log_by_username', return_value=None):
            _, details = get_order_account_details(store, 'TEST', 123, claim_id)
        self.assertEqual(details[0][0]['username'], 'replacement')
        view = delivery_warranty_view('TEST', claim_id)
        button = next(c for c in view.children if isinstance(c, CheckAccButton))
        match = re.fullmatch(button.template, button.item.custom_id)
        restored = await CheckAccButton.from_custom_id(None, button.item, match)
        self.assertEqual(restored.claim_id, claim_id)
        self.assertTrue(button.is_persistent())
        self.assertTrue(any(isinstance(c, WarrantyButton) for c in view.children))
        store.get_claim.return_value['buyer'] = 456
        with self.assertRaises(ValueError):
            get_order_account_details(store, 'TEST', 123, claim_id)
        view.stop()

    async def test_persistent_button_dispatch_survives_view_cleanup(self):
        from discord.ui.view import ViewStore
        from ui.warranty import delivery_warranty_view
        store = ViewStore(Mock())
        store.add_dynamic_items(WarrantyButton)
        view = delivery_warranty_view('TEST')
        store.add_view(view, 123)
        view.stop()
        self.assertIn(WarrantyButton, store._dynamic_items.values())

    async def test_evidence_types_limits_and_same_content(self):
        with tempfile.TemporaryDirectory() as folder:
            fake = SimpleNamespace(size=5, read=AsyncMock(return_value=b'hello'))
            with self.assertRaises(WarrantyError):
                await save_evidence([fake], folder)
            good = SimpleNamespace(size=12, read=AsyncMock(return_value=b'\x89PNG\r\n\x1a\ntest'))
            with self.assertRaises(WarrantyError):
                await save_evidence([good, good], folder)
            huge = SimpleNamespace(size=30 * 1024 * 1024, read=AsyncMock())
            with self.assertRaises(WarrantyError):
                await save_evidence([huge], folder)
            huge.read.assert_not_awaited()
            evidence = await save_evidence([good], folder)
            self.assertTrue(Path(evidence[0]['path']).is_file())

    async def test_failed_discord_send_keeps_same_replacements(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            stock = root / '14k.txt'
            stock.write_text('new:pass\nnext:pass\n')
            store = WarrantyStore(root / 'ledger.db', stock_path=lambda _: str(stock))
            store.record_delivery(dict(order_code='TEST', user_id=123, account_type='14k', quantity=1), ['old:pass'])
            store.mark_delivered('TEST')
            evidence = root / 'proof.png'
            evidence.write_bytes(b'proof')
            claim = store.create_claim('TEST', 123, [1], [{'path': str(evidence), 'hash': hashlib.sha256(b'proof').hexdigest()}])
            interaction = SimpleNamespace(user=SimpleNamespace(id=123), client=Mock(),
                                          followup=SimpleNamespace(send=AsyncMock(side_effect=[RuntimeError('network'), None])))
            with self.assertRaises(RuntimeError):
                await send_claim_result(interaction, store, 'TEST', claim)
            await send_claim_result(interaction, store, 'TEST', claim)
            self.assertEqual(stock.read_text(), 'next:pass\n')
            self.assertEqual(store.claims('TEST', 123)[0]['replacements'], ['new:pass'])

    async def test_manual_admin_approval_and_rejection_and_retrieval(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = WarrantyStore(root / 'ledger.db', stock_path=lambda _: str(root / 'stock.txt'))
            store.record_delivery(dict(order_code='ORD1', user_id=123, account_type='5k', quantity=1), ['user1:pass1'])
            store.mark_delivered('ORD1')
            proof = root / 'proof.png'
            proof.write_bytes(b'proof')
            claim_id = store.create_claim('ORD1', 123, [1], [{'path': str(proof), 'hash': hashlib.sha256(b'proof').hexdigest()}])
            
            # Verify pending claim retrieval
            data = store.get_claim(claim_id)
            self.assertIsNotNone(data)
            self.assertEqual(data['state'], 'pending')
            self.assertEqual(data['buyer'], 123)
            self.assertEqual(data['positions'], [1])

            # Test allocate_manual
            store.allocate_manual(claim_id, ['manual_user:manual_pass'], admin_id=999, note="Bù acc VIP")
            data_after = store.get_claim(claim_id)
            self.assertEqual(data_after['state'], 'approved')
            self.assertEqual(data_after['admin_id'], 999)
            self.assertEqual(data_after['admin_note'], 'Bù acc VIP')
            self.assertEqual(data_after['replacements'], ['manual_user:manual_pass'])

            # Reject test
            store.record_delivery(dict(order_code='ORD2', user_id=123, account_type='5k', quantity=1), ['user2:pass2'])
            store.mark_delivered('ORD2')
            proof2 = root / 'proof2.png'
            proof2.write_bytes(b'proof2')
            claim_id_2 = store.create_claim('ORD2', 123, [1], [{'path': str(proof2), 'hash': hashlib.sha256(b'proof2').hexdigest()}])
            store.reject_claim(claim_id_2, admin_id=999, reason="Clip không rõ")
            data_rej = store.get_claim(claim_id_2)
            self.assertEqual(data_rej['state'], 'rejected')
            self.assertEqual(data_rej['admin_note'], 'Clip không rõ')

    async def test_single_account_order_auto_selects(self):
        store = Mock()
        store.order.return_value = dict(accounts=['single_user:pass'], used=set(),
                                       account_type='5k', expires_at=time.time() + 7200)
        panel = WarrantyPanel(store, 'SINGLE', 123)
        self.assertEqual(panel.selected, [1])
        # AccountPicker should not be present because only 1 acc is available
        self.assertFalse(any(isinstance(c, __import__('discord').ui.Select) for c in panel.children))
        panel.stop()

    async def test_all_admin_dynamic_items_are_persistent(self):
        from ui.warranty import ApproveStockWarrantyButton, ApproveManualWarrantyButton, RejectWarrantyButton
        self.assertTrue(ApproveStockWarrantyButton('cid').is_persistent())
        self.assertTrue(ApproveManualWarrantyButton('cid').is_persistent())
        self.assertTrue(RejectWarrantyButton('cid').is_persistent())

    async def test_three_attempts_warranty_flow_and_two_buttons_on_attempt_three(self):
        from ui.warranty import AdminWarrantyActionView, ApproveStockWarrantyButton, ApproveManualWarrantyButton, RejectWarrantyButton
        # Check AdminWarrantyActionView on attempt 1, 2, 3
        v1 = AdminWarrantyActionView('cid', attempt=1)
        self.assertEqual(len(v1.children), 3)
        self.assertTrue(any(isinstance(c, ApproveStockWarrantyButton) for c in v1.children))

        v2 = AdminWarrantyActionView('cid', attempt=2)
        self.assertEqual(len(v2.children), 3)

        v3 = AdminWarrantyActionView('cid', attempt=3)
        # Attempt 3 MUST have exactly 2 buttons: check tay and tu choi
        self.assertEqual(len(v3.children), 2)
        self.assertFalse(any(isinstance(c, ApproveStockWarrantyButton) for c in v3.children))
        manual_btn = next(c for c in v3.children if isinstance(c, ApproveManualWarrantyButton))
        self.assertEqual(manual_btn.label, "Check tay & Bù acc")
        self.assertTrue(any(isinstance(c, RejectWarrantyButton) for c in v3.children))

        # Check DB attempt progression & max 3 limit
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = WarrantyStore(root / 'ledger.db', stock_path=lambda _: str(root / 'stock.txt'))
            store.record_delivery(dict(order_code='ORD3', user_id=123, account_type='5k', quantity=1), ['user3:pass3'])
            store.mark_delivered('ORD3')

            # Claim 1
            p1 = root / 'p1.png'
            p1.write_bytes(b'p1')
            c1 = store.create_claim('ORD3', 123, [1], [{'path': str(p1), 'hash': hashlib.sha256(b'p1').hexdigest()}])
            self.assertEqual(store.get_claim(c1)['attempt'], 1)
            store.allocate_manual(c1, ['repl1:pass1'], admin_id=1)

            # Claim 2 (replacement 1 also broken)
            p2 = root / 'p2.png'
            p2.write_bytes(b'p2')
            c2 = store.create_claim('ORD3', 123, [1], [{'path': str(p2), 'hash': hashlib.sha256(b'p2').hexdigest()}])
            self.assertEqual(store.get_claim(c2)['attempt'], 2)
            store.allocate_manual(c2, ['repl2:pass2'], admin_id=1)

            # Claim 3 (replacement 2 also broken)
            p3 = root / 'p3.png'
            p3.write_bytes(b'p3')
            c3 = store.create_claim('ORD3', 123, [1], [{'path': str(p3), 'hash': hashlib.sha256(b'p3').hexdigest()}])
            self.assertEqual(store.get_claim(c3)['attempt'], 3)
            store.allocate_manual(c3, ['repl3:pass3'], admin_id=1)

            # Claim 4 should be rejected because max 3 attempts reached
            p4 = root / 'p4.png'
            p4.write_bytes(b'p4')
            with self.assertRaises(WarrantyError) as ctx:
                store.create_claim('ORD3', 123, [1], [{'path': str(p4), 'hash': hashlib.sha256(b'p4').hexdigest()}])
            self.assertIn('3 lần bảo hành', str(ctx.exception))


