import os
import discord

def create_game_logo_file(game: str = "valorant") -> discord.File | None:
    """Tạo đối tượng discord.File cho logo game tương ứng nếu file tồn tại."""
    from utils.constants import get_game_logo_path, get_game_logo_filename
    path = get_game_logo_path(game)
    if os.path.exists(path):
        return discord.File(path, filename=get_game_logo_filename(game))
    return None

def build_payment_message(payment):
    from Modules import pay
    from Modules.PaymentOrder import PENDING_TTL_SECONDS

    bank_code = (pay.BANK_CODE or "").strip()
    bank_name = "MB BANK" if bank_code.upper() in {"MB", "MBB", "MBBANK", "MB BANK"} else (bank_code or "Chưa cấu hình")
    amount = f"{payment.amount:,.0f}".replace(",", ".")
    order_code = getattr(payment, "orderCode", None) or getattr(payment, "order_code", None) or payment.memo
    duration = (f"{PENDING_TTL_SECONDS // 60} phút" if PENDING_TTL_SECONDS % 60 == 0
                else f"{PENDING_TTL_SECONDS} giây")
    embed = discord.Embed(
        title="💳 THANH TOÁN ĐƠN HÀNG",
        description=f"🛍️ **{payment.item_name}**\nKiểm tra số tiền và nội dung trước khi chuyển khoản.",
        color=0x5865F2,
    )
    embed.set_author(name="DTFF SHOP • THANH TOÁN")
    embed.add_field(name="💰 Số tiền", value=f"**{amount} VNĐ**", inline=True)
    embed.add_field(name="📝 Nội dung", value=f"`{payment.memo}`", inline=True)
    embed.add_field(name="🏦 Ngân hàng", value=f"**{bank_name}**", inline=True)
    embed.add_field(name="💳 Số tài khoản", value=f"`{pay.ACCOUNT_NO or 'Chưa cấu hình'}`", inline=True)
    embed.add_field(name="👤 Chủ tài khoản", value=pay.ACCOUNT_NAME or "Chưa cấu hình", inline=True)
    embed.add_field(name="⏳ Thời hạn", value=f"**{duration}** từ khi tạo đơn", inline=True)
    qr_url = getattr(payment, "qrUrl", None) or getattr(payment, "qr_url", None)
    if qr_url:
        embed.set_thumbnail(url=qr_url)
        embed.add_field(name="📲 Quét mã thanh toán", value=f"[Mở QR kích thước lớn]({qr_url})", inline=False)
    embed.add_field(
        name="📌 Lưu ý",
        value="Giữ nguyên nội dung chuyển khoản. Hết hạn: tạo đơn mới trước khi trả tiền.\nĐọc <#1395053297080991874> • Chơi tại net cần bật **Secure Boot**.",
        inline=False,
    )
    embed.add_field(
        name="🛠️ Hỗ trợ kỹ thuật",
        value="Cần hướng dẫn chơi cheat hoặc gặp lỗi **HVCI** và các lỗi khác? Xem <#1555949395109748807>.",
        inline=False,
    )
    embed.set_footer(text=f"Mã đơn: {order_code} • Giữ mã đơn khi cần hỗ trợ")
    return embed


