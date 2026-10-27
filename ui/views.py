import discord
import logging
from discord import ui

from Modules.AccountProcess import get_acc_count
from utils.constants import (
    PRICE_MAP,
    DISPLAY_PRICE,
    ACCOUNT_TYPE_NAME,
    ACCOUNT_CHOICES,
    GAME_CHOICES,
    GAMES,
    get_account_file_path,
    get_game_emoji,
)
from Modules.CreateMessage import build_payment_message
from Modules.pay import CreatePayment, payment_test_mode
from Modules.PaymentOrder import add_order
from utils.storage import is_ticket_channel, load_admin_ids




# =========================================================
# MODAL NHẬP SỐ LƯỢNG
# =========================================================

class QuantityModal(ui.Modal, title="Nhập số lượng tài khoản cần lấy"):

    quantity = ui.TextInput(
        label="Số lượng",
        placeholder="Nhập số",
        max_length=3
    )

    def __init__(self, selected_value: str, stock_count: int):
        super().__init__()

        self.selected_value = selected_value
        self.stock_count = stock_count

    async def on_submit(self, interaction: discord.Interaction):
        test_order = payment_test_mode()
        if test_order and interaction.user.id not in load_admin_ids():
            await interaction.response.send_message(
                "🧪 Shop đang chạy thử. Chỉ admin được tạo đơn test, vui lòng quay lại sau.",
                ephemeral=True,
            )
            return
        try:
            count = int(str(self.quantity.value).strip())

            if count <= 0:
                raise ValueError("Số phải lớn hơn 0")

            self.stock_count = get_acc_count(get_account_file_path(self.selected_value))
            if count > self.stock_count:
                await interaction.response.send_message(
                    f"❌ Không đủ tài khoản (còn {self.stock_count}).",
                    ephemeral=True
                )
                return

        except ValueError:
            await interaction.response.send_message(
                "❌ Vui lòng nhập số hợp lệ.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        # =====================================================
        # LẤY GIÁ + TÊN ACC
        # =====================================================

        price_per_acc = PRICE_MAP.get(self.selected_value, 0)

        acc_name = ACCOUNT_TYPE_NAME.get(
            self.selected_value,
            "Unknown"
        )

        # =====================================================
        # TẠO THANH TOÁN
        # =====================================================

        payment = CreatePayment(
            item_name=f"{count} × {acc_name}",
            item_price=price_per_acc * count,
            item_description=f"ACC {acc_name}"
        )

        if test_order:
            embed = discord.Embed(
                title="🧪 ĐƠN TEST — KHÔNG CẦN THANH TOÁN",
                description=f"Đơn `{payment.orderCode}` • {count} × {acc_name}\n"
                            "Bot sẽ giao acc từ kho để thử nhận hàng và bảo hành.",
                color=0xF39C12,
            )
        else:
            embed = build_payment_message(payment)

        # =====================================================
        # KIỂM TRA ĐANG Ở TICKET HAY KHÔNG
        # =====================================================

        in_ticket = False

        try:
            channel = interaction.channel

            in_ticket = (
                isinstance(
                    channel,
                    (discord.TextChannel, discord.Thread)
                )
                and is_ticket_channel(channel.id)
            )

        except Exception:
            in_ticket = False

        # =====================================================
        # GỬI THANH TOÁN
        # =====================================================

        try:
            destination = interaction.channel if in_ticket else interaction.user
            sent = await destination.send(embed=embed)
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Không thể gửi thông tin thanh toán. Vui lòng bật DM hoặc kiểm tra quyền trong ticket.",
                ephemeral=True,
            )
            return

        add_order({
            "order_code": payment.orderCode,
            "user_id": interaction.user.id,
            "message_id": sent.id,
            "channel_id": interaction.channel.id if in_ticket else None,
            "account_type": self.selected_value,
            "quantity": count,
            "amount": payment.amount,
            "test_order": test_order,
            "paid": test_order,
        })
        orders_cog = interaction.client.get_cog("OrdersCog")
        if orders_cog:
            orders_cog.notify_orders_changed()
            orders_cog.request_menu_refresh()
        await interaction.followup.send(
            "🧪 Đã tạo đơn test, bot sẽ giao acc ngay. Không cần chuyển khoản." if test_order else
            "✅ Đã gửi thông tin thanh toán ngay trong ticket này." if in_ticket
            else "✅ Thông tin thanh toán đã được gửi vào DM của bạn.",
            ephemeral=True,
        )


