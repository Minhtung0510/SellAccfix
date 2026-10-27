import os
import discord
from discord import app_commands
from discord.ext import commands
from utils.storage import load_admin_ids
from Modules.AccountProcess import get_acc_count
from utils.constants import (
    ACCOUNT_CHOICES,
    ACCOUNT_TYPE_NAME,
    PRICE_MAP,
    get_account_file_path,
)


def format_price(value: str) -> str:
    return f"{PRICE_MAP[value]:,}".replace(",", ".") + "đ"


def account_choice_label(value: str) -> str:
    name = ACCOUNT_TYPE_NAME[value]
    if "Chủ Off" in name:
        icon = "👑"
    elif "CSGO" in name:
        icon = "💣"
    elif "Steam" in name or "PUBG" in name:
        icon = "🎮"
    else:
        icon = "🎯"
    return f"{icon} {format_price(value)} • {name}"


# Preserve the internal IDs and stock mapping; only improve displayed labels.
LOAI_CHOICES = [
    app_commands.Choice(name=account_choice_label(value)[:100], value=value)
    for _label, value, _path, _color in ACCOUNT_CHOICES
]



class AccountsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.choices(loai=LOAI_CHOICES)
    @app_commands.command(name="add_account", description="Nhập kho tài khoản bằng danh sách hoặc file TXT.")
    @app_commands.describe(
        loai="Chọn đúng gói rank hoặc loại tài khoản cần nhập",
        danh_sach="Dán danh sách tài khoản (mỗi dòng 1 acc hoặc khối log)",
        file="Tải file .txt UTF-8 lên • Mỗi dòng một tài khoản hoặc khối log",
    )
    async def add_account(self, interaction: discord.Interaction, loai: str, danh_sach: str = "", file: discord.Attachment | None = None):
        admin_ids = load_admin_ids()
        if interaction.user.id not in admin_ids:
            await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True, ephemeral=True)

        from Modules.AccountProcess import split_raw_accounts

        accs: list[str] = []
        if danh_sach:
            accs.extend(split_raw_accounts(danh_sach))

        if file:
            try:
                content = (await file.read()).decode("utf-8")
                new_accs = split_raw_accounts(content)
                accs.extend(new_accs)
            except Exception as e:
                await interaction.followup.send(f"❌ Không đọc được file: {e}")
                return

        if not accs:
            await interaction.followup.send("❗ Bạn cần nhập ít nhất một tài khoản (qua text hoặc file).")
            return

        # CÙNG mapping với menu đếm stock và lúc giao acc
        file_path = get_account_file_path(loai)
        if file_path is None:
            await interaction.followup.send(f"❌ Loại acc không hợp lệ: `{loai}`.")
            return

        try:
            self.bot.warranty_store.recover_allocations()
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            need_newline = False
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                with open(file_path, "rb") as rf:
                    rf.seek(-1, os.SEEK_END)
                    need_newline = rf.read(1) not in (b"\n", b"\r")

            with open(file_path, "a", encoding="utf-8") as f:
                if need_newline:
                    f.write("\n")
                for acc in accs:
                    if "Username:" in acc or "\n" in acc:
                        f.write(acc.strip() + "\n---------------------------\n")
                    else:
                        f.write(acc.strip() + "\n")

            orders_cog = self.bot.get_cog("OrdersCog")
            if orders_cog:
                orders_cog.request_menu_refresh()
                orders_cog.notify_orders_changed()

            embed = discord.Embed(
                title="✅ Nhập kho thành công",
                description=f"**{ACCOUNT_TYPE_NAME[loai]}**\nĐã bổ sung tài khoản vào đúng kho đã chọn.",
                color=0x2ECC71,
            )
            embed.add_field(name="💰 Giá bán / acc", value=f"**{format_price(loai)}**", inline=True)
            embed.add_field(name="📥 Vừa thêm", value=f"**+{len(accs):,} acc**", inline=True)
            embed.add_field(name="📦 Tồn kho hiện tại", value=f"**{get_acc_count(file_path):,} acc**", inline=True)
            embed.set_footer(text="QUẢN LÝ KHO • Chỉ bạn thấy thông báo này")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ Không thể ghi file: {e}")

    @app_commands.command(name="add_steam", description="Nhập kho tài khoản Steam (dán danh sách hoặc tải file TXT)")
    @app_commands.describe(
        danh_sach="Dán danh sách tài khoản Steam (format tool check)",
        file="Tải file .txt UTF-8 chứa danh sách tài khoản Steam",
    )
    async def add_steam(self, interaction: discord.Interaction, danh_sach: str = "", file: discord.Attachment | None = None):
        admin_ids = load_admin_ids()
        if interaction.user.id not in admin_ids:
            await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True, ephemeral=True)

        from utils.steam_storage import parse_steam_account_line, STEAM_ACCOUNTS_FILE, get_total_steam_count

        raw_lines: list[str] = []
        if danh_sach:
            raw_lines.extend(danh_sach.splitlines())

        if file:
            try:
                content = (await file.read()).decode("utf-8", errors="ignore")
                raw_lines.extend(content.splitlines())
            except Exception as e:
                await interaction.followup.send(f"❌ Không đọc được file: {e}")
                return

        valid_lines: list[str] = []
        tier_counts = {"steam_tier_1": 0, "steam_tier_2": 0, "steam_tier_3": 0}
        for line in raw_lines:
            line_str = line.strip()
            if not line_str or line_str.startswith("---"):
                continue
            parsed = parse_steam_account_line(line_str)
            if parsed:
                valid_lines.append(parsed["raw_line"])
                tier_counts[parsed["tier_id"]] += 1

        if not valid_lines:
            await interaction.followup.send("❗ Không tìm thấy tài khoản Steam hợp lệ nào từ dữ liệu nhập.")
            return

        file_path = STEAM_ACCOUNTS_FILE
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        need_newline = False
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            with open(file_path, "rb") as rf:
                rf.seek(-1, os.SEEK_END)
                need_newline = rf.read(1) not in (b"\n", b"\r")

        with open(file_path, "a", encoding="utf-8") as f:
            if need_newline:
                f.write("\n")
            for l in valid_lines:
                f.write(l + "\n")

        orders_cog = self.bot.get_cog("OrdersCog")
        if orders_cog:
            orders_cog.request_menu_refresh()
            orders_cog.notify_orders_changed()

        embed = discord.Embed(
            title="🎮 Nhập kho Steam thành công",
            description=f"Đã bổ sung **+{len(valid_lines):,}** tài khoản Steam vào kho.",
            color=0x1B2838,
        )
        embed.add_field(name="🟢 Gói 0-10 Games", value=f"+{tier_counts['steam_tier_1']} acc", inline=True)
        embed.add_field(name="🟡 Gói 11-40 Games", value=f"+{tier_counts['steam_tier_2']} acc", inline=True)
        embed.add_field(name="🔴 Gói 41+ Games", value=f"+{tier_counts['steam_tier_3']} acc", inline=True)
        embed.add_field(name="📦 Tổng kho Steam hiện tại", value=f"**{get_total_steam_count():,} acc**", inline=False)
        embed.set_footer(text="QUẢN LÝ KHO STEAM • Chỉ bạn thấy thông báo này")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="check_acc", description="Tra cứu chi tiết tài khoản / log acc đã mua hoặc theo username.")
    @app_commands.describe(
        ma_don="Mã đơn hàng (ví dụ: DTFF-XXXXXX hoặc mã nhận được khi mua)",
        username="Tên tài khoản Riot / Username (Admin tra cứu trực tiếp)",
    )
    async def check_acc(self, interaction: discord.Interaction, ma_don: str = "", username: str = ""):
        admin_ids = load_admin_ids()
        is_admin = interaction.user.id in admin_ids

        if not ma_don and not username:
            await interaction.response.send_message("❗ Vui lòng nhập `ma_don` hoặc `username` để tra cứu.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        from ui.check_acc import get_order_account_details, CheckAccActionView, build_check_acc_card, find_account_log_by_username
        from utils.html_generator import parse_checker_text

        # 1. Tra cứu theo mã đơn hàng
        if ma_don:
            code = ma_don.strip()
            store = self.bot.warranty_store
            try:
                order = store.order(code, interaction.user.id)
            except Exception:
                if is_admin:
                    with store.connection() as db:
                        row = db.execute("SELECT * FROM deliveries WHERE code=?", (code,)).fetchone()
                        if not row:
                            await interaction.followup.send(f"❌ Không tìm thấy đơn hàng `{code}` trong hệ thống.", ephemeral=True)
                            return
                        import json
                        order = dict(row)
                        order["accounts"] = json.loads(order["accounts"])
                else:
                    await interaction.followup.send("❌ Đơn hàng không tồn tại hoặc bạn không có quyền xem.", ephemeral=True)
                    return

            _order, accounts_data = get_order_account_details(store, code, order["buyer"])
            if not accounts_data:
                await interaction.followup.send("❌ Đơn hàng chưa có dữ liệu tài khoản.", ephemeral=True)
                return

            view = CheckAccActionView(code, accounts_data, current_index=0)
            d0, _r0 = accounts_data[0]
            embed, img_file = build_check_acc_card(code, d0, 0, len(accounts_data))
            try:
                if img_file:
                    await interaction.followup.send(embed=embed, file=img_file, view=view, ephemeral=True)
                else:
                    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            finally:
                if img_file:
                    img_file.close()
            return

        # 2. Tra cứu trực tiếp theo username (Dành cho Admin)
        if username:
            if not is_admin:
                await interaction.followup.send("❌ Chỉ quản trị viên (Admin) mới có quyền tra cứu theo username.", ephemeral=True)
                return

            u_clean = username.strip()
            raw_log = find_account_log_by_username(u_clean)
            if not raw_log:
                await interaction.followup.send(f"❌ Không tìm thấy file log nào chứa tài khoản `{u_clean}` trong hệ thống.", ephemeral=True)
                return

            parsed = parse_checker_text(raw_log)
            if not parsed:
                await interaction.followup.send(f"⚠️ Đã tìm thấy văn bản nhưng không bóc tách được log cho `{u_clean}`.", ephemeral=True)
                return

            accounts_data = [(parsed[0], raw_log)]
            view = CheckAccActionView("TRA-CUU", accounts_data, current_index=0)
            embed, img_file = build_check_acc_card("TRA-CUU", parsed[0], 0, 1)
            try:
                await interaction.followup.send(embed=embed, file=img_file, view=view, ephemeral=True)
            finally:
                img_file.close()

    @app_commands.command(name="upload_log", description="Tải file log tool check (.txt) vào hệ thống tra cứu của bot.")
    @app_commands.describe(file="Tải lên file log định dạng TXT xuất ra từ tool check")
    async def upload_log(self, interaction: discord.Interaction, file: discord.Attachment):
        admin_ids = load_admin_ids()
        if interaction.user.id not in admin_ids:
            await interaction.response.send_message("❌ Bạn không có quyền dùng lệnh này.", ephemeral=True)
            return

        if not (file.filename.endswith(".txt") or file.filename.endswith(".log")):
            await interaction.response.send_message("❌ Vui lòng chỉ tải file đuôi `.txt` hoặc `.log`.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            content = (await file.read()).decode("utf-8", errors="ignore")
            from Modules.AccountProcess import split_raw_accounts
            from ui.check_acc import LOGS_DIR

            os.makedirs(LOGS_DIR, exist_ok=True)
            safe_filename = os.path.basename(file.filename)
            save_path = os.path.join(LOGS_DIR, safe_filename)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(content)

            acc_count = len(split_raw_accounts(content))

            embed = discord.Embed(
                title="📁 Tải file log thành công",
                description=f"Đã lưu file log vào hệ thống tra cứu:\n`{file.filename}`",
                color=0x2ECC71,
            )
            embed.add_field(name="📦 Số tài khoản nhận diện", value=f"**{acc_count:,} acc**", inline=True)
            embed.add_field(name="📂 Đường dẫn lưu", value="`data/logs/`", inline=True)
            embed.set_footer(text="Hệ thống Check Acc sẽ tự động tìm kiếm trong file này khi khách bấm nút Check Acc.")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi khi lưu file log: {e}", ephemeral=True)




async def setup(bot: commands.Bot):
    await bot.add_cog(AccountsCog(bot))
