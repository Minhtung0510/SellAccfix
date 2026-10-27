import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from discord.ext import commands

from ui.check_acc import (
    find_account_log_by_username,
    get_order_account_details,
    build_account_check_embed,
    CheckAccDetailView,
    CheckAccButton,
)
from utils.html_generator import parse_checker_text
from utils.warranty import WarrantyStore


SAMPLE_LOG_TEXT = """Username: kensferr
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
"""


class TestCheckAcc(unittest.TestCase):
    def setUp(self):
        import os
        from utils.constants import ROOT_DIR
        self.log_path = os.path.join(ROOT_DIR, "data", "logs", "test_sample_check.txt")
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write(SAMPLE_LOG_TEXT)

    def tearDown(self):
        import os
        if os.path.exists(self.log_path):
            os.remove(self.log_path)

    def test_find_account_log(self):
        log = find_account_log_by_username("kensferr")
        self.assertIsNotNone(log)
        self.assertIn("WERT7654321e", log)
        self.assertIn("DyroneTavis#DARKE", log)

    def test_embed_builder_valid_bounds(self):
        parsed = parse_checker_text(SAMPLE_LOG_TEXT)
        self.assertTrue(len(parsed) > 0)
        embed = build_account_check_embed(parsed[0], 0, 1, "ORDER-TEST-001")
        self.assertIsInstance(embed, discord.Embed)
        self.assertIn("kensferr", str(embed.fields[0].value))
        for f in embed.fields:
            self.assertLessEqual(len(f.value), 1024)
            self.assertLessEqual(len(f.name), 256)

    def test_view_paging_and_components(self):
        parsed = parse_checker_text(SAMPLE_LOG_TEXT)
        accounts_data = [
            (parsed[0], SAMPLE_LOG_TEXT),
            (parsed[0], SAMPLE_LOG_TEXT),
        ]
        view = CheckAccDetailView("ORDER-TEST-002", accounts_data, current_index=0, buyer_id=123)
        self.assertEqual(len(view.accounts_data), 2)
        self.assertTrue(view.btn_prev.disabled)
        self.assertFalse(view.btn_next.disabled)

    def test_check_acc_button_dynamic_template(self):
        button = CheckAccButton("DTFF-123456")
        self.assertEqual(button.code, "DTFF-123456")
        self.assertEqual(button.item.custom_id, "checkacc:DTFF-123456")


if __name__ == "__main__":
    unittest.main()