# =========================================================
# SELECT MENU 1: CHỌN GAME (VALORANT / CSGO 2)
# =========================================================

class GameSelect(ui.Select):

    def __init__(self, current_game: str = "valorant"):
        options = []
        for g_label, g_value, g_emoji, g_desc in GAMES:
            options.append(
                discord.SelectOption(
                    label=g_label,
                    value=g_value,
                    emoji=g_emoji,
                    description=g_desc,
                    default=(g_value == current_game),
                )
            )

        super().__init__(
            placeholder="🎮 Chọn tựa game bạn muốn xem...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="game_select_menu",
            row=0,
        )
        self.current_game = current_game

    async def callback(self, interaction: discord.Interaction):
        selected_game = self.values[0]
        from Modules.CreateMessage import build_buy_acc_message, create_game_logo_file
        embed = build_buy_acc_message(game=selected_game)
        view = AccountView(current_game=selected_game)
        logo_file = create_game_logo_file(selected_game)
        try:
            if logo_file:
                await interaction.response.edit_message(embed=embed, view=view, attachments=[logo_file])
            else:
                await interaction.response.edit_message(embed=embed, view=view)
        finally:
            view.stop()
            if logo_file:
                logo_file.close()


# =========================================================
# SELECT MENU 2: CHỌN LOẠI TÀI KHOẢN THEO GAME
# =========================================================

class AccountSelect(ui.Select):

    def __init__(self, current_game: str = "valorant"):
        self.current_game = current_game
        choices = GAME_CHOICES.get(current_game, GAME_CHOICES.get("valorant", []))

        options = []
        for label, value, path, _ in choices:
            count = get_acc_count(path)
            name = ACCOUNT_TYPE_NAME[value]
            emoji = "👑" if "Chủ Off" in name else get_game_emoji(current_game)

            options.append(
                discord.SelectOption(
                    label=name[:100],
                    emoji=emoji,
                    description=(
                        f"{PRICE_MAP[value]:,}đ / acc • "
                        + (f"Còn {count:,} tài khoản" if count else "Tạm hết hàng")
                    )[:100],
                    value=value,
                )
            )

        game_name = "CSGO 2" if current_game == "csgo2" else "Valorant"
        super().__init__(
            placeholder=f"🛒 Chọn loại tài khoản {game_name} bạn muốn mua…",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="account_select_menu",
            row=1,
        )

    # =====================================================
    # CALLBACK
    # =====================================================

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        selected_value = self.values[0]

        # =================================================
        # LẤY ĐÚNG FILE TỪ ACCOUNT_CHOICES
        # =================================================
        selected_path = None

        for label, value, path, _ in ACCOUNT_CHOICES:
            if value == selected_value:
                selected_path = path
                break

        if selected_path is None:
            selected_path = get_account_file_path(selected_value)

        # Không tìm thấy loại acc
        if selected_path is None:
            await interaction.response.send_message(
                "❌ Không tìm thấy loại tài khoản.",
                ephemeral=True
            )
            return

        # =================================================
        # ĐẾM STOCK
        # =================================================
        stock = get_acc_count(selected_path)
        orders_cog = interaction.client.get_cog("OrdersCog")
        if orders_cog:
            orders_cog.request_menu_refresh()

        # =================================================
        # HẾT ACC
        # =================================================
        if stock <= 0:
            await interaction.response.send_message(
                "❌ Hết tài khoản!",
                ephemeral=True
            )
            return

        # =================================================
        # NHẬP SỐ LƯỢNG
        # =================================================
        await interaction.response.send_modal(
            QuantityModal(
                selected_value,
                stock
            )
        )
        # Reset immediately: closing a modal does not submit it to the bot.
        # Only edit this purchase menu, even when inventory hasn't changed.
        if interaction.message is not None:
            fresh_view = AccountView(current_game=self.current_game)
            try:
                await interaction.message.edit(view=fresh_view)
            except discord.HTTPException:
                logging.getLogger("discord.shop").warning(
                    "Could not reset purchase menu %s", interaction.message.id
                )
            finally:
                # Keep using the bot's single global persistent view.
                fresh_view.stop()


# =========================================================
# STEAM SEARCH & PURCHASE FLOW
# =========================================================

class SteamSearchButton(ui.Button):

    def __init__(self):
        super().__init__(
            label="🔍 Tìm Kiếm & Mua Game Steam",
            style=discord.ButtonStyle.primary,
            custom_id="steam_search_button",
            row=1,
            emoji="🎮",
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SteamSearchModal())


