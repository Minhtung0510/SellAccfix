import unittest
import os
import shutil
import tempfile
import discord
from unittest.mock import MagicMock, AsyncMock

from utils.warranty import WarrantyStore
from ui.warranty import delivery_warranty_view, WarrantyButton
from ui.check_acc import (
    CheckAccButton,
    CheckAccDetailView,
    get_order_account_details,
    find_account_log_by_username,
    build_account_check_embed,
)
from Modules.AccountProcess import split_raw_accounts, get_acc_count, get_random_acc


SAMPLE_CHECKER_BLOCKS = """Username: kensferr
Password: WERT7654321e
Region: NA
Riot ID: DyroneTavis#DARKE
Email Verified: True
Phone Verified: False
Level: 76
Valorant Points: 137
Radianite Points: 85
Kingdom Credits: 3423
Last Game Date: 28/04/2026 21:12:51

Weapons (64):
- Blush Frenzy
- Blush Operator
- ChronoVoid Phantom
- Elderflame Operator
- Prime Vandal

Knives (2):
- Xenohunter Knife

Current Rank: Unranked (V26:A5)
Previous Rated Rank: Silver 1 (E7:A3)
Peak Rank: Silver 1 (E7:A3)
Eligible for Rated Play: True

---------------------------
Username: CoBr3S9
Password: Brendalyn9
Region: NA
Riot ID: Cobraz RE#BDB
Email Verified: True
Phone Verified: True
Level: 138
Valorant Points: 279
Radianite Points: 50
Kingdom Credits: 3062
Last Game Date: 21/09/2026 06:48:45

Weapons (57):
- .SYS Bucky
- Elderflame Vandal
- Reaver Ghost
- Sentinels of Light Vandal

Knives (6):
- Prime//2.0 Karambit

Current Rank: Bronze 3 (V26:A5)
Previous Rated Rank: Silver 2 (E7:A1)
Peak Rank: Platinum 1 (E6:A2)
Eligible for Rated Play: True
"""


class TestE2ECheckAcc(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "warranty.sqlite3")
        self.store = WarrantyStore(path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_delivery_view_has_both_buttons(self):
        code = "DTFF-TEST999"
        view = delivery_warranty_view(code)
        items = view.children
        self.assertEqual(len(items), 3)
        button_types = [type(item) for item in items]
        self.assertIn(CheckAccButton, button_types)
        self.assertIn(WarrantyButton, button_types)

        check_btn = next(item for item in items if isinstance(item, CheckAccButton))
        self.assertEqual(check_btn.item.custom_id, f"checkacc:{code}")
        self.assertEqual(check_btn.item.label, "Check Acc")

    def test_e2e_delivery_and_check_acc(self):
        code = "DTFF-ORDER-E2E"
        user_id = 9876543210
        accs = split_raw_accounts(SAMPLE_CHECKER_BLOCKS)
        self.assertEqual(len(accs), 2)

        order = {
            "order_code": code,
            "user_id": user_id,
            "account_type": "5k",
            "quantity": 2,
            "amount": 10000,
        }

        # 1. Record delivery
        self.store.record_delivery(order, accs)
        self.store.mark_delivered(code)

        # 2. Retrieve account details
        retrieved_order, accounts_data = get_order_account_details(self.store, code, user_id)
        self.assertEqual(len(accounts_data), 2)

        # Acc 1 validation
        acc1_data, raw1 = accounts_data[0]
        self.assertEqual(acc1_data["username"], "kensferr")
        self.assertEqual(acc1_data["riot_id"], "DyroneTavis#DARKE")
        self.assertEqual(acc1_data["level"], "76")
        self.assertEqual(int(acc1_data["vp"]), 137)
        self.assertEqual(acc1_data["knives_count"], 1)
        self.assertIn("Xenohunter Knife", [s["name"] for s in acc1_data["skins"]])

        # Acc 2 validation
        acc2_data, raw2 = accounts_data[1]
        self.assertEqual(acc2_data["username"], "CoBr3S9")
        self.assertEqual(acc2_data["riot_id"], "Cobraz RE#BDB")
        self.assertEqual(acc2_data["current_rank"], "Bronze 3 (V26:A5)")

        # 3. View creation and validation
        view = CheckAccDetailView(code, accounts_data, current_index=0, buyer_id=user_id)
        emb1 = view.get_current_embed()
        self.assertIn("DyroneTavis#DARKE", emb1.title)
        self.assertIn("kensferr", str(emb1.to_dict()))

        # Navigation
        view.current_index = 1
        emb2 = view.get_current_embed()
        self.assertIn("Cobraz RE#BDB", emb2.title)
        self.assertIn("CoBr3S9", str(emb2.to_dict()))

    def test_single_acc_order_view(self):
        code = "DTFF-ORDER-SINGLE"
        user_id = 111222333
        accs = [split_raw_accounts(SAMPLE_CHECKER_BLOCKS)[0]]

        order = {
            "order_code": code,
            "user_id": user_id,
            "account_type": "5k",
            "quantity": 1,
            "amount": 5000,
        }

        self.store.record_delivery(order, accs)
        self.store.mark_delivered(code)

        _order, accounts_data = get_order_account_details(self.store, code, user_id)
        self.assertEqual(len(accounts_data), 1)

        view = CheckAccDetailView(code, accounts_data, current_index=0, buyer_id=user_id)
        self.assertTrue(view.btn_prev.disabled)
        self.assertTrue(view.btn_next.disabled)

    def test_check_acc_action_view(self):
        from ui.check_acc import CheckAccActionView
        code = "TEST-ORDER-ACTION"
        accounts_data = [({"username": "user1", "password": "p1"}, "")]
        view = CheckAccActionView(code, accounts_data, current_index=0)
        labels = [item.label for item in view.children]
        self.assertIn("Sao chép TK:MK", labels)
        self.assertIn("Tải File HTML", labels)


if __name__ == "__main__":
    unittest.main()


