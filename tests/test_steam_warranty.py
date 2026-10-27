import os
import shutil
import tempfile
import unittest
from pathlib import Path

from utils.warranty import WarrantyStore, WarrantyError
from ui.warranty import AdminWarrantyActionView, ApproveStockWarrantyButton, ApproveManualWarrantyButton, RejectWarrantyButton


class SteamAndSpecialWarrantyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "warranty.sqlite3")
        self.steam_file = os.path.join(self.temp_dir, "steam.txt")
        self.cs2_prime_file = os.path.join(self.temp_dir, "cs2_prime.txt")

        # Sample Steam stock
        self.steam_lines = [
            # user_gta_2: 2 games, contains GTA V -> steam_tier_1
            "[101/1000] ✅ user_gta_2:pass1 | SteamID: 10001 | Lvl:0 | Games:2 | Wallet:0 | Country:VN | Games: [Grand Theft Auto V, Raft] || CS2 Prime : Not Active ❌ || VAC : Clean ✅",
            # user_gta_5: 5 games, contains GTA V -> steam_tier_1
            "[102/1000] ✅ user_gta_5:pass2 | SteamID: 10002 | Lvl:1 | Games:5 | Wallet:0 | Country:VN | Games: [Grand Theft Auto V, Dota 2, CS2] || CS2 Prime : Not Active ❌ || VAC : Clean ✅",
            # user_cod_1: 1 game, Call of Duty -> steam_tier_1
            "[103/1000] ✅ user_cod_1:pass3 | SteamID: 10003 | Lvl:0 | Games:1 | Wallet:0 | Country:US | Games: [Call of Duty®] || CS2 Prime : Not Active ❌ || VAC : Clean ✅",
        ]
        with open(self.steam_file, "w", encoding="utf-8") as f:
            f.write("\n".join(self.steam_lines) + "\n")

        def stock_resolver(kind):
            if str(kind).startswith("steam_tier_"):
                return self.steam_file
            if kind == "cs2_prime":
                return self.cs2_prime_file
            return os.path.join(self.temp_dir, f"{kind}.txt")

        self.store = WarrantyStore(self.db_path, stock_path=stock_resolver)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _dummy_evidence(self, key="e1"):
        p = os.path.join(self.temp_dir, f"{key}.png")
        with open(p, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + key.encode())
        import hashlib
        h = hashlib.sha256(b"\x89PNG\r\n\x1a\n" + key.encode()).hexdigest()
        return [{"hash": h, "path": p}]

    def test_steam_warranty_allocates_exact_same_game(self):
        # 1. Khách mua GTA V (Gói 0 - 10 games: steam_tier_1)
        order = {
            "order_code": "STEAM_GTA_01",
            "user_id": 99999,
            "account_type": "steam_tier_1",
            "quantity": 1,
            "amount": 5000,
            "steam_game": "GTA V",
        }
        initial_acc = ["old_gta_user:old_pass | SteamID: 999 | Games(1): [Grand Theft Auto V]"]
        self.store.record_delivery(order, initial_acc)
        self.store.mark_delivered("STEAM_GTA_01")

        # 2. Khách gửi yêu cầu bảo hành acc #1
        claim_id = self.store.create_claim("STEAM_GTA_01", 99999, [1], self._dummy_evidence("gta_err"))
        claim = self.store.get_claim(claim_id)
        self.assertEqual(claim["steam_game"], "GTA V")

        # 3. Duyệt từ kho: Phải cấp đúng acc có chứa GTA V và ít game nhất trước (user_gta_2)
        repls = self.store.allocate(claim_id, buyer=99999)
        self.assertEqual(len(repls), 1)
        self.assertIn("user_gta_2", repls[0])
        self.assertIn("Grand Theft Auto V", repls[0])

        # 4. Kiểm tra kho steam.txt đã trừ đúng acc user_gta_2
        with open(self.steam_file, "r", encoding="utf-8") as f:
            remaining_content = f.read()
        self.assertNotIn("user_gta_2", remaining_content)
        self.assertIn("user_gta_5", remaining_content)
        self.assertIn("user_cod_1", remaining_content)

    def test_cs2_prime_and_pubg_plus_disallow_auto_stock_allocation(self):
        # 1. Đơn CS2 Prime
        order_cs = {
            "order_code": "CS_PRIME_01",
            "user_id": 88888,
            "account_type": "cs2_prime",
            "quantity": 1,
            "amount": 50000,
        }
        self.store.record_delivery(order_cs, ["cs_old:pass1"])
        self.store.mark_delivered("CS_PRIME_01")
        claim_cs = self.store.create_claim("CS_PRIME_01", 88888, [1], self._dummy_evidence("cs_err"))

        # Backend từ chối auto allocate
        with self.assertRaises(WarrantyError) as ctx:
            self.store.allocate(claim_cs)
        self.assertIn("bắt buộc Admin phải check tay", str(ctx.exception))

        # Admin duyệt thủ công thì thành công
        self.store.allocate_manual(claim_cs, ["cs_checked_by_admin:newpass1"])
        order_after = self.store.order("CS_PRIME_01", 88888)
        self.assertEqual(order_after["current_accounts"][0], "cs_checked_by_admin:newpass1")

        # 2. Đơn PUBG Plus
        order_pubg = {
            "order_code": "PUBG_PLUS_01",
            "user_id": 77777,
            "account_type": "pubg_plus",
            "quantity": 1,
            "amount": 50000,
        }
        self.store.record_delivery(order_pubg, ["pubg_old:pass1"])
        self.store.mark_delivered("PUBG_PLUS_01")
        claim_pubg = self.store.create_claim("PUBG_PLUS_01", 77777, [1], self._dummy_evidence("pubg_err"))

        # Backend từ chối auto allocate
        with self.assertRaises(WarrantyError) as ctx2:
            self.store.allocate(claim_pubg)
        self.assertIn("bắt buộc Admin phải check tay", str(ctx2.exception))

    def test_admin_warranty_view_buttons(self):
        # Đối với acc thường (Steam tier 1): Có 3 nút (Duyệt kho, Nhập tay, Từ chối)
        view_normal = AdminWarrantyActionView("claim_1", attempt=1, account_type="steam_tier_1")
        types_normal = [type(item) for item in view_normal.children]
        self.assertIn(ApproveStockWarrantyButton, types_normal)
        self.assertIn(ApproveManualWarrantyButton, types_normal)
        self.assertIn(RejectWarrantyButton, types_normal)
        self.assertEqual(len(view_normal.children), 3)

        # Đối với CS2 Prime: Chỉ có 2 nút (Nhập tay, Từ chối) - KHÔNG có Duyệt từ kho
        view_cs = AdminWarrantyActionView("claim_2", attempt=1, account_type="cs2_prime")
        types_cs = [type(item) for item in view_cs.children]
        self.assertNotIn(ApproveStockWarrantyButton, types_cs)
        self.assertIn(ApproveManualWarrantyButton, types_cs)
        self.assertIn(RejectWarrantyButton, types_cs)
        self.assertEqual(len(view_cs.children), 2)

        # Đối với PUBG Plus: Chỉ có 2 nút (Nhập tay, Từ chối) - KHÔNG có Duyệt từ kho
        view_pubg = AdminWarrantyActionView("claim_3", attempt=1, account_type="pubg_plus")
        types_pubg = [type(item) for item in view_pubg.children]
        self.assertNotIn(ApproveStockWarrantyButton, types_pubg)
        self.assertIn(ApproveManualWarrantyButton, types_pubg)
        self.assertIn(RejectWarrantyButton, types_pubg)
        self.assertEqual(len(view_pubg.children), 2)


if __name__ == "__main__":
    unittest.main()
