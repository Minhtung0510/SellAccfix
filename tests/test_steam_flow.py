import asyncio
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import discord

from utils.steam_storage import (
    parse_steam_account_line,
    search_steam_accounts,
    allocate_steam_accounts,
    get_total_steam_count,
    STEAM_TIERS,
)
from ui.views import SteamSearchModal, SteamTierSelect, SteamQuantityModal, AccountView
from Modules.CreateMessage import build_buy_acc_message, build_delivery_message


class SteamFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.sample_lines = [
            "[101/1000] ✅ user_cs_1:pass1 | SteamID: 10001 | Lvl:0 | Games:1 | Wallet:0 | Country:VN | Games: [Counter-Strike 2] || CS2 Prime : Not Active ❌ || VAC : Clean ✅",
            "[102/1000] ✅ user_cs_4:pass2 | SteamID: 10002 | Lvl:2 | Games:4 | Wallet:$1.00 USD | Country:US | Games: [Counter-Strike 2, PUBG, Apex Legends, Warframe] || CS2 Prime : Not Active ❌ || VAC : Clean ✅",
            "[103/1000] ✅ user_cs_15:pass3 | SteamID: 10003 | Lvl:5 | Games:15 | Wallet:¥ 10 | Country:CN | Games: [Counter-Strike 2, GTA V, R6, Cyberpunk 2077] || CS2 Prime : Not Active ❌ || VAC : Clean ✅",
            "[104/1000] ✅ user_cod_2:pass4 | SteamID: 10004 | Lvl:1 | Games:2 | Wallet:0 | Country:TH | Games: [Call of Duty®, Battlefield 6] || CS2 Prime : Not Active ❌ || VAC : Clean ✅",
        ]
        tmp = tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False)
        tmp.write("\n".join(self.sample_lines) + "\n")
        tmp.close()
        self.tmp_path = tmp.name

    def tearDown(self):
        if os.path.exists(self.tmp_path):
            os.remove(self.tmp_path)

    def test_search_steam_accounts_grouping_and_sorting(self):
        results = search_steam_accounts("Counter-Strike 2", file_path=self.tmp_path)
        # Tier 1 (0-10 games): user_cs_1 (1 game) and user_cs_4 (4 games)
        tier1 = results["steam_tier_1"]
        self.assertEqual(len(tier1), 2)
        # Verify optimized ascending order: least games delivered first!
        self.assertEqual(tier1[0]["username"], "user_cs_1")
        self.assertEqual(tier1[0]["game_count"], 1)
        self.assertEqual(tier1[1]["username"], "user_cs_4")
        self.assertEqual(tier1[1]["game_count"], 4)

        # Tier 2 (11-40 games): user_cs_15 (15 games)
        tier2 = results["steam_tier_2"]
        self.assertEqual(len(tier2), 1)
        self.assertEqual(tier2[0]["username"], "user_cs_15")
        self.assertEqual(tier2[0]["game_count"], 15)

    def test_alias_search(self):
        # Searching "cs2" alias finds Counter-Strike 2
        results = search_steam_accounts("cs2", file_path=self.tmp_path)
        self.assertEqual(len(results["steam_tier_1"]), 2)
        self.assertEqual(len(results["steam_tier_2"]), 1)

        # Searching "cod" alias finds Call of Duty
        results_cod = search_steam_accounts("cod", file_path=self.tmp_path)
        self.assertEqual(len(results_cod["steam_tier_1"]), 1)
        self.assertEqual(results_cod["steam_tier_1"][0]["username"], "user_cod_2")

    def test_allocate_steam_accounts_optimal_least_games(self):
        # Allocating 1 account from tier 1 should pick user_cs_1 (1 game), NOT user_cs_4 (4 games)
        allocated = allocate_steam_accounts("Counter-Strike 2", "steam_tier_1", 1, file_path=self.tmp_path)
        self.assertEqual(len(allocated), 1)
        self.assertEqual(allocated[0]["username"], "user_cs_1")
        self.assertEqual(allocated[0]["game_count"], 1)

        # After allocation, user_cs_1 should be removed from file, leaving 3 accounts
        remaining = get_total_steam_count(file_path=self.tmp_path)
        self.assertEqual(remaining, 3)

        # Next allocation picks user_cs_4
        allocated_next = allocate_steam_accounts("Counter-Strike 2", "steam_tier_1", 1, file_path=self.tmp_path)
        self.assertEqual(len(allocated_next), 1)
        self.assertEqual(allocated_next[0]["username"], "user_cs_4")

        # Now tier 1 is empty for CS2
        allocated_empty = allocate_steam_accounts("Counter-Strike 2", "steam_tier_1", 1, file_path=self.tmp_path)
        self.assertEqual(len(allocated_empty), 0)

    def test_build_buy_acc_message_steam(self):
        embed = build_buy_acc_message(game="steam")
        self.assertIn("STEAM", embed.title)
        field_names = [f.name for f in embed.fields]
        self.assertTrue(any("0 - 10" in name for name in field_names))
        self.assertTrue(any("11 - 40" in name for name in field_names))
        self.assertTrue(any("41+" in name for name in field_names))

    def test_build_delivery_message_steam(self):
        order = {
            "order_code": "DTFF-STM-001",
            "account_type": "steam_tier_1",
            "game": "steam",
            "steam_game": "Counter-Strike 2",
            "quantity": 1,
            "amount": 5000,
        }
        accounts = [
            "[101/1000] ✅ user_cs_1:pass1 | SteamID: 10001 | Lvl:0 | Games:1 | Wallet:0 | Country:VN | Games: [Counter-Strike 2] || CS2 Prime : Not Active ❌ || VAC : Clean ✅"
        ]
        embed, as_file = build_delivery_message(order, accounts)
        self.assertIn("STEAM", embed.title)
        self.assertIn("user_cs_1", embed.fields[5].value)
        self.assertEqual(embed.fields[2].value, "**5.000 VNĐ**")


if __name__ == "__main__":
    unittest.main()
