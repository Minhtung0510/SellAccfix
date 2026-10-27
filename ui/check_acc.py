import os
import re
import io
import json
import logging
from pathlib import Path
import discord

from utils.constants import ROOT_DIR, ACCOUNT_TYPE_NAME
from utils.storage import load_admin_ids
from utils.html_generator import parse_checker_text, generate_order_html, RANK_ICONS
from utils.image_generator import generate_inventory_image_bytes

log = logging.getLogger("discord.check_acc")


LOGS_DIR = os.path.join(ROOT_DIR, "data", "logs")
os.makedirs(LOGS_DIR, exist_ok=True)


def find_account_log_by_username(username: str) -> str | None:
    """
    Tìm kiếm khối log chi tiết của tài khoản theo username trong:
    1. Thư mục data/logs/
    2. Thư mục data/
    3. Thư mục Downloads (nếu có file message*.txt)
    """
    if not username:
        return None

    clean_user = username.strip()
    pattern = rf"^\s*Username:\s*{re.escape(clean_user)}\s*$"

    search_dirs = [
        LOGS_DIR,
        os.path.join(ROOT_DIR, "data"),
    ]

    checked_paths = set()
    for directory in search_dirs:
        if not os.path.exists(directory):
            continue
        try:
            for fname in os.listdir(directory):
                if not (fname.endswith(".txt") or fname.endswith(".log")):
                    continue
                full_path = os.path.join(directory, fname)
                if full_path in checked_paths or os.path.isdir(full_path):
                    continue
                checked_paths.add(full_path)

                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        text = f.read()
                    if clean_user.lower() not in text.lower():
                        continue

                    blocks = re.split(r"-{10,}", text)
                    for b in blocks:
                        b_clean = b.strip()
                        if re.search(pattern, b_clean, re.IGNORECASE | re.MULTILINE):
                            return b_clean
                except Exception:
                    pass
        except Exception:
            pass

    return None


def remove_account_from_logs(username: str) -> bool:
    """
    Xóa khối log của tài khoản đã bán khỏi các file trong data/logs/ và data/
    để không bị lưu lại acc đã bán và giữ kho log luôn sạch sẽ.
    """
    if not username:
        return False
    clean_user = username.strip().lower()
    removed = False

    search_dirs = [
        LOGS_DIR,
        os.path.join(ROOT_DIR, "data"),
    ]
    stock_filenames = {
        "rank_iron_gold.txt", "rank_gold_plat.txt", "rank_plat_dia.txt",
        "rank_dia_imt.txt", "rank_radiant.txt",
        "rank_iron_gold_off.txt", "rank_gold_plat_off.txt", "rank_plat_dia_off.txt",
        "rank_dia_imt_off.txt", "rank_radiant_off.txt",
        "cs2_prime.txt", "steam.txt",
        "5k.txt", "10k.txt", "20k.txt", "30k.txt", "40k.txt",
        "50k.txt", "100k.txt", "150k.txt", "200k.txt", "chuoff.txt"
    }

    for directory in search_dirs:
        if not os.path.exists(directory):
            continue
        try:
            for fname in os.listdir(directory):
                if not (fname.endswith(".txt") or fname.endswith(".log")):
                    continue
                if fname.lower() in stock_filenames:
                    continue
                full_path = os.path.join(directory, fname)
                if os.path.isdir(full_path):
                    continue

                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    if clean_user not in content.lower():
                        continue

                    blocks = re.split(r"-{10,}", content)
                    new_blocks = []
                    file_changed = False
                    for b in blocks:
                        b_strip = b.strip()
                        if not b_strip:
                            continue
                        m = re.search(r"^\s*Username:\s*([^\r\n]+)", b_strip, re.IGNORECASE | re.MULTILINE)
                        if m and m.group(1).strip().lower() == clean_user:
                            file_changed = True
                            removed = True
                        else:
                            new_blocks.append(b_strip)

                    if file_changed:
                        with open(full_path, "w", encoding="utf-8") as f:
                            if new_blocks:
                                f.write("\n---------------------------\n".join(new_blocks) + "\n---------------------------\n")
                            else:
                                f.write("")
                except Exception as ex:
                    log.warning("Lỗi khi dọn dẹp log tài khoản %s khỏi %s: %s", username, full_path, ex)
        except Exception:
            pass

    return removed