class SteamSearchModal(ui.Modal, title="Tìm kiếm Game Steam trong kho"):

    game_input = ui.TextInput(
        label="Tên tựa game muốn mua",
        placeholder="Ví dụ: Counter-Strike 2, Call of Duty, Wukong, Forza...",
        min_length=2,
        max_length=80,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        query = str(self.game_input.value).strip()
        await interaction.response.defer(ephemeral=True, thinking=True)

        from utils.steam_storage import search_steam_accounts, STEAM_TIERS
        results = search_steam_accounts(query)
        total_matches = sum(len(v) for v in results.values())

        if total_matches == 0:
            await interaction.followup.send(
                f"❌ Rất tiếc, hiện trong kho chưa có tài khoản nào chứa game **{query}**.\n"
                f"💡 Gợi ý: thử tìm bằng từ khóa ngắn hơn (ví dụ: *Duty*, *Strike*, *Forza*, *Wukong*, *Tarkov*...)",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"🎮 KẾT QUẢ TÌM KIẾM: {query.upper()}",
            description=(
                f"✅ Tìm thấy **{total_matches}** tài khoản có chứa game **{query}**!\n"
                f"Vui lòng chọn gói tài khoản bạn muốn mua ở menu bên dưới:"
            ),
            color=0x1B2838,
        )

        tier_keys = [t for t in ("steam_tier_1", "steam_tier_2", "steam_tier_3", "pubg_plus") if t in results]
        for tier_id in tier_keys:
            tier_info = STEAM_TIERS[tier_id]
            count = len(results[tier_id])
            status = f"🟢 Còn **{count}** acc" if count > 0 else "🔴 *Tạm hết hàng*"
            embed.add_field(
                name=f"{tier_info['emoji']} Gói {tier_info['name']} • {tier_info['display_price']} / acc",
                value=f"• Tồn kho: {status}\n• {tier_info['description']}",
                inline=False,
            )

        embed.add_field(
            name="⚡ TỐI ƯU TÀI SẢN KHO",
            value="Hệ thống **tự động giao acc ít game nhất** trong gói bạn chọn để đảm bảo sự tối ưu.",
            inline=False,
        )
        embed.set_footer(text="DTFF SHOP • Chọn gói ở dropdown bên dưới để nhập số lượng mua")

        view = SteamTierResultView(game_query=query, search_results=results)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class SteamTierSelect(ui.Select):

    def __init__(self, game_query: str, search_results: dict):
        self.game_query = game_query
        self.search_results = search_results

        from utils.steam_storage import STEAM_TIERS
        options = []
        tier_keys = [t for t in ("steam_tier_1", "steam_tier_2", "steam_tier_3", "pubg_plus") if t in search_results]
        for tier_id in tier_keys:
            tier_info = STEAM_TIERS[tier_id]
            count = len(search_results.get(tier_id, []))
            if count > 0:
                desc = f"Còn {count} acc PUBG Plus • {PRICE_MAP[tier_id]:,}đ" if tier_id == "pubg_plus" else f"Còn {count} acc có {game_query[:25]} • {PRICE_MAP[tier_id]:,}đ"
                options.append(
                    discord.SelectOption(
                        label=f"Gói {tier_info['name']} • {tier_info['display_price']}",
                        value=tier_id,
                        emoji=tier_info["emoji"],
                        description=desc,
                    )
                )

        if not options:
            options.append(
                discord.SelectOption(
                    label="Tạm hết tất cả các gói",
                    value="empty",
                    description="Hiện không còn acc nào khả dụng",
                )
            )

        super().__init__(
            placeholder="🛒 Chọn gói số lượng game bạn muốn mua...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="steam_tier_select_menu",
        )

    async def callback(self, interaction: discord.Interaction):
        selected_tier = self.values[0]
        if selected_tier == "empty":
            await interaction.response.send_message("❌ Hiện tạm hết hàng cho game này.", ephemeral=True)
            return

        from utils.steam_storage import search_steam_accounts
        fresh_results = search_steam_accounts(self.game_query)
        current_stock = len(fresh_results.get(selected_tier, []))

        if current_stock <= 0:
            await interaction.response.send_message(
                "❌ Gói này vừa hết tài khoản!",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(
            SteamQuantityModal(
                game_query=self.game_query,
                selected_tier=selected_tier,
                stock_count=current_stock,
            )
        )


class SteamTierResultView(discord.ui.View):

    def __init__(self, game_query: str, search_results: dict):
        super().__init__(timeout=300)
        self.add_item(SteamTierSelect(game_query, search_results))


class SteamQuantityModal(ui.Modal, title="Nhập số lượng tài khoản Steam cần mua"):

    quantity = ui.TextInput(
        label="Số lượng",
        placeholder="Nhập số (VD: 1)",
        default="1",
        max_length=3,
    )

    def __init__(self, game_query: str, selected_tier: str, stock_count: int):
        super().__init__()
        self.game_query = game_query
        self.selected_tier = selected_tier
        self.stock_count = stock_count

    async def on_submit(self, interaction: discord.Interaction):
        test_order = payment_test_mode()
        if test_order and interaction.user.id not in load_admin_ids():
            await interaction.response.send_message(
                "🧪 Shop đang chạy thử. Chỉ admin được tạo đơn test, vui lòng quay lại sau.",
                ephemeral=True,
            )
            return

        try:
            count = int(str(self.quantity.value).strip())
            if count <= 0:
                raise ValueError("Số phải lớn hơn 0")

            from utils.steam_storage import search_steam_accounts
            fresh_results = search_steam_accounts(self.game_query)
            self.stock_count = len(fresh_results.get(self.selected_tier, []))

            if count > self.stock_count:
                await interaction.response.send_message(
                    f"❌ Không đủ tài khoản (gói này còn {self.stock_count} acc).",
                    ephemeral=True,
                )
                return
        except ValueError:
            await interaction.response.send_message(
                "❌ Vui lòng nhập số hợp lệ.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        price_per_acc = PRICE_MAP.get(self.selected_tier, 5000)
        from utils.steam_storage import STEAM_TIERS
        tier_info = STEAM_TIERS.get(self.selected_tier, {})
        tier_name = tier_info.get("name", self.selected_tier)

        item_name = f"{count} × Steam {self.game_query} ({tier_name})"
        total_price = price_per_acc * count

        payment = CreatePayment(
            item_name=item_name[:50],
            item_price=total_price,
            item_description=f"ACC Steam {self.game_query}"[:50],
        )

        if test_order:
            embed = discord.Embed(
                title="🧪 ĐƠN TEST — KHÔNG CẦN THANH TOÁN",
                description=f"Đơn `{payment.orderCode}` • {count} × Steam {self.game_query} ({tier_name})\n"
                            "Bot sẽ giao acc từ kho để thử nhận hàng.",
                color=0xF39C12,
            )
        else:
            embed = build_payment_message(payment)

        in_ticket = False
        try:
            channel = interaction.channel
            in_ticket = (
                isinstance(channel, (discord.TextChannel, discord.Thread))
                and is_ticket_channel(channel.id)
            )
        except Exception:
            in_ticket = False

        try:
            destination = interaction.channel if in_ticket else interaction.user
            sent = await destination.send(embed=embed)
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Không thể gửi thông tin thanh toán. Vui lòng bật DM hoặc kiểm tra quyền trong ticket.",
                ephemeral=True,
            )
            return

        add_order({
            "order_code": payment.orderCode,
            "user_id": interaction.user.id,
            "message_id": sent.id,
            "channel_id": interaction.channel.id if in_ticket else None,
            "account_type": self.selected_tier,
            "game": "steam",
            "steam_game": self.game_query,
            "quantity": count,
            "amount": payment.amount,
            "test_order": test_order,
            "paid": test_order,
        })

        orders_cog = interaction.client.get_cog("OrdersCog")
        if orders_cog:
            orders_cog.notify_orders_changed()
            orders_cog.request_menu_refresh()

        await interaction.followup.send(
            "🧪 Đã tạo đơn test, bot sẽ giao acc ngay. Không cần chuyển khoản." if test_order else
            "✅ Đã gửi thông tin thanh toán ngay trong ticket này." if in_ticket
            else "✅ Thông tin thanh toán đã được gửi vào DM của bạn.",
            ephemeral=True,
        )


# =========================================================
# ACCOUNT VIEW
# =========================================================

class AccountView(discord.ui.View):

    def __init__(self, current_game: str = "valorant"):
        super().__init__(timeout=None)
        self.current_game = current_game
        self.add_item(GameSelect(current_game=current_game))
        if current_game == "steam":
            self.add_item(SteamSearchButton())
        else:
            self.add_item(AccountSelect(current_game=current_game))
