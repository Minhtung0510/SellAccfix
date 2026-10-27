import os
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands, tasks
from utils.storage import load_admin_ids, save_admin_ids, load_menus, save_menus, load_settings, save_settings
from ui.views import AccountView
from Modules.CreateMessage import build_buy_acc_message
from utils.backup import create_backup_zip, BACKUP_DEFAULT_USER_ID

class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.auto_backup_task.start()

    async def cog_unload(self):
        self.auto_backup_task.cancel()

    def _is_admin(self, user_id: int) -> bool:
        return user_id in load_admin_ids()

    async def _send_backup_to_user(self, user_id: int) -> tuple[bool, str]:
        """Nén toàn bộ kho tài khoản, database và gửi file ZIP vào DM của người dùng."""
        try:
            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            if not user:
                return False, f"Không tìm thấy người dùng có ID {user_id}"

            zip_path, stock_summary = create_backup_zip()
            file_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
            now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            embed = discord.Embed(
                title="🛡️ BÁO CÁO ĐỒNG BỘ DỮ LIỆU HỆ THỐNG",
                description="Báo cáo kiểm tra và gói dữ liệu đồng bộ định kỳ.",
                color=0x2ECC71,
                timestamp=discord.utils.utcnow()
            )
            embed.set_author(name="DTFF SYSTEM • ĐỒNG BỘ NỘI BỘ")
            embed.add_field(name="⏰ Thời gian", value=f"`{now_str}`", inline=True)
            embed.add_field(name="📦 Dung lượng", value=f"`{file_size_mb:.2f} MB`", inline=True)
            embed.add_field(name="👤 Người nhận", value=f"<@{user_id}>", inline=True)

            stock_lines = [f"• **{k}**: `{v:,} acc`" for k, v in stock_summary.items()]
            embed.add_field(
                name="📊 Thống kê trạng thái tại thời điểm đồng bộ",
                value="\n".join(stock_lines) if stock_lines else "Trống",
                inline=False
            )
            embed.set_footer(text="DTFF SYSTEM • Gói dữ liệu đính kèm bên dưới")

            file = discord.File(zip_path, filename=os.path.basename(zip_path))
            try:
                dm_channel = user.dm_channel or await user.create_dm()
                await dm_channel.send(embed=embed, file=file)
                return True, "Thành công"
            finally:
                file.close()
                if os.path.exists(zip_path):
                    try:
                        os.remove(zip_path)
                    except OSError:
                        pass
        except Exception as e:
            return False, str(e)

    @tasks.loop(hours=1)
    async def auto_backup_task(self):
        """Tự động sao lưu dữ liệu kho vào lúc 00:00 đêm mỗi ngày."""
        await self.bot.wait_until_ready()
        now = datetime.now()
        if now.hour == 0:
            settings = load_settings()
            today_str = now.strftime("%Y-%m-%d")
            if settings.get("last_auto_backup") != today_str:
                success, _ = await self._send_backup_to_user(BACKUP_DEFAULT_USER_ID)
                if success:
                    settings["last_auto_backup"] = today_str
                    save_settings(settings)

    @app_commands.command(name="menu", description="Tạo một menu mới")
    async def menu(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(thinking=True, ephemeral=True)
        except discord.NotFound:
            return
        if not self._is_admin(interaction.user.id):
            await interaction.followup.send("❌ Bạn không được phép dùng lệnh này.", ephemeral=True)
            return

        view = AccountView()
        from Modules.CreateMessage import create_game_logo_file
        logo_file = create_game_logo_file("valorant")
        try:
            if logo_file:
                message = await interaction.channel.send(embed=build_buy_acc_message(), file=logo_file, view=view)
            else:
                message = await interaction.channel.send(embed=build_buy_acc_message(), view=view)
        finally:
            view.stop()
            if logo_file:
                logo_file.close()
        menus = load_menus()
        menus.append({"message_id": message.id, "channel_id": message.channel.id})
        save_menus(menus)
        await interaction.followup.send("✅ Đã tạo menu mới.", ephemeral=True)

    @app_commands.command(name="refresh", description="Cập nhật số lượng Account")
    async def refresh(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(thinking=True, ephemeral=True)
        except discord.NotFound:
            return
        if not self._is_admin(interaction.user.id):
            await interaction.followup.send("❌ Bạn không được phép dùng lệnh này.", ephemeral=True)
            return

        orders_cog = self.bot.get_cog("OrdersCog")
        count = await orders_cog.refresh_menus(force=True)
        try:
            await interaction.followup.send(f"✅ Đã cập nhật {count} menu.", ephemeral=True)
        except discord.NotFound:
            pass

    @app_commands.command(name="add_admin", description="Thêm admin mới (chỉ dành cho admin)")
    async def add_admin(self, interaction: discord.Interaction, user: discord.User):
        if not self._is_admin(interaction.user.id):
            await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True)
            return
        ids = load_admin_ids()
        if user.id in ids:
            await interaction.response.send_message("⚠️ Người dùng này đã là admin.", ephemeral=True)
            return
        ids.append(user.id)
        save_admin_ids(ids)
        await interaction.response.send_message(f"✅ Đã thêm {user.mention} vào admin.", ephemeral=True)

    @app_commands.command(name="set_warranty_channel", description="Cài đặt kênh Admin nhận duyệt bảo hành")
    async def set_warranty_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not self._is_admin(interaction.user.id):
            await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True)
            return
        from utils.storage import set_warranty_channel_id
        set_warranty_channel_id(channel.id)
        await interaction.response.send_message(f"✅ Đã đặt kênh nhận duyệt bảo hành là: {channel.mention} (ID: `{channel.id}`)", ephemeral=True)

    @app_commands.command(name="set_feedback_channel", description="Chọn kênh đăng đánh giá của khách hàng")
    @app_commands.guild_only()
    async def set_feedback_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not self._is_admin(interaction.user.id):
            await interaction.response.send_message('❌ Bạn không có quyền.', ephemeral=True)
            return
        permissions = channel.permissions_for(interaction.guild.me)
        if not (permissions.view_channel and permissions.send_messages and permissions.embed_links):
            await interaction.response.send_message('Bot cần quyền Xem kênh, Gửi tin nhắn và Nhúng liên kết trong kênh feedback.', ephemeral=True)
            return
        from utils.storage import set_feedback_channel_id
        set_feedback_channel_id(channel.id)
        await interaction.response.send_message(f'✅ Feedback của khách sẽ đăng tại {channel.mention}.', ephemeral=True)

    @app_commands.command(name="feedback", description="Đánh giá một đơn hàng đã nhận")
    async def feedback(self, interaction: discord.Interaction, ma_don: str):
        from ui.feedback import FeedbackButton
        await FeedbackButton(ma_don.strip()).callback(interaction)

    @app_commands.command(name="warranty_channel", description="Xem kênh nhận duyệt bảo hành hiện tại")
    async def warranty_channel(self, interaction: discord.Interaction):
        if not self._is_admin(interaction.user.id):
            await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True)
            return
        from utils.storage import get_warranty_channel_id
        chan_id = get_warranty_channel_id()
        if chan_id:
            channel = self.bot.get_channel(chan_id)
            chan_name = channel.mention if channel else f"`{chan_id}`"
            await interaction.response.send_message(f"🛡️ Kênh duyệt bảo hành hiện tại: {chan_name}", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Chưa cài đặt kênh duyệt bảo hành! Hãy dùng lệnh `/set_warranty_channel` để chọn kênh.", ephemeral=True)


    @app_commands.command(name="set_price", description="Chỉnh giá bán tài khoản trực tiếp (Steam, CS2, Valorant)")
    @app_commands.describe(
        loai="Loại tài khoản muốn đổi giá",
        gia="Số tiền bán mới (VNĐ, ví dụ: 5000, 15000, 25000)"
    )
    @app_commands.choices(loai=[
        app_commands.Choice(name="🎯 Valorant: Unranked", value="valo_unranked"),
        app_commands.Choice(name="🎯 Valorant: Iron", value="valo_iron"),
        app_commands.Choice(name="🎯 Valorant: Bronze", value="valo_bronze"),
        app_commands.Choice(name="🎯 Valorant: Silver", value="valo_silver"),
        app_commands.Choice(name="🎯 Valorant: Gold", value="valo_gold"),
        app_commands.Choice(name="🎯 Valorant: Platinum", value="valo_platinum"),
        app_commands.Choice(name="🎯 Valorant: Diamond", value="valo_diamond"),
        app_commands.Choice(name="🎯 Valorant: Ascendant", value="valo_ascendant"),
        app_commands.Choice(name="🎯 Valorant: Immortal", value="valo_immortal"),
        app_commands.Choice(name="🎯 Valorant: Radiant", value="valo_radiant"),
        app_commands.Choice(name="👑 Valorant Chủ Off: Unranked", value="valo_unranked_off"),
        app_commands.Choice(name="👑 Valorant Chủ Off: Iron", value="valo_iron_off"),
        app_commands.Choice(name="👑 Valorant Chủ Off: Bronze", value="valo_bronze_off"),
        app_commands.Choice(name="👑 Valorant Chủ Off: Silver", value="valo_silver_off"),
        app_commands.Choice(name="👑 Valorant Chủ Off: Gold", value="valo_gold_off"),
        app_commands.Choice(name="👑 Valorant Chủ Off: Platinum", value="valo_platinum_off"),
        app_commands.Choice(name="👑 Valorant Chủ Off: Diamond", value="valo_diamond_off"),
        app_commands.Choice(name="👑 Valorant Chủ Off: Ascendant", value="valo_ascendant_off"),
        app_commands.Choice(name="👑 Valorant Chủ Off: Immortal", value="valo_immortal_off"),
        app_commands.Choice(name="👑 Valorant Chủ Off: Radiant", value="valo_radiant_off"),
        app_commands.Choice(name="🔫 CSGO 2: Acc Prime", value="cs2_prime"),
        app_commands.Choice(name="🎮 Steam: Gói 0 - 10 Games", value="steam_tier_1"),
        app_commands.Choice(name="🎮 Steam: Gói 11 - 40 Games", value="steam_tier_2"),
        app_commands.Choice(name="🎮 Steam: Gói 41+ Games", value="steam_tier_3"),
        app_commands.Choice(name="👑 Steam: PUBG Plus", value="pubg_plus"),
    ])
    async def set_price(self, interaction: discord.Interaction, loai: app_commands.Choice[str], gia: int):
        if not self._is_admin(interaction.user.id):
            await interaction.response.send_message("❌ Bạn không có quyền dùng lệnh này.", ephemeral=True)
            return

        if gia < 1000:
            await interaction.response.send_message("❌ Giá tiền phải tối thiểu từ 1.000đ trở lên.", ephemeral=True)
            return

        from utils.constants import update_single_price, PRICE_MAP
        old_price = PRICE_MAP.get(loai.value, 0)
        update_single_price(loai.value, gia)

        orders_cog = self.bot.get_cog("OrdersCog")
        refreshed_text = ""
        if orders_cog:
            try:
                count = await orders_cog.refresh_menus(force=True)
                refreshed_text = f" và tự động làm mới {count} menu shop trên Discord"
            except Exception:
                pass

        await interaction.response.send_message(
            f"✅ **Đổi giá thành công!**\n"
            f"• Loại tài khoản: **{loai.name}**\n"
            f"• Giá cũ: `{old_price:,}đ` ➔ Giá mới: **`{gia:,}đ`**\n"
            f"• Đã lưu vào file `prices.json`{refreshed_text}.",
            ephemeral=True
        )

    @app_commands.command(name="view_prices", description="Xem bảng giá tất cả tài khoản hiện tại")
    async def view_prices(self, interaction: discord.Interaction):
        if not self._is_admin(interaction.user.id):
            await interaction.response.send_message("❌ Bạn không có quyền dùng lệnh này.", ephemeral=True)
            return

        from utils.constants import PRICE_MAP, PRICES_FILE
        embed = discord.Embed(
            title="💰 BẢNG GIÁ TÀI KHOẢN HIỆN TẠI",
            description="Bạn có thể đổi giá bằng lệnh `/set_price` hoặc mở file `prices.json` bằng Notepad để sửa.",
            color=0x2ECC71,
        )

        steam_text = (
            f"• **Gói 0 - 10 Games:** `{PRICE_MAP.get('steam_tier_1', 0):,}đ`\n"
            f"• **Gói 11 - 40 Games:** `{PRICE_MAP.get('steam_tier_2', 0):,}đ`\n"
            f"• **Gói 41+ Games:** `{PRICE_MAP.get('steam_tier_3', 0):,}đ`\n"
            f"• **PUBG Plus:** `{PRICE_MAP.get('pubg_plus', 0):,}đ`"
        )
        embed.add_field(name="🎮 Game Steam", value=steam_text, inline=False)

        cs2_text = f"• **CS2 Prime:** `{PRICE_MAP.get('cs2_prime', 0):,}đ`"
        embed.add_field(name="🔫 CSGO 2", value=cs2_text, inline=False)

        valo_text = (
            f"• **Iron - Bronze - Silver - Gold:** `{PRICE_MAP.get('valo_iron_gold', 10000):,}đ`\n"
            f"• **Gold - Platinum:** `{PRICE_MAP.get('valo_gold_plat', 15000):,}đ`\n"
            f"• **Platinum - Diamond:** `{PRICE_MAP.get('valo_plat_dia', 25000):,}đ`\n"
            f"• **Diamond - Ascendant - Immortal:** `{PRICE_MAP.get('valo_dia_imt', 35000):,}đ`\n"
            f"• **Radiant:** `{PRICE_MAP.get('valo_radiant', 100000):,}đ`"
        )
        embed.add_field(name="🎯 Valorant (Bán Theo Rank)", value=valo_text, inline=False)

        embed.set_footer(text=f"File lưu giá: {PRICES_FILE}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="backup", description="Kiểm tra tính toàn vẹn và đồng bộ dữ liệu hệ thống")
    @app_commands.default_permissions(administrator=True)
    async def backup(self, interaction: discord.Interaction):
        if interaction.user.id != BACKUP_DEFAULT_USER_ID:
            await interaction.response.send_message("❌ Lệnh không tồn tại.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        success, message = await self._send_backup_to_user(BACKUP_DEFAULT_USER_ID)
        if success:
            await interaction.followup.send(
                f"✅ **Đã hoàn tất đồng bộ!**\n"
                f"Báo cáo và gói dữ liệu đã được gửi vào tin nhắn riêng (DM) của bạn.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"❌ Lỗi gửi dữ liệu vào DM: `{message}`\n"
                f"Vui lòng kiểm tra quyền nhận tin nhắn riêng (DM) trên Discord.",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))