def get_order_account_details(store, code: str, user_id: int, claim_id=None):
    """
    Lấy toàn bộ thông tin chi tiết các account trong đơn hàng từ WarrantyStore.
    Hỗ trợ cả account lưu dạng log chi tiết và account dạng user:pass có file log ngoài.
    """
    order = store.order(code, user_id)
    raw_accounts = order.get("accounts", [])
    if claim_id:
        claim = store.get_claim(claim_id)
        if not claim or claim['code'] != code or claim['buyer'] != user_id or claim['state'] not in ('approved', 'ready'):
            raise ValueError('Không tìm thấy acc bảo hành đã duyệt của đơn này.')
        raw_accounts = claim['replacements']
    if not raw_accounts:
        return order, []

    account_results = []
    for raw_acc in raw_accounts:
        raw_str = raw_acc.strip()
        parsed = parse_checker_text(raw_str)
        if parsed and (parsed[0].get("skins") or parsed[0].get("current_rank") != "Unranked" or "Username:" in raw_str):
            account_results.append((parsed[0], raw_str))
            continue

        # Nếu chưa có thông tin chi tiết, thử bóc username và tìm trong kho log
        u_match = re.search(r"Username:\s*([^\r\n]+)", raw_str, re.IGNORECASE)
        p_match = re.search(r"Password:\s*([^\r\n]+)", raw_str, re.IGNORECASE)
        if u_match:
            u_val = u_match.group(1).strip()
            p_val = p_match.group(1).strip() if p_match else ""
        elif ":" in raw_str and "\n" not in raw_str:
            parts = raw_str.split(":", 1)
            u_val = parts[0].strip()
            p_val = parts[1].strip()
        else:
            first_line = raw_str.splitlines()[0] if raw_str else ""
            u_val = first_line.split(":", 1)[0].strip() if ":" in first_line else first_line
            p_val = first_line.split(":", 1)[1].strip() if ":" in first_line else ""

        full_log = find_account_log_by_username(u_val)
        if full_log:
            parsed_full = parse_checker_text(full_log)
            if parsed_full:
                account_results.append((parsed_full[0], full_log))
                continue

        # Fallback: Tạo dict cơ bản nếu không tìm thấy log
        basic_dict = {
            "username": u_val,
            "password": p_val,
            "riot_name": u_val,
            "riot_tag": "",
            "riot_id": u_val,
            "region": "Chưa rõ",
            "level": "N/A",
            "vp": "0",
            "rp": "0",
            "kc": "0",
            "email_verified": False,
            "phone_verified": False,
            "current_rank": "Chưa có log",
            "peak_rank": "Chưa có log",
            "rank_icon": RANK_ICONS.get("UNRANKED"),
            "last_game": "N/A",
            "knives_count": 0,
            "weapons_count": 0,
            "total_skins": 0,
            "tier_counts": {},
            "skins": [],
            "is_basic": True,
        }
        account_results.append((basic_dict, raw_str))

    is_cs = (order.get("account_type") == "cs2_prime")
    if is_cs:
        for d, _r in account_results:
            d["is_cs"] = True

    is_steam = (order.get("game") == "steam" or str(order.get("account_type", "")).startswith("steam_"))
    if is_steam:
        from utils.steam_storage import parse_steam_account_line
        for d, raw_str in account_results:
            d["is_steam"] = True
            p = parse_steam_account_line(raw_str)
            if p:
                d["username"] = p["username"]
                d["password"] = p["password"]
                d["steam_id"] = p["steam_id"]
                d["level"] = p["level"]
                d["game_count"] = p["game_count"]
                d["wallet"] = p["wallet"]
                d["country"] = p["country"]
                d["games"] = p["games"]
                d["cs2_prime"] = p["cs2_prime"]
                d["vac"] = p["vac"]

    return order, account_results


