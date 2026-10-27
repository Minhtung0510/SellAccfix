import asyncio
import logging
import time
import re

import discord
from discord.ext import commands

from Modules.AccountProcess import get_random_acc, get_acc_count
from utils.constants import ACCOUNT_CHOICES
from Modules.CreateMessage import build_buy_acc_message, build_delivery_message
from Modules.PaymentOrder import load_orders, save_orders, remove_order, PENDING_TTL_SECONDS
from Modules.pay import _fetch_history, check_payment_status
from ui.views import AccountView
from ui.warranty import delivery_warranty_view
from utils.storage import (load_menus, save_menus, load_tickets, save_tickets,
                           load_stock_cooldown, save_stock_cooldown)

log = logging.getLogger(__name__)
stock_log = logging.getLogger("discord.stock")
STOCK_CHANNEL_ID = 1416059603996901427
# Coalesce channel renames independently so Discord throttling cannot delay menus.
STOCK_RENAME_INTERVAL = 600
import os
ORDER_POLL_INTERVAL = int(os.getenv("ORDER_POLL_INTERVAL", "15"))


class OrdersCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._orders_changed = asyncio.Event()
        self._menus_changed = asyncio.Event()
        self._stock_changed = asyncio.Event()
        self._stock_name = None
        self._stock_next_edit = 0.0
        self._menu_lock = asyncio.Lock()
        self._ticket_lock = asyncio.Lock()
        self._no_stock_notified = set()
        self._menu_signature = None
        self._workers = []

    def _restore_stock_cooldown(self):
        deadline = load_stock_cooldown(STOCK_CHANNEL_ID)
        if deadline is None:
            # Older versions did not persist renames; allow their limit to expire.
            deadline = time.time() + STOCK_RENAME_INTERVAL
            save_stock_cooldown(STOCK_CHANNEL_ID, deadline)
        self._stock_next_edit = deadline

    def _defer_stock_edit(self):
        self._stock_next_edit = time.time() + STOCK_RENAME_INTERVAL
        save_stock_cooldown(STOCK_CHANNEL_ID, self._stock_next_edit)

    async def cog_load(self):
        self._restore_stock_cooldown()
        self._workers = [asyncio.create_task(self._order_worker()),
                         asyncio.create_task(self._menu_worker()),
                         asyncio.create_task(self._stock_worker())]

    async def cog_unload(self):
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)

    def request_menu_refresh(self):
        self._menus_changed.set()
        self._stock_changed.set()

    def notify_orders_changed(self):
        self._orders_changed.set()

    async def _stock_worker(self):
        await self.bot.wait_until_ready()
        while True:
            await self._stock_changed.wait()
            delay = self._stock_next_edit - time.time()
            if delay > 0:
                stock_log.info("Kênh %s: đang chờ %.0f giây trước khi cập nhật tên; không cần khởi động lại.",
                               STOCK_CHANNEL_ID, delay)
                await asyncio.sleep(delay)
            else:
                await asyncio.sleep(0.5)
            # Read the latest stock after the delay, merging intervening events.
            self._stock_changed.clear()
            try:
                await self.update_stock_channel()
            except discord.Forbidden:
                stock_log.error("Kênh %s: bot thiếu quyền xem hoặc Quản lý kênh (Manage Channels).", STOCK_CHANNEL_ID)
            except discord.NotFound:
                stock_log.error("Không tìm thấy kênh %s. Kiểm tra ID kênh và server của bot.", STOCK_CHANNEL_ID)
            except discord.HTTPException as exc:
                stock_log.warning("Kênh %s: cập nhật lỗi HTTP %s; sẽ thử lại sau thời gian chờ.",
                                  STOCK_CHANNEL_ID, exc.status)
                self._defer_stock_edit()
                self._stock_changed.set()
            except Exception:
                stock_log.exception("Không cập nhật được bộ đếm kho %s", STOCK_CHANNEL_ID)

    async def update_stock_channel(self):
        # Shared stock files must only contribute once to the total.
        total = sum(get_acc_count(path) for path in dict.fromkeys(item[2] for item in ACCOUNT_CHOICES))
        name = f"🟢 CÒN {total} TÀI KHOẢN" if total else "🔴 HẾT TÀI KHOẢN"
        if name == self._stock_name:
            return
        channel = self.bot.get_channel(STOCK_CHANNEL_ID)
        if channel is None:
            channel = await self.bot.fetch_channel(STOCK_CHANNEL_ID)
        if channel.name != name:
            if time.time() < self._stock_next_edit:
                self._stock_changed.set()
                return
            # Persist before HTTP too, including interruption while Discord retries.
            self._defer_stock_edit()
            stock_log.info("Kênh %s: đang đổi tên thành %s", STOCK_CHANNEL_ID, name)
            await channel.edit(name=name, reason="Cập nhật tổng tài khoản còn trong kho")
            stock_log.info("Kênh %s: đã đổi tên thành %s", STOCK_CHANNEL_ID, name)
            self._defer_stock_edit()
        self._stock_name = name

    async def _menu_worker(self):
        await self.bot.wait_until_ready()
        while True:
            await self._menus_changed.wait()
            # Merge bursts of clicks/uploads into one refresh.
            await asyncio.sleep(0.5)
            self._menus_changed.clear()
            try:
                await self.refresh_menus()
            except Exception:
                log.exception("Không thể cập nhật menu")

    async def refresh_menus(self, force=False):
        self._stock_changed.set()
        async with self._menu_lock:
            view = AccountView()
            signature = tuple(
                (o.value, o.description, str(o.emoji))
                for item in view.children
                for o in getattr(item, "options", [])
            )
            if not force and signature == self._menu_signature:
                view.stop()
                return 0
            missing = set()
            count = 0
            failed = False
            try:
                for menu in load_menus():
                    try:
                        channel = self.bot.get_channel(menu['channel_id'])
                        if channel is None:
                            channel = await self.bot.fetch_channel(menu['channel_id'])
                        message_view = AccountView()
                        from Modules.CreateMessage import create_game_logo_file
                        logo_file = create_game_logo_file("valorant")
                        try:
                            if logo_file:
                                await channel.get_partial_message(menu['message_id']).edit(
                                    embed=build_buy_acc_message(), view=message_view, attachments=[logo_file]
                                )
                            else:
                                await channel.get_partial_message(menu['message_id']).edit(
                                    embed=build_buy_acc_message(), view=message_view
                                )
                        finally:
                            message_view.stop()
                            if logo_file:
                                logo_file.close()
                        count += 1
                    except discord.NotFound:
                        missing.add(menu['message_id'])
                    except discord.HTTPException:
                        failed = True
                        log.warning("Không cập nhật được menu %s", menu['message_id'])
                if missing:
                    # Reload so menus created during an HTTP await are retained.
                    save_menus([m for m in load_menus() if m['message_id'] not in missing])
                if not failed:
                    self._menu_signature = signature
                return count
            finally:
                # The global persistent AccountView handles interactions.
                view.stop()

    async def _ensure_ticket(self, channel):
        if not isinstance(channel, discord.TextChannel) or not channel.name.startswith('ticket-'):
            return
        async with self._ticket_lock:
            if channel.id in load_tickets():
                return
            try:
                view = AccountView()
                from Modules.CreateMessage import create_game_logo_file
                logo_file = create_game_logo_file("valorant")
                try:
                    if logo_file:
                        msg = await channel.send(embed=build_buy_acc_message(), file=logo_file, view=view)
                    else:
                        msg = await channel.send(embed=build_buy_acc_message(), view=view)
                finally:
                    view.stop()
                    if logo_file:
                        logo_file.close()
            except discord.HTTPException:
                log.warning("Không gửi được menu vào ticket %s", channel.id)
                return
            menus = load_menus()
            menus.append({'message_id': msg.id, 'channel_id': channel.id})
            save_menus(menus)
            tickets = load_tickets()
            if channel.id not in tickets:
                tickets.append(channel.id)
                save_tickets(tickets)
            self.request_menu_refresh()

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        await self._ensure_ticket(channel)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        # Covers ticket bots that create a channel, then rename/set permissions.
        await self._ensure_ticket(after)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        async with self._ticket_lock:
            tickets = load_tickets()
            if channel.id in tickets:
                save_tickets([tid for tid in tickets if tid != channel.id])
            menus = load_menus()
            kept = [m for m in menus if m['channel_id'] != channel.id]
            if len(kept) != len(menus):
                save_menus(kept)

    @commands.Cog.listener()
    async def on_ready(self):
        self._stock_name = None
        self._stock_changed.set()
        # Reconcile once on startup/reconnect, including tickets created offline.
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                await self._ensure_ticket(channel)

    async def _order_worker(self):
        await self.bot.wait_until_ready()
        while True:
            self._orders_changed.clear()
            orders = load_orders()
            if not orders:
                await self._orders_changed.wait()
                continue
            try:
                # One history request for the entire batch, off the Discord event loop.
                history = await asyncio.to_thread(_fetch_history) if any(
                    not o.get('paid') and not o.get('delivery_accounts') for o in orders
                ) else {}
                for order in orders:
                    try:
                        await self._process_order(order, history or {})
                    except Exception:
                        log.exception("Lỗi xử lý đơn %s", order.get('order_code'))
            except Exception:
                log.exception("Lỗi kiểm tra thanh toán")
            if self._orders_changed.is_set():
                continue
            remaining = load_orders()
            if not remaining:
                continue
            if all(o.get('paid') and not o.get('delivery_accounts') for o in remaining):
                # Paid orders awaiting stock resume on upload/new purchase only.
                await self._orders_changed.wait()
                continue
            try:
                await asyncio.wait_for(self._orders_changed.wait(), timeout=ORDER_POLL_INTERVAL)
            except asyncio.TimeoutError:
                pass

    def _save_order(self, order):
        orders = load_orders()
        for index, existing in enumerate(orders):
            if existing['order_code'] == order['order_code']:
                orders[index] = order
                save_orders(orders)
                return

    async def _destination(self, order):
        if order.get('channel_id'):
            return self.bot.get_channel(order['channel_id']) or await self.bot.fetch_channel(order['channel_id'])
        user = self.bot.get_user(order['user_id']) or await self.bot.fetch_user(order['user_id'])
        return await user.create_dm()

    async def _process_order(self, order, history):
        code = order['order_code']
        paid = order.get('paid') or order.get('delivery_accounts') or check_payment_status(order, history)
        if not paid:
            if time.time() - int(order.get('created_at', time.time())) > PENDING_TTL_SECONDS:
                remove_order(code)
                self._no_stock_notified.discard(code)
            return
        order['paid'] = True
        self._save_order(order)
        destination = await self._destination(order)
        accounts = order.get('delivery_accounts')
        if not accounts:
            self.bot.warranty_store.recover_allocations()
            is_steam = (order.get('game') == 'steam' or str(order.get('account_type', '')).startswith('steam_'))
            if is_steam:
                from utils.steam_storage import allocate_steam_accounts
                steam_accs = allocate_steam_accounts(
                    game_query=order.get('steam_game', ''),
                    tier_id=order['account_type'],
                    quantity=order['quantity'],
                )
                if not steam_accs:
                    if code not in self._no_stock_notified:
                        await destination.send(f"❌ Không đủ tài khoản Steam để giao (mã đơn: {code}). Liên hệ admin.")
                        self._no_stock_notified.add(code)
                    return
                accounts = [a['raw_line'] for a in steam_accs]
            else:
                accounts = get_random_acc(order['account_type'], order['quantity'])
                if not accounts:
                    if code not in self._no_stock_notified:
                        await destination.send(f"❌ Không đủ tài khoản để giao (mã đơn: {code}). Liên hệ admin.")
                        self._no_stock_notified.add(code)
                    return
            # Keep assigned accounts for retry if Discord delivery fails.
            order['delivery_accounts'] = accounts
            self._save_order(order)
            self.request_menu_refresh()
        self.bot.warranty_store.record_delivery(order, accounts)
        embed, as_file = build_delivery_message(order, accounts)
        if order.get('test_order'):
            embed.set_author(name='🧪 ĐƠN TEST • Không thu tiền • Acc lấy từ kho')
        warranty_view = delivery_warranty_view(code)
        is_steam = (order.get('game') == 'steam' or str(order.get('account_type', '')).startswith('steam_'))
        is_cs = (order.get('account_type') == 'cs2_prime')
        from Modules.CreateMessage import create_game_logo_file
        if is_steam:
            logo_game = 'steam'
        elif is_cs:
            logo_game = 'csgo2'
        else:
            logo_game = 'valorant'
        logo_file = create_game_logo_file(logo_game)
        files = []
        if logo_file:
            files.append(logo_file)
        if as_file:
            import io
            raw_creds = '\n'.join(accounts)
            files.append(discord.File(io.BytesIO(raw_creds.encode('utf-8')), filename=f'{code}.txt'))

        try:
            if files:
                await destination.send(embed=embed, files=files, view=warranty_view)
            else:
                await destination.send(embed=embed, view=warranty_view)
        finally:
            warranty_view.stop()
            for f in files:
                f.close()
        self.bot.warranty_store.mark_delivered(code)
        remove_order(code)
        self._no_stock_notified.discard(code)

        try:
            from ui.check_acc import remove_account_from_logs
            for acc_item in accounts:
                u_match = re.search(r"Username:\s*([^\r\n]+)", acc_item, re.IGNORECASE)
                if u_match:
                    uname = u_match.group(1).strip()
                elif ":" in acc_item and "\n" not in acc_item:
                    uname = acc_item.split(":", 1)[0].strip()
                else:
                    first_line = acc_item.strip().splitlines()[0] if acc_item.strip() else ""
                    uname = first_line.split(":", 1)[0].strip() if ":" in first_line else first_line
                if uname:
                    remove_account_from_logs(uname)
        except Exception as ex:
            log.warning("Lỗi dọn dẹp log: %s", ex)

        try:
            await destination.get_partial_message(order['message_id']).delete()
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(OrdersCog(bot))
