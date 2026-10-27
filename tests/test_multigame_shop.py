import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import discord
from ui.views import GameSelect, AccountSelect, AccountView
from utils.constants import (
    GAMES,
    GAME_CHOICES,
    VALORANT_CHOICES,
    CSGO2_CHOICES,
    PRICE_MAP,
    DISPLAY_PRICE,
    ACCOUNT_TYPE_NAME,
    ACCOUNT_FILES,
    get_account_file_path,
)
from Modules.CreateMessage import build_buy_acc_message
from ui.check_acc import build_check_acc_card, build_account_check_embed


class MultiGameShopTests(unittest.IsolatedAsyncioTestCase):
    def test_csgo2_prime_constants(self):
        self.assertEqual(PRICE_MAP["cs2_prime"], 50000)
        self.assertEqual(DISPLAY_PRICE["cs2_prime"], "50k")
        self.assertIn("CSGO 2 Prime", ACCOUNT_TYPE_NAME["cs2_prime"])
        self.assertEqual(ACCOUNT_FILES["cs2_prime"], "cs2_prime.txt")
        self.assertTrue(get_account_file_path("cs2_prime").endswith("cs2_prime.txt"))

        # CSGO 2 only sells CSGO 2 Prime
        self.assertEqual(len(CSGO2_CHOICES), 1)
        self.assertEqual(CSGO2_CHOICES[0][1], "cs2_prime")

    def test_games_list(self):
        game_values = [g[1] for g in GAMES]
        self.assertIn("valorant", game_values)
        self.assertIn("csgo2", game_values)
        self.assertIn("steam", game_values)
        self.assertEqual(len(GAMES), 3)

    def test_account_view_initialization(self):
        from ui.views import SteamSearchButton
        view_val = AccountView(current_game="valorant")
        self.assertEqual(len(view_val.children), 2)
        game_sel_val = view_val.children[0]
        acc_sel_val = view_val.children[1]
        self.assertIsInstance(game_sel_val, GameSelect)
        self.assertIsInstance(acc_sel_val, AccountSelect)
        self.assertEqual(len(acc_sel_val.options), len(VALORANT_CHOICES))
        self.assertEqual(game_sel_val.options[0].emoji.name, "dtff_valorant")
        self.assertEqual(game_sel_val.options[1].emoji.name, "dtff_cs2")
        self.assertEqual(game_sel_val.options[2].emoji.name, "dtff_steam")

        view_cs = AccountView(current_game="csgo2")
        acc_sel_cs = view_cs.children[1]
        self.assertEqual(len(acc_sel_cs.options), 1)
        self.assertEqual(acc_sel_cs.options[0].value, "cs2_prime")
        self.assertEqual(acc_sel_cs.options[0].emoji.name, "dtff_cs2")
        self.assertIn("50,000đ", acc_sel_cs.options[0].description)

        view_steam = AccountView(current_game="steam")
        self.assertEqual(len(view_steam.children), 2)
        self.assertIsInstance(view_steam.children[0], GameSelect)
        self.assertIsInstance(view_steam.children[1], SteamSearchButton)
        self.assertEqual(view_steam.children[1].custom_id, "steam_search_button")

    async def test_game_select_callback_switches_to_csgo2(self):
        game_select = GameSelect(current_game="valorant")
        game_select._values = ["csgo2"]

        interaction = SimpleNamespace(
            response=SimpleNamespace(edit_message=AsyncMock()),
            client=Mock(),
        )

        await game_select.callback(interaction)

        interaction.response.edit_message.assert_awaited_once()
        kwargs = interaction.response.edit_message.call_args.kwargs
        embed = kwargs["embed"]
        view = kwargs["view"]

        self.assertIn("CSGO 2", embed.title)
        self.assertIsInstance(view, AccountView)
        self.assertEqual(view.current_game, "csgo2")

        acc_select = view.children[1]
        self.assertEqual(len(acc_select.options), 1)
        self.assertEqual(acc_select.options[0].value, "cs2_prime")
        for att in kwargs.get("attachments", []):
            att.close()

    async def test_buy_csgo2_modal_submission_preserves_game(self):
        with patch("ui.views.get_acc_count", return_value=5):
            select = AccountSelect(current_game="csgo2")
            select._values = ["cs2_prime"]
            interaction = SimpleNamespace(
                response=SimpleNamespace(send_modal=AsyncMock()),
                client=Mock(),
                message=SimpleNamespace(id=999, edit=AsyncMock()),
            )

            await select.callback(interaction)

            modal = interaction.response.send_modal.call_args.args[0]
            self.assertEqual(modal.selected_value, "cs2_prime")
            self.assertEqual(modal.stock_count, 5)

            view = interaction.message.edit.call_args.kwargs["view"]
            self.assertEqual(view.current_game, "csgo2")
            acc_select = view.children[1]
            self.assertEqual(len(acc_select.options), 1)
            self.assertEqual(acc_select.options[0].value, "cs2_prime")

    def test_csgo2_check_acc_card(self):
        data = {
            "username": "steam_user_1",
            "password": "steam_pass_1",
            "is_cs": True,
        }
        embed, img_file = build_check_acc_card("ORDER-CS-001", data, 0, 1)
        self.assertIsNotNone(img_file)
        self.assertEqual(img_file.filename, "cs2_logo.png")
        self.assertIn("CSGO 2 PRIME", embed.title)
        self.assertIn("steam_user_1", embed.description)
        self.assertEqual(embed.thumbnail.url, "attachment://cs2_logo.png")
        img_file.close()

        embed_detail = build_account_check_embed(data, 0, 1, "ORDER-CS-001")
        self.assertIn("CSGO 2", embed_detail.title)
        self.assertIn("Steam", embed_detail.fields[0].name)
        self.assertEqual(embed_detail.thumbnail.url, "attachment://cs2_logo.png")

    def test_steam_pricing_and_tiers(self):
        self.assertEqual(PRICE_MAP["steam_tier_1"], 5000)
        self.assertEqual(PRICE_MAP["steam_tier_2"], 15000)
        self.assertEqual(PRICE_MAP["steam_tier_3"], 25000)

        self.assertEqual(DISPLAY_PRICE["steam_tier_1"], "5k")
        self.assertEqual(DISPLAY_PRICE["steam_tier_2"], "15k")
        self.assertEqual(DISPLAY_PRICE["steam_tier_3"], "25k")

        self.assertIn("0 - 10 Games", ACCOUNT_TYPE_NAME["steam_tier_1"])
        self.assertIn("11 - 40 Games", ACCOUNT_TYPE_NAME["steam_tier_2"])
        self.assertIn("41+ Games", ACCOUNT_TYPE_NAME["steam_tier_3"])

    def test_steam_parsing_and_optimization_sorting(self):
        import tempfile
        from utils.steam_storage import parse_steam_account_line, search_steam_accounts

        lines = [
            "[100/1000] ✅ user_high:pass1 | SteamID: 111 | Lvl:5 | Games:8 | Wallet:0 | Country:US | Games: [Counter-Strike 2, GameA, GameB, GameC, GameD, GameE, GameF, GameG]",
            "[101/1000] ✅ user_low:pass2 | SteamID: 222 | Lvl:0 | Games:2 | Wallet:0 | Country:VN | Games: [Counter-Strike 2, GameA]",
            "[102/1000] ✅ user_mid:pass3 | SteamID: 333 | Lvl:1 | Games:5 | Wallet:0 | Country:JP | Games: [Counter-Strike 2, Game1, Game2, Game3, Game4]",
        ]

        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as tmp:
            tmp.write("\n".join(lines) + "\n")
            tmp_name = tmp.name

        try:
            results = search_steam_accounts("Counter-Strike 2", file_path=tmp_name)
            tier1 = results["steam_tier_1"]
            self.assertEqual(len(tier1), 3)
            # Must be sorted ascending by game_count for optimization
            self.assertEqual([a["game_count"] for a in tier1], [2, 5, 8])
            self.assertEqual(tier1[0]["username"], "user_low")
            self.assertEqual(tier1[1]["username"], "user_mid")
            self.assertEqual(tier1[2]["username"], "user_high")
        finally:
            import os
            if os.path.exists(tmp_name):
                os.remove(tmp_name)

    def test_steam_check_acc_card(self):
        data = {
            "username": "steam_player_99",
            "password": "secret_pass_99",
            "is_steam": True,
            "steam_id": "76561199379274757",
            "level": 3,
            "game_count": 3,
            "games": ["Counter-Strike 2", "Wayfinder", "BLOODSTRIKE"],
            "wallet": "$5.00 USD",
            "country": "Vietnam",
        }
        embed, img_file = build_check_acc_card("ORDER-STEAM-001", data, 0, 1)
        self.assertIsNotNone(img_file)
        self.assertEqual(img_file.filename, "steam_logo.png")
        self.assertIn("TÀI KHOẢN STEAM", embed.title)
        self.assertIn("steam_player_99", embed.description)
        self.assertIn("76561199379274757", embed.description)
        self.assertEqual(embed.thumbnail.url, "attachment://steam_logo.png")
        img_file.close()

        embed_detail = build_account_check_embed(data, 0, 1, "ORDER-STEAM-001")
        self.assertIn("STEAM", embed_detail.title)
        self.assertIn("Thông Tin Đăng Nhập", embed_detail.fields[0].name)
    def test_valorant_individual_ranks_and_prices(self):
        # 1. 2x prices check for all individual ranks
        ranks = ["unranked", "iron", "bronze", "silver", "gold", "platinum", "diamond", "ascendant", "immortal", "radiant"]
        for r in ranks:
            reg_key = f"valo_{r}"
            off_key = f"valo_{r}_off"
            self.assertEqual(PRICE_MAP[off_key], PRICE_MAP[reg_key] * 2)
            self.assertIn("Chủ Off", ACCOUNT_TYPE_NAME[off_key])
            self.assertTrue(ACCOUNT_FILES[off_key].endswith(f"rank_{r}_off.txt"))
            self.assertTrue(get_account_file_path(off_key).endswith(f"rank_{r}_off.txt"))
            self.assertTrue(ACCOUNT_FILES[reg_key].endswith(f"rank_{r}.txt"))
            self.assertTrue(get_account_file_path(reg_key).endswith(f"rank_{r}.txt"))

        # 2. 20 choices in VALORANT_CHOICES (10 regular + 10 chủ off)
        self.assertEqual(len(VALORANT_CHOICES), 20)

        # 3. View dropdown has 20 options and crown emoji on 10 Chủ Off
        view_val = AccountView(current_game="valorant")
        acc_sel = view_val.children[1]
        self.assertEqual(len(acc_sel.options), 20)
        crown_options = [opt for opt in acc_sel.options if opt.emoji and opt.emoji.name == "👑"]
        self.assertEqual(len(crown_options), 10)
        for opt in crown_options:
            self.assertTrue(opt.value.endswith("_off"))

    def test_valorant_chu_off_warranty_ttl(self):
        from utils.warranty import WarrantyStore
        import tempfile, time, json
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "test_w.sqlite3"
            store = WarrantyStore(path=str(db_path))
            
            # Normal order
            normal_order = {
                "order_code": "NORM-001",
                "user_id": 111,
                "account_type": "valo_iron",
                "quantity": 1,
                "amount": 10000,
            }
            store.record_delivery(normal_order, ["user1:pass1"])
            store.mark_delivered("NORM-001")
            delivered_normal = store.order("NORM-001", 111)
            # Default normal TTL is 7200 seconds (2h)
            self.assertAlmostEqual(delivered_normal["expires_at"] - delivered_normal["delivered_at"], 7200, delta=5)

            # Chủ Off order
            off_order = {
                "order_code": "OFF-001",
                "user_id": 222,
                "account_type": "valo_iron_off",
                "quantity": 1,
                "amount": 20000,
            }
            store.record_delivery(off_order, ["user2:pass2"])
            store.mark_delivered("OFF-001")
            delivered_off = store.order("OFF-001", 222)
            # Default off TTL is 18000 seconds (5h)
            self.assertAlmostEqual(delivered_off["expires_at"] - delivered_off["delivered_at"], 18000, delta=5)

    def test_valorant_storefront_embed_sections(self):
        embed = build_buy_acc_message("valorant")
        field_names = [f.name for f in embed.fields]
        self.assertTrue(any("THƯỜNG" in fn for fn in field_names))
        self.assertTrue(any("CHỦ OFF" in fn for fn in field_names))


if __name__ == "__main__":
    unittest.main()