def build_buy_acc_message(game: str = "valorant") -> discord.Embed:
    """One compact storefront, refreshed together with its purchase selector."""
    from utils.constants import GAME_CHOICES, ACCOUNT_TYPE_NAME, PRICE_MAP, get_game_logo_filename

    if game == "steam":
        from utils.steam_storage import get_total_steam_count, get_steam_tier_counts
        total = get_total_steam_count()
        tier_counts = get_steam_tier_counts()
        logo_filename = get_game_logo_filename("steam")
        embed = discord.Embed(
            title="TÀI KHOẢN GAME STEAM THEO YÊU CẦU",
            description=(
                f"🟢 **{total:,} tài khoản Steam sẵn sàng trong kho**\n"
                f"Bấm nút **🔍 Tìm Kiếm Game** bên dưới để tìm tài khoản có tựa game bạn muốn mua!"
                if total else
                "🔴 **Tạm hết hàng Steam**\nKho sẽ được cập nhật khi có tài khoản mới."
            ),
            color=0x1B2838 if total else 0x95A5A6,
        )
        embed.set_author(name="DTFF SHOP • GAME STEAM", icon_url=f"attachment://{logo_filename}")
        embed.set_thumbnail(url=f"attachment://{logo_filename}")

        t1_count = tier_counts.get("steam_tier_1", 0)
        t2_count = tier_counts.get("steam_tier_2", 0)
        t3_count = tier_counts.get("steam_tier_3", 0)

        p1 = f"{PRICE_MAP.get('steam_tier_1', 5000):,}đ".replace(",", ".")
        p2 = f"{PRICE_MAP.get('steam_tier_2', 15000):,}đ".replace(",", ".")
        p3 = f"{PRICE_MAP.get('steam_tier_3', 25000):,}đ".replace(",", ".")

        embed.add_field(
            name=f"🟢 GÓI 0 - 10 GAMES • {p1} / ACC",
            value=f"• Còn **{t1_count:,}** acc trong kho\n• Tiết kiệm nhất, ít game thừa, tập trung đúng tựa game bạn cần.",
            inline=False,
        )
        embed.add_field(
            name=f"🟡 GÓI 11 - 40 GAMES • {p2} / ACC",
            value=f"• Còn **{t2_count:,}** acc trong kho\n• Nhận kèm nhiều tựa game phụ hấp dẫn cùng tài khoản.",
            inline=False,
        )
        embed.add_field(
            name=f"🔴 GÓI 41+ GAMES • {p3} / ACC",
            value=f"• Còn **{t3_count:,}** acc trong kho\n• Kho game khủng, giá trị thực tế hàng triệu đồng trên Steam.",
            inline=False,
        )
        embed.add_field(
            name="⚡ CƠ CHẾ GIAO ACC TỐI ƯU",
            value="Hệ thống **tự động ưu tiên giao acc ít game nhất** trong gói bạn chọn để đảm bảo sự tối ưu tài sản và quyền lợi tốt nhất.",
            inline=False,
        )
        embed.add_field(
            name="🛒 HƯỚNG DẪN MUA",
            value="**1.** Bấm nút **🔍 Tìm Kiếm Game** bên dưới\n**2.** Nhập tên game bạn muốn mua (VD: *Black Myth, Call of Duty, CS2...*)\n**3.** Chọn gói số lượng game & quét QR thanh toán nhận acc ngay.",
            inline=False,
        )
        embed.set_footer(text="DTFF SHOP • Kho game Steam bản quyền • Cập nhật tự động")
        return embed

    from Modules.AccountProcess import get_acc_count
    choices = GAME_CHOICES.get(game, GAME_CHOICES.get("valorant", []))
    is_cs = (game == "csgo2")

    groups = {False: [], True: []}
    counts = {}
    for _, value, path, _ in choices:
        if path not in counts:
            counts[path] = get_acc_count(path)
        count = counts[path]
        if count <= 0:
            continue
        name = ACCOUNT_TYPE_NAME[value]
        off = "Chủ Off" in name
        short_name = name.replace(" Chủ Off", "")
        price = f"{PRICE_MAP[value]:,}".replace(",", ".")
        groups[off].append(f"**{short_name}**\n`{price}đ` · Còn **{count:,}** acc")

    total = sum(counts.values())
    game_title = "CSGO 2" if is_cs else "VALORANT"
    game_color = 0xDE9B35 if is_cs else 0x5865F2
    logo_filename = get_game_logo_filename(game)

    embed = discord.Embed(
        title=f"TÀI KHOẢN {game_title}",
        description=(
            f"🟢 **{total:,} tài khoản sẵn có**\n"
            f"Chọn game & loại tài khoản {game_title} trong menu bên dưới."
            if total else f"🔴 **Tạm hết hàng {game_title}**\nKho sẽ được cập nhật khi có tài khoản mới."
        ),
        color=game_color if total else 0x95A5A6,
    )
    embed.set_author(name=f"DTFF SHOP • {game_title}", icon_url=f"attachment://{logo_filename}")
    embed.set_thumbnail(url=f"attachment://{logo_filename}")

    if is_cs:
        if groups[False]:
            embed.add_field(name="💣 CSGO 2 PRIME", value="\n\n".join(groups[False]), inline=False)
        elif not total:
            embed.add_field(name="💣 CSGO 2 PRIME", value="`50.000đ` · *Tạm hết hàng*", inline=False)
    else:
        normal_lines = []
        off_lines = []
        for _, value, path, _ in choices:
            count = counts.get(path, 0)
            name = ACCOUNT_TYPE_NAME.get(value, value)
            price = f"{PRICE_MAP.get(value, 0):,}".replace(",", ".")
            status = f"🟢 Còn **{count:,}** acc" if count > 0 else "🔴 *Tạm hết hàng*"
            if "Chủ Off" in name:
                display_name = name.replace(" Chủ Off", "")
                off_lines.append(f"• **{display_name}**\n  ↳ Giá: **`{price}đ`** · {status}")
            else:
                normal_lines.append(f"• **{name}**\n  ↳ Giá: **`{price}đ`** · {status}")

        if normal_lines:
            embed.add_field(name="🎯 ACC VALORANT THEO RANK (THƯỜNG • BH 2H)", value="\n".join(normal_lines), inline=False)
        if off_lines:
            embed.add_field(name="👑 ACC VALORANT THEO RANK (CHỦ OFF • BH 5H)", value="\n".join(off_lines), inline=False)

    embed.add_field(
        name="🛒 CÁCH MUA",
        value="**1.** Chọn Game  →  **2.** Chọn loại acc  →  **3.** Nhập số lượng\n**4.** Quét QR và thanh toán đúng số tiền, nội dung để nhận acc.",
        inline=False,
    )
    if not is_cs:
        embed.add_field(
            name="📌 TRƯỚC KHI MUA",
            value="Đọc <#1395053297080991874> trước khi thanh toán.\nChơi tại quán net: cần bật **Secure Boot**.",
            inline=False,
        )
    embed.set_footer(text="Giá tính trên 1 tài khoản • Tồn kho cập nhật theo giao dịch")
    return embed