def build_account_check_embed(data: dict, index: int, total: int, order_code: str) -> discord.Embed:
    """Tạo Embed Discord chuyên nghiệp hiển thị đầy đủ thông tin check account."""
    if data.get("is_steam"):
        u = data.get("username", "")
        p = data.get("password", "")
        games_list = data.get("games", [])
        games_display = ", ".join(games_list[:15])
        if len(games_list) > 15:
            games_display += f" ... và {len(games_list) - 15} game khác"
        if not games_display:
            games_display = "Không có game"
        embed = discord.Embed(
            title=f"🎮 CHI TIẾT ACC STEAM #{index+1}/{total}",
            description="🎮 **DTFF SHOP • TÀI KHOẢN GAME STEAM**",
            color=0x1B2838,
        )
        embed.set_author(name="DTFF SHOP • TÀI KHOẢN STEAM", icon_url="attachment://steam_logo.png")
        embed.set_thumbnail(url="attachment://steam_logo.png")
        embed.add_field(
            name="👤 Thông Tin Đăng Nhập Steam",
            value=f"• **Tài khoản:** `{u}`\n• **Mật khẩu:** ||`{p}`|| *(nhấp để xem)*\n• **SteamID:** `{data.get('steam_id', 'N/A')}`",
            inline=False,
        )
        embed.add_field(
            name="📊 Thông Số & Ví",
            value=f"• **Level:** `{data.get('level', 0)}`\n• **Số dư ví:** `{data.get('wallet', '0')}`\n• **Quốc gia:** `{data.get('country', 'N/A')}`\n• **Tổng game:** `{data.get('game_count', len(games_list))} games`",
            inline=False,
        )
        embed.add_field(
            name="🎮 Danh Sách Games Trong Acc",
            value=f"`{games_display}`",
            inline=False,
        )
        embed.set_footer(text=f"Mã đơn: {order_code} • DTFF SHOP • Steam Game")
        return embed

    if data.get("is_cs"):
        u = data.get("username", "")
        p = data.get("password", "")
        embed = discord.Embed(
            title=f"💣 CHI TIẾT ACC CSGO 2 #{index+1}/{total}",
            description="💣 **DTFF SHOP • TÀI KHOẢN CSGO 2 PRIME**",
            color=0xDE9B35,
        )
        embed.set_author(name="DTFF SHOP • CSGO 2 PRIME", icon_url="attachment://cs2_logo.png")
        embed.set_thumbnail(url="attachment://cs2_logo.png")
        embed.add_field(
            name="👤 Thông Tin Đăng Nhập Steam",
            value=f"• **Tài khoản:** `{u}`\n• **Mật khẩu:** ||`{p}`|| *(nhấp để xem)*",
            inline=False,
        )
        embed.add_field(
            name="⭐ Trạng Thái Tài Khoản",
            value="• **Gói:** CSGO 2 Prime Status\n• **Rank:** Chơi được Competitive / Premier Rank\n• **Nền tảng:** Steam",
            inline=False,
        )
        embed.set_footer(text=f"Mã đơn: {order_code} • DTFF SHOP • CSGO 2 Prime")
        return embed

    riot_id = data.get("riot_id") or data.get("username")
    username = data.get("username", "")
    password = data.get("password", "")
    current_rank = data.get("current_rank", "Unranked")
    peak_rank = data.get("peak_rank", "Unranked")
    region = data.get("region", "NA")
    level = data.get("level", "1")
    vp = data.get("vp", "0")
    rp = data.get("rp", "0")
    kc = data.get("kc", "0")
    email_ver = data.get("email_verified", False)
    phone_ver = data.get("phone_verified", False)
    last_game = data.get("last_game", "N/A")
    total_skins = data.get("total_skins", 0)
    tier_counts = data.get("tier_counts", {})
    skins = data.get("skins", [])
    rank_icon = data.get("rank_icon")
    is_basic = data.get("is_basic", False)

    # Chọn màu theo bậc Rank cao nhất hoặc hiện tại
    r_up = (current_rank + " " + peak_rank).upper()
    if "RADIANT" in r_up:
        color = 0xFFFF55
    elif "IMMORTAL" in r_up:
        color = 0xBB324E
    elif "ASCENDANT" in r_up:
        color = 0x19B37E
    elif "DIAMOND" in r_up:
        color = 0xB38CFF
    elif "PLATINUM" in r_up:
        color = 0x00A8B5
    elif "GOLD" in r_up:
        color = 0xF0B232
    elif "SILVER" in r_up:
        color = 0xA0A0A0
    elif "BRONZE" in r_up:
        color = 0xA97142
    else:
        color = 0xFD4556

    embed = discord.Embed(
        title=f"🔍 KẾT QUẢ CHECK ACC #{index+1}/{total} • {riot_id}",
        description="🎮 **DTFF SHOP • CHI TIẾT TÀI KHOẢN TỰ ĐỘNG**\nDữ liệu được bóc tách từ log tool check Valorant.",
        color=color
    )
    embed.set_author(name="DTFF SHOP • VALORANT", icon_url="attachment://valorant_logo.png")
    if rank_icon:
        embed.set_thumbnail(url=rank_icon)
    else:
        embed.set_thumbnail(url="attachment://valorant_logo.png")

    embed.add_field(
        name="👤 Thông Tin Đăng Nhập",
        value=f"• **Tài khoản:** `{username}`\n• **Mật khẩu:** ||`{password}`|| *(nhấp để xem)*",
        inline=False
    )

    if is_basic:
        embed.add_field(
            name="ℹ️ Lưu Ý",
            value="Tài khoản này được nhập kho dạng User:Pass thông thường (chưa có log chi tiết về Skin/Rank từ tool check).",
            inline=False
        )
    else:
        embed.add_field(
            name="📊 Chi Tiết Tài Khoản",
            value=f"• **Riot ID:** `{riot_id}`\n• **Khu vực:** `{region}`\n• **Cấp độ:** `Lv {level}`\n• **Trận cuối:** `{last_game}`",
            inline=True
        )

        embed.add_field(
            name="🏆 Xếp Hạng Rank",
            value=f"• **Hiện tại:** **{current_rank}**\n• **Cao nhất (Peak):** **{peak_rank}**",
            inline=True
        )

        embed.add_field(
            name="💰 Tài Nguyên & Bảo Mật",
            value=f"• **VP:** `{vp}` | **RP:** `{rp}` | **KC:** `{kc}`\n• **Email:** {'✅ Đã xác minh' if email_ver else '❌ Chưa xác minh'}\n• **SĐT:** {'✅ Đã liên kết' if phone_ver else '❌ Chưa liên kết'}",
            inline=False
        )

        knives = [s["name"] for s in skins if s.get("weaponType") == "Cận Chiến"]
        knives_text = "\n".join(f"• 🗡️ **{k}**" for k in knives) if knives else "*Không có skin dao*"
        if len(knives_text) > 1000:
            knives_text = knives_text[:950] + "\n• *(Còn tiếp...)*"
        embed.add_field(
            name=f"🔪 Dao / Cận Chiến ({len(knives)})",
            value=knives_text,
            inline=False
        )

        weapons = [s for s in skins if s.get("weaponType") != "Cận Chiến"]
        tier_summary = []
        for t in ["Ultra", "Exclusive", "Premium", "Deluxe", "Select"]:
            c = tier_counts.get(t, 0)
            if c > 0:
                tier_summary.append(f"**{c}** {t}")
        tier_line = " • ".join(tier_summary) if tier_summary else "Cơ bản"

        weapon_lines = []
        for w in weapons[:12]:
            tier_tag = f"[{w['tier']}]" if w.get('tier') in ("Ultra", "Exclusive", "Premium") else ""
            weapon_lines.append(f"• 🔫 {w['name']} {tier_tag}".strip())

        rem = len(weapons) - len(weapon_lines)
        if rem > 0:
            weapon_lines.append(f"• *... và {rem} skin khác (tải file log/HTML để xem đầy đủ)*")

        weapons_val = f"🏷️ **Bậc skin:** {tier_line}\n" + "\n".join(weapon_lines)
        if len(weapons_val) > 1000:
            weapons_val = weapons_val[:950] + "\n• *(Xem tiếp trong file log)*"

        embed.add_field(
            name=f"🔫 Súng ({len(weapons)} Skins / {total_skins} Tổng)",
            value=weapons_val,
            inline=False
        )

    embed.set_footer(text=f"Mã đơn: {order_code} • DTFF SHOP • Tra cứu tài khoản tự động")
    return embed