def build_delivery_message(order, accounts):
    """Return the delivery card and whether credentials need a TXT attachment."""
    from utils.constants import ACCOUNT_TYPE_NAME, PRICE_MAP, get_game_logo_filename

    account_type = ACCOUNT_TYPE_NAME.get(order["account_type"], order["account_type"])
    is_steam = (order.get("game") == "steam" or str(order.get("account_type", "")).startswith("steam_"))
    is_cs = (order.get("account_type") == "cs2_prime")

    if is_steam:
        game_title = "STEAM"
        logo_filename = get_game_logo_filename("steam")
        embed_color = 0x1B2838
        if order.get("steam_game"):
            account_type = f"Steam Game: {order['steam_game']} ({account_type})"
    elif is_cs:
        game_title = "CSGO 2"
        logo_filename = get_game_logo_filename("csgo2")
        embed_color = 0xDE9B35
    else:
        game_title = "VALORANT"
        logo_filename = get_game_logo_filename("valorant")
        embed_color = 0x2ECC71

    import re
    from utils.steam_storage import parse_steam_account_line
    compact_list = []
    for acc in accounts:
        if is_steam:
            parsed = parse_steam_account_line(acc)
            if parsed:
                games_snippet = ", ".join(parsed["games"][:4])
                if len(parsed["games"]) > 4:
                    games_snippet += f"... (+{len(parsed['games'])-4})"
                compact_list.append(
                    f"{parsed['username']}:{parsed['password']} | SteamID: {parsed['steam_id']} | Games({parsed['game_count']}): [{games_snippet}]"
                )
            else:
                compact_list.append(acc.strip())
        else:
            u_match = re.search(r"Username:\s*([^\r\n]+)", acc, re.IGNORECASE)
            p_match = re.search(r"Password:\s*([^\r\n]+)", acc, re.IGNORECASE)
            if u_match and p_match:
                compact_list.append(f"{u_match.group(1).strip()}:{p_match.group(1).strip()}")
            else:
                first_line = acc.strip().splitlines()[0] if acc.strip() else ""
                compact_list.append(first_line)

    credentials = "\n".join(compact_list)
    # Keep every credential intact; large lists or Markdown delimiters go in a file.
    as_file = len(credentials) + 8 > 1024 or "`" in credentials
    embed = discord.Embed(
        title=f"🎁 TÀI KHOẢN {game_title} CỦA BẠN",
        description="**Giao hàng thành công**\nCảm ơn bạn đã mua hàng tại **DTFF SHOP**!",
        color=embed_color,
    )
    embed.set_author(name=f"DTFF SHOP • GIAO TÀI KHOẢN {game_title}", icon_url=f"attachment://{logo_filename}")
    embed.set_thumbnail(url=f"attachment://{logo_filename}")
    embed.add_field(name="🎮 Loại tài khoản", value=f"**{account_type}**", inline=False)
    quantity = int(order.get("quantity", len(accounts)))
    amount = order.get("amount")
    if amount is not None and quantity > 0:
        total_price = int(amount)
        unit_price = total_price / quantity
        total_label = "💰 Tổng thanh toán"
    else:
        # Legacy orders did not store the amount: label current prices honestly.
        unit_price = PRICE_MAP.get(order["account_type"])
        total_price = unit_price * quantity if unit_price is not None else None
        total_label = "💰 Tổng theo giá hiện tại"
    if unit_price is not None:
        unit_text = f"{unit_price:,.0f}".replace(",", ".")
        total_text = f"{total_price:,.0f}".replace(",", ".")
        embed.add_field(name="🏷️ Giá / acc" if amount is not None else "🏷️ Giá hiện tại / acc",
                        value=f"**{unit_text} VNĐ**", inline=True)
        embed.add_field(name=total_label, value=f"**{total_text} VNĐ**", inline=True)
    embed.add_field(name="📦 Số lượng", value=f"**{len(accounts)} acc**", inline=True)
    embed.add_field(name="🧾 Mã đơn", value=f"`{order['order_code']}`", inline=True)
    embed.add_field(
        name="🔑 Thông tin đăng nhập",
        value="🔍 Bấm nút **Check Acc** bên dưới để xem toàn bộ chi tiết hoặc tải file log TXT / HTML!"
              if as_file else f"```\n{credentials}\n```\n🔍 *Bấm nút **Check Acc** bên dưới để xem chi tiết & tải file log TXT / HTML.*",
        inline=False,
    )
    embed.add_field(
        name="📌 Sau khi nhận",
        value="Lưu lại thông tin tài khoản và mã đơn để tra cứu khi cần hỗ trợ.\nKhông chia sẻ thông tin đăng nhập cho người khác.",
        inline=False,
    )
    embed.add_field(
        name="🛠️ Hỗ trợ kỹ thuật",
        value="Hướng dẫn chơi cheat, lỗi **HVCI** và các lỗi khác: <#1555949395109748807>.",
        inline=False,
    )
    warranty_hours = 5 if "Chủ Off" in account_type else 2
    embed.add_field(
        name="🛡️ Bảo hành",
        value=f"**{warranty_hours} giờ** từ khi giao acc • Mỗi acc bảo hành tối đa **3 lượt**, lượt 3 Admin check tay.\n"
              "Bấm **Bảo hành** bên dưới, chọn acc lỗi và tải ảnh/video (1 file cho mỗi acc).",
        inline=False,
    )
    embed.set_footer(text="DTFF SHOP • Cảm ơn bạn đã tin tưởng")
    return embed, as_file