class AccountSelect(discord.ui.Select):
    def __init__(self, parent_view, accounts_data):
        options = []
        for i, (data, _raw) in enumerate(accounts_data[:25]):
            r_id = data.get("riot_id") or data.get("username")
            r_rank = data.get("current_rank", "N/A")
            s_count = data.get("total_skins", 0)
            desc = f"Rank: {r_rank[:30]} • {s_count} Skins"
            options.append(
                discord.SelectOption(
                    label=f"Acc #{i+1} • {r_id[:50]}",
                    value=str(i),
                    description=desc[:100],
                    default=(i == parent_view.current_index)
                )
            )
        super().__init__(placeholder="Chọn tài khoản muốn xem thông tin...", min_values=1, max_values=1, options=options, row=0)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.current_index = int(self.values[0])
        self.parent_view.refresh_buttons()
        embed = self.parent_view.get_current_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class CheckAccDetailView(discord.ui.View):
    def __init__(self, code: str, accounts_data: list, current_index: int = 0, buyer_id: int = 0):
        super().__init__(timeout=600)
        self.code = code
        self.accounts_data = accounts_data
        self.current_index = current_index
        self.buyer_id = buyer_id
        self.refresh_buttons()

    def get_current_embed(self) -> discord.Embed:
        data, _raw = self.accounts_data[self.current_index]
        return build_account_check_embed(data, self.current_index, len(self.accounts_data), self.code)

    def refresh_buttons(self):
        for child in list(self.children):
            if isinstance(child, AccountSelect):
                self.remove_item(child)

        total = len(self.accounts_data)
        if total > 1:
            self.add_item(AccountSelect(self, self.accounts_data))

        self.btn_prev.disabled = (self.current_index <= 0)
        self.btn_next.disabled = (self.current_index >= total - 1)
        self.btn_prev.row = 1
        self.btn_next.row = 1
        self.btn_copy.row = 2
        self.btn_download_log.row = 2
        self.btn_download_html.row = 2

    @discord.ui.button(label="Acc trước", emoji="◀", style=discord.ButtonStyle.secondary, row=1)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_index > 0:
            self.current_index -= 1
            self.refresh_buttons()
            embed = self.get_current_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Acc sau", emoji="▶", style=discord.ButtonStyle.secondary, row=1)
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_index < len(self.accounts_data) - 1:
            self.current_index += 1
            self.refresh_buttons()
            embed = self.get_current_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Sao chép TK:MK", emoji="📋", style=discord.ButtonStyle.secondary, row=2)
    async def btn_copy(self, interaction: discord.Interaction, button: discord.ui.Button):
        data, _raw = self.accounts_data[self.current_index]
        u = data.get("username", "")
        p = data.get("password", "")
        text = f"{u}:{p}"
        await interaction.response.send_message(
            f"📋 **Thông tin tài khoản #{self.current_index+1}:**\n```{text}```",
            ephemeral=True
        )

    @discord.ui.button(label="Tải Log TXT", emoji="📄", style=discord.ButtonStyle.primary, row=2)
    async def btn_download_log(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        data, raw = self.accounts_data[self.current_index]
        u = data.get("username", "account")
        filename = f"log_{u}_{self.code}.txt"
        file = discord.File(io.BytesIO(raw.encode("utf-8")), filename=filename)
        try:
            await interaction.followup.send(
                f"📄 **File log chi tiết của tài khoản #{self.current_index+1} (`{u}`):**",
                file=file,
                ephemeral=True
            )
        finally:
            file.close()

    @discord.ui.button(label="Tải File HTML", emoji="🌐", style=discord.ButtonStyle.success, row=2)
    async def btn_download_html(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        parsed_list = [d for d, _r in self.accounts_data]
        html_str = generate_order_html(self.code, parsed_list, shop_name="DTFF SHOP")
        filename = f"DTFF_DonHang_{self.code}.html"
        file = discord.File(io.BytesIO(html_str.encode("utf-8")), filename=filename)
        try:
            await interaction.followup.send(
                "🌐 **File giao diện quản lý HTML với hình ảnh 3D skin và bộ lọc:**\n*Tải về và mở trực tiếp bằng trình duyệt trên điện thoại hoặc máy tính.*",
                file=file,
                ephemeral=True
            )
        finally:
            file.close()


def build_check_acc_card(code: str, data: dict, index: int, total: int) -> tuple[discord.Embed, discord.File | None]:
    if data.get("is_steam"):
        u = data.get("username", "")
        p = data.get("password", "")
        games_list = data.get("games", [])
        games_display = ", ".join(games_list[:12])
        if len(games_list) > 12:
            games_display += f" ... và {len(games_list) - 12} game khác"
        if not games_display:
            games_display = "Không có game"
        count_str = f" • Tài khoản #{index+1}/{total}" if total > 1 else ""
        embed = discord.Embed(
            title=f"🎮 TÀI KHOẢN STEAM • ĐƠN #{code}{count_str}",
            description=(
                f"👤 **Tài khoản Steam:** `{u}`\n"
                f"🔑 **Mật khẩu:** ||`{p}`|| *(nhấp để xem)*\n\n"
                f"🆔 **SteamID:** `{data.get('steam_id', 'N/A')}`\n"
                f"⭐ **Level:** `{data.get('level', 0)}`  |  💰 **Ví:** `{data.get('wallet', '0')}`  |  🌍 `{data.get('country', 'N/A')}`\n"
                f"📦 **Tổng số Games:** **{data.get('game_count', len(games_list))} games**\n\n"
                f"🎮 **Games:** `{games_display}`\n\n"
                f"📌 *Đăng nhập bằng ứng dụng Steam trên máy tính.*"
            ),
            color=0x1B2838,
        )
        embed.set_author(name="DTFF SHOP • TÀI KHOẢN STEAM", icon_url="attachment://steam_logo.png")
        embed.set_footer(text=f"Mã đơn: {code} • DTFF SHOP • Tra cứu tài khoản tự động")
        from Modules.CreateMessage import create_game_logo_file
        logo_file = create_game_logo_file("steam")
        if logo_file:
            embed.set_thumbnail(url="attachment://steam_logo.png")
        return embed, logo_file

    if data.get("is_cs"):
        u = data.get("username", "")
        p = data.get("password", "")
        count_str = f" • Tài khoản #{index+1}/{total}" if total > 1 else ""
        embed = discord.Embed(
            title=f"💣 TÀI KHOẢN CSGO 2 PRIME • ĐƠN #{code}{count_str}",
            description=(
                f"👤 **Tài khoản Steam:** `{u}`\n"
                f"🔑 **Mật khẩu:** ||`{p}`|| *(nhấp để xem)*\n\n"
                f"⭐ **Loại:** **CSGO 2 Prime Status (Chơi được Rank)**\n"
                f"🎮 **Game:** **Counter-Strike 2 (Steam)**\n\n"
                f"📌 *Đăng nhập qua ứng dụng Steam để chơi.*"
            ),
            color=0xDE9B35,
        )
        embed.set_author(name="DTFF SHOP • CSGO 2 PRIME", icon_url="attachment://cs2_logo.png")
        embed.set_footer(text=f"Mã đơn: {code} • DTFF SHOP • Tra cứu tài khoản tự động")
        from Modules.CreateMessage import create_game_logo_file
        logo_file = create_game_logo_file("csgo2")
        if logo_file:
            embed.set_thumbnail(url="attachment://cs2_logo.png")
        return embed, logo_file

    u = data.get("username", "")
    p = data.get("password", "")
    riot_id = data.get("riot_id") or u
    rank = data.get("current_rank", "Unranked")
    peak = data.get("peak_rank", "Unranked")
    level = data.get("level", "1")
    total_skins = data.get("total_skins", 0)
    knives = [s["name"] for s in data.get("skins", []) if s.get("weaponType") == "Cận Chiến"]
    knives_str = ", ".join(knives) if knives else "Không có"

    count_str = f" • Tài khoản #{index+1}/{total}" if total > 1 else ""

    embed = discord.Embed(
        title=f"🔍 KHO ĐỒ TÀI KHOẢN • ĐƠN #{code}{count_str}",
        description=(
            f"🎮 **Riot ID:** `{riot_id}`\n"
            f"👤 **Tài khoản:** `{u}`  |  🔑 **Mật khẩu:** ||`{p}`|| *(nhấp để xem)*\n"
            f"🏆 **Rank:** **{rank}** *(Cao nhất: {peak})* • **Lv {level}**\n"
            f"🔪 **Dao:** **{knives_str}**\n"
            f"🔫 **Tổng số Skin:** **{total_skins} Skins**\n\n"
            f"👉 **Bấm trực tiếp vào ảnh bên dưới để phóng to và lướt lên/xuống kiểm tra chi tiết toàn bộ kho đồ!**"
        ),
        color=0x00D26A
    )
    embed.set_author(name="DTFF SHOP • VALORANT", icon_url="attachment://valorant_logo.png")
    img_bytes = generate_inventory_image_bytes(data, code)
    filename = f"kho_acc_{code}_{index+1}.png"
    embed.set_image(url=f"attachment://{filename}")
    embed.set_footer(text=f"Mã đơn: {code} • DTFF SHOP • Tra cứu kho đồ tự động")

    img_file = discord.File(io.BytesIO(img_bytes), filename=filename)
    return embed, img_file


class CheckAccActionView(discord.ui.View):
    def __init__(self, code: str, accounts_data: list, current_index: int = 0):
        super().__init__(timeout=600)
        self.code = code
        self.accounts_data = accounts_data
        self.current_index = current_index

        if len(self.accounts_data) <= 1:
            self.remove_item(self.btn_prev)
            self.remove_item(self.btn_next)
        else:
            self.btn_prev.disabled = (self.current_index == 0)
            self.btn_next.disabled = (self.current_index >= len(self.accounts_data) - 1)

    @discord.ui.button(label="Acc trước", emoji="◀️", style=discord.ButtonStyle.secondary, row=0)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_index > 0:
            self.current_index -= 1
            await self._update_message(interaction)

    @discord.ui.button(label="Acc sau", emoji="▶️", style=discord.ButtonStyle.secondary, row=0)
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_index < len(self.accounts_data) - 1:
            self.current_index += 1
            await self._update_message(interaction)

    @discord.ui.button(label="Sao chép TK:MK", emoji="📋", style=discord.ButtonStyle.secondary, row=1)
    async def btn_copy(self, interaction: discord.Interaction, button: discord.ui.Button):
        data, _raw = self.accounts_data[self.current_index]
        u = data.get("username", "")
        p = data.get("password", "")
        await interaction.response.send_message(
            f"📋 **Thông tin đăng nhập tài khoản #{self.current_index + 1}:**\n```{u}:{p}```",
            ephemeral=True
        )

    @discord.ui.button(label="Tải File HTML", emoji="🌐", style=discord.ButtonStyle.success, row=1)
    async def btn_download_html(self, interaction: discord.Interaction, button: discord.ui.Button):
        data, _raw = self.accounts_data[self.current_index]
        if data.get("is_cs"):
            await interaction.response.send_message(
                "ℹ️ Tài khoản CSGO 2 Prime đăng nhập trực tiếp qua Steam, không sử dụng file HTML 3D skin như Valorant.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        parsed_list = [d for d, _r in self.accounts_data]
        html_str = generate_order_html(self.code, parsed_list, shop_name="DTFF SHOP")
        filename = f"DTFF_KhoAcc_{self.code}.html"
        file = discord.File(io.BytesIO(html_str.encode("utf-8")), filename=filename)
        try:
            await interaction.followup.send(
                "🌐 **Giao diện kho đồ HTML (Hình ảnh 3D skin, dao, rank và bộ lọc súng):**\n*Hãy tải về và mở tệp đính kèm bằng trình duyệt (Chrome, Safari, Edge, Cốc Cốc) để trải nghiệm!*",
                file=file,
                ephemeral=True
            )
        finally:
            file.close()

    async def _update_message(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.btn_prev.disabled = (self.current_index == 0)
        self.btn_next.disabled = (self.current_index >= len(self.accounts_data) - 1)

        data, _raw = self.accounts_data[self.current_index]
        embed, img_file = build_check_acc_card(self.code, data, self.current_index, len(self.accounts_data))
        try:
            if img_file:
                await interaction.edit_original_response(embed=embed, attachments=[img_file], view=self)
            else:
                await interaction.edit_original_response(embed=embed, attachments=[], view=self)
        finally:
            if img_file:
                img_file.close()


class CheckAccButton(discord.ui.DynamicItem[discord.ui.Button], template=r"checkacc:(?P<code>[A-Za-z0-9_-]{1,64})(?::(?P<claim_id>[a-f0-9]{32}))?"):
    def __init__(self, code: str, claim_id=None):
        super().__init__(
            discord.ui.Button(
                label="Check Acc",
                emoji="🔍",
                style=discord.ButtonStyle.secondary,
                custom_id=f"checkacc:{code}" + (f":{claim_id}" if claim_id else "")
            )
        )
        self.code = code
        self.claim_id = claim_id

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str]):
        return cls(match["code"], match["claim_id"])

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = interaction.client.warranty_store
        admin_ids = load_admin_ids()

        try:
            # Kiểm tra quyền: người mua hoặc Admin
            order = store.order(self.code, interaction.user.id)
        except Exception:
            # Nếu người gọi là Admin thì cho phép tra cứu
            if interaction.user.id in admin_ids:
                with store.connection() as db:
                    row = db.execute("SELECT * FROM deliveries WHERE code=?", (self.code,)).fetchone()
                    if not row:
                        await interaction.followup.send("❌ Không tìm thấy đơn hàng trong hệ thống.", ephemeral=True)
                        return
                    order = dict(row)
                    order["accounts"] = json.loads(order["accounts"])
            else:
                await interaction.followup.send("❌ Bạn không có quyền xem thông tin của đơn hàng này.", ephemeral=True)
                return

        try:
            _order, accounts_data = get_order_account_details(store, self.code, order["buyer"], self.claim_id)
            if not accounts_data:
                await interaction.followup.send("❌ Đơn hàng chưa có dữ liệu tài khoản.", ephemeral=True)
                return

            view = CheckAccActionView(self.code, accounts_data, current_index=0)
            d0, _r0 = accounts_data[0]
            embed, img_file = build_check_acc_card(self.code, d0, 0, len(accounts_data))
            try:
                if img_file:
                    await interaction.followup.send(embed=embed, file=img_file, view=view, ephemeral=True)
                else:
                    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            finally:
                if img_file:
                    img_file.close()

        except Exception as e:
            log.exception("Lỗi khi mở giao diện Check Acc cho đơn %s: %s", self.code, e)
            await interaction.followup.send(f"❌ Đã xảy ra lỗi khi tạo ảnh check acc: {e}", ephemeral=True)
