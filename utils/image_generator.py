import io
import os
import hashlib
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont
import requests

from utils.constants import ROOT_DIR
from utils.html_generator import get_rank_icon

CACHE_DIR = os.path.join(ROOT_DIR, "data", "icon_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

TIER_COLORS = {
    "Ultra": (250, 214, 99),
    "Exclusive": (245, 149, 91),
    "Premium": (209, 84, 141),
    "Deluxe": (0, 149, 135),
    "Select": (90, 159, 226),
    "Standard": (160, 170, 185)
}

RANK_COLORS = {
    "IRON": (107, 114, 128),
    "BRONZE": (160, 116, 75),
    "SILVER": (192, 197, 206),
    "GOLD": (246, 199, 68),
    "PLATINUM": (69, 166, 184),
    "DIAMOND": (179, 108, 235),
    "ASCENDANT": (19, 169, 117),
    "IMMORTAL": (214, 51, 108),
    "RADIANT": (255, 240, 153),
    "UNRANKED": (88, 101, 242)
}


def get_rank_color(rank_str: str) -> tuple:
    r = rank_str.upper()
    for k, v in RANK_COLORS.items():
        if k in r:
            return v
    return RANK_COLORS["UNRANKED"]


def get_cached_icon(url: str, max_size: tuple[int, int] = (130, 42)) -> Image.Image | None:
    """Tải và lưu trữ cục bộ icon skin / rank dạng PNG RGBA, co giãn chuẩn tỷ lệ."""
    if not url:
        return None
    h = hashlib.md5(url.encode("utf-8")).hexdigest()
    path = os.path.join(CACHE_DIR, f"{h}.png")

    if not os.path.exists(path):
        try:
            r = requests.get(url, timeout=3.5)
            if r.status_code == 200:
                with open(path, "wb") as f:
                    f.write(r.content)
        except Exception:
            return None

    if os.path.exists(path):
        try:
            im = Image.open(path).convert("RGBA")
            im.thumbnail(max_size, Image.Resampling.LANCZOS)
            return im
        except Exception:
            return None
    return None


def prefetch_icons(urls: list[str], max_size: tuple[int, int] = (140, 48)):
    """Tải song song nhiều icon để tối ưu tốc độ sinh ảnh lần đầu."""
    valid_urls = [u for u in urls if u]
    if not valid_urls:
        return
    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(lambda u: get_cached_icon(u, max_size), valid_urls))


def _load_fonts():
    font_bold_candidates = [
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    font_reg_candidates = [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]

    bold_path = next((f for f in font_bold_candidates if os.path.exists(f)), None)
    reg_path = next((f for f in font_reg_candidates if os.path.exists(f)), None)

    if bold_path and reg_path:
        return {
            "banner": ImageFont.truetype(bold_path, 20),
            "order": ImageFont.truetype(bold_path, 13),
            "riot_id": ImageFont.truetype(bold_path, 22),
            "section": ImageFont.truetype(bold_path, 15),
            "bold": ImageFont.truetype(bold_path, 13),
            "regular": ImageFont.truetype(reg_path, 13),
            "small": ImageFont.truetype(reg_path, 12),
            "small_bold": ImageFont.truetype(bold_path, 11),
            "tiny": ImageFont.truetype(reg_path, 11),
        }
    else:
        default = ImageFont.load_default()
        return {
            "banner": default,
            "order": default,
            "riot_id": default,
            "section": default,
            "bold": default,
            "regular": default,
            "small": default,
            "small_bold": default,
            "tiny": default,
        }


def generate_inventory_image(acc: dict, order_code: str = "") -> Image.Image:
    """
    Tạo ảnh PNG đồ họa kho đồ Valorant sắc nét, có ĐẦY ĐỦ HÌNH ẢNH CỦA MỖI SKIN và rank badge.
    Hiển thị trực tiếp trong Discord để người dùng bấm vào xem toàn màn hình và lướt lên xuống kiểm tra.
    """
    fonts = _load_fonts()
    width = 920
    margin = 24
    inner_w = width - margin * 2

    username = acc.get("username", "")
    riot_id = acc.get("riot_id") or username
    rank = acc.get("current_rank", "Unranked")
    peak = acc.get("peak_rank", "Unranked")
    level = acc.get("level", "1")
    region = acc.get("region", "NA")
    vp = acc.get("vp", "0")
    rp = acc.get("rp", "0")
    kc = acc.get("kc", "0")
    email_ok = acc.get("email_verified", False)
    phone_ok = acc.get("phone_verified", False)
    last_game = acc.get("last_game", "N/A")

    knives = [s for s in acc.get("skins", []) if s.get("weaponType") == "Cận Chiến"]
    weapons = [s for s in acc.get("skins", []) if s.get("weaponType") != "Cận Chiến"]
    total_skins = acc.get("total_skins", len(knives) + len(weapons))
    tier_counts = acc.get("tier_counts", {})

    # 1. Tải trước toàn bộ icon của các skin và rank
    all_icon_urls = [s.get("icon") for s in acc.get("skins", []) if s.get("icon")]
    rank_icon_url = get_rank_icon(rank)
    if rank_icon_url:
        all_icon_urls.append(rank_icon_url)
    prefetch_icons(all_icon_urls, max_size=(140, 48))

    # 2. Tính toán chiều cao
    knife_card_h = 64
    weapon_card_h = 56

    h = 24
    h += 190  # Header box
    h += 18   # Spacing
    if knives:
        h += 32
        knife_rows = (len(knives) + 1) // 2
        h += knife_rows * (knife_card_h + 6) + 4
        h += 16

    h += 32   # Weapons title
    h += 36   # Tier badges bar
    weapon_rows = (len(weapons) + 1) // 2
    h += max(weapon_rows * (weapon_card_h + 6) + 8, 44)
    h += 52   # Footer
    h += 24   # Bottom margin

    img = Image.new("RGB", (width, h), color=(11, 14, 20))
    draw = ImageDraw.Draw(img)

    # -----------------------------
    # 1. Header Box
    # -----------------------------
    y = 24
    header_box = (margin, y, margin + inner_w, y + 190)
    draw.rounded_rectangle(header_box, radius=12, fill=(19, 25, 36), outline=(36, 46, 66), width=1)

    # Top accent line
    draw.rounded_rectangle((margin, y, margin + inner_w, y + 4), radius=2, fill=(0, 210, 106))

    # Header top row
    draw.text((margin + 18, y + 14), "DTFF SHOP", font=fonts["banner"], fill=(0, 245, 212))
    bbox_dtff = fonts["banner"].getbbox("DTFF SHOP")
    dtff_w = bbox_dtff[2] - bbox_dtff[0]
    draw.text((margin + 24 + dtff_w, y + 18), "•  HỆ THỐNG TRA CỨU KHO TÀI KHOẢN VALORANT", font=fonts["small"], fill=(140, 155, 175))

    # Order badge on top right
    if order_code:
        order_text = f"Đơn hàng #{order_code}"
        obbox = fonts["order"].getbbox(order_text)
        ow = obbox[2] - obbox[0] + 20
        ox = margin + inner_w - 18 - ow
        draw.rounded_rectangle((ox, y + 14, ox + ow, y + 36), radius=6, fill=(20, 45, 35), outline=(0, 210, 106), width=1)
        draw.text((ox + 10, y + 16), order_text, font=fonts["order"], fill=(255, 255, 255))

    draw.line([(margin + 18, y + 48), (margin + inner_w - 18, y + 48)], fill=(30, 40, 58), width=1)

    # User info (Left column)
    draw.text((margin + 18, y + 58), riot_id, font=fonts["riot_id"], fill=(255, 255, 255))
    draw.text((margin + 18, y + 88), f"Tài khoản: {username}   |   Khu vực: {region}   |   Cấp độ: Lv {level}", font=fonts["regular"], fill=(170, 185, 205))

    # Security pills
    em_text = "✅ Email: Đã xác minh" if email_ok else "❌ Email: Chưa xác minh"
    em_color = (0, 210, 106) if email_ok else (239, 68, 68)
    draw.text((margin + 18, y + 115), em_text, font=fonts["small"], fill=em_color)

    ph_text = "✅ SĐT: Đã liên kết" if phone_ok else "❌ SĐT: Chưa liên kết"
    ph_color = (0, 210, 106) if phone_ok else (180, 190, 205)
    draw.text((margin + 180, y + 115), ph_text, font=fonts["small"], fill=ph_color)

    # Currencies bar
    curr_text = f"💎 VP: {vp}    🔷 RP: {rp}    🪙 KC: {kc}"
    draw.text((margin + 18, y + 148), curr_text, font=fonts["bold"], fill=(245, 149, 91))

    # Rank card on right (có kèm icon Rank nếu có)
    rx1 = margin + inner_w - 260
    ry1 = y + 58
    rx2 = margin + inner_w - 18
    ry2 = y + 172
    rank_color = get_rank_color(rank)
    draw.rounded_rectangle((rx1, ry1, rx2, ry2), radius=8, fill=(25, 33, 48), outline=rank_color, width=1)

    rank_im = get_cached_icon(rank_icon_url, max_size=(50, 50))
    if rank_im:
        img.paste(rank_im, (rx1 + 10, ry1 + 32), rank_im)
        r_tx = rx1 + 68
    else:
        r_tx = rx1 + 14

    draw.text((r_tx, ry1 + 12), "XẾP HẠNG RANK", font=fonts["small_bold"], fill=(140, 155, 175))
    clean_rank = rank[:18] if len(rank) > 18 else rank
    draw.text((r_tx, ry1 + 32), clean_rank, font=fonts["bold"], fill=rank_color)
    draw.text((r_tx, ry1 + 62), f"Peak: {peak}", font=fonts["small"], fill=(200, 210, 225))
    clean_date = last_game[:10] if last_game and last_game != "N/A" else "Gần đây"
    draw.text((r_tx, ry1 + 84), f"Trận cuối: {clean_date}", font=fonts["small"], fill=(140, 155, 175))

    y += 190 + 18

    # -----------------------------
    # 2. Knives Section (Có ảnh dao)
    # -----------------------------
    if knives:
        draw.text((margin, y), f"🔪 DAO & VŨ KHÍ CẬN CHIẾN ({len(knives)})", font=fonts["section"], fill=(245, 149, 91))
        y += 28

        col_w = (inner_w - 12) // 2
        for i, k in enumerate(knives):
            col = i % 2
            row = i // 2
            kx = margin + col * (col_w + 12)
            ky = y + row * (knife_card_h + 6)
            tier = k.get("tier", "Exclusive")
            t_color = TIER_COLORS.get(tier, (245, 149, 91))

            # Nền thẻ dao
            draw.rounded_rectangle((kx, ky, kx + col_w, ky + knife_card_h), radius=6, fill=(22, 28, 40), outline=(42, 54, 76), width=1)
            # Vạch màu bên trái
            draw.rounded_rectangle((kx, ky, kx + 5, ky + knife_card_h), radius=2, fill=t_color)

            # Tên dao và nhãn
            k_name = k.get("name", "Dao")
            if len(k_name) > 23:
                k_name = k_name[:21] + ".."
            draw.text((kx + 14, ky + 12), k_name, font=fonts["bold"], fill=(255, 255, 255))
            draw.text((kx + 14, ky + 36), f"{tier} • Cận Chiến", font=fonts["small"], fill=t_color)

            # Hình ảnh dao
            k_icon = get_cached_icon(k.get("icon"), max_size=(135, 50))
            if k_icon:
                ix = kx + col_w - k_icon.width - 10
                iy = ky + (knife_card_h - k_icon.height) // 2
                img.paste(k_icon, (ix, iy), k_icon)

        knife_rows = (len(knives) + 1) // 2
        y += knife_rows * (knife_card_h + 6) + 14

    # -----------------------------
    # 3. Weapons Section (Có ảnh súng)
    # -----------------------------
    draw.text((margin, y), f"🔫 KHO VŨ KHÍ & SKIN ({total_skins} SKINS)", font=fonts["section"], fill=(0, 245, 212))
    y += 28

    # Tier summary pills row
    tx = margin
    for t_name in ["Ultra", "Exclusive", "Premium", "Deluxe", "Select"]:
        c = tier_counts.get(t_name, 0)
        t_col = TIER_COLORS.get(t_name, (200, 200, 200))
        t_str = f"{t_name}: {c}"
        tw = fonts["small_bold"].getbbox(t_str)[2] - fonts["small_bold"].getbbox(t_str)[0] + 16
        draw.rounded_rectangle((tx, y, tx + tw, y + 24), radius=4, fill=(20, 26, 38), outline=t_col, width=1)
        draw.text((tx + 8, y + 4), t_str, font=fonts["small_bold"], fill=t_col)
        tx += tw + 10
    y += 34

    col_w = (inner_w - 12) // 2
    if weapons:
        for i, w in enumerate(weapons):
            col = i % 2
            row = i // 2
            wx = margin + col * (col_w + 12)
            wy = y + row * (weapon_card_h + 6)
            tier = w.get("tier", "Select")
            t_color = TIER_COLORS.get(tier, (90, 159, 226))
            w_type = w.get("weaponType", "Vũ khí")

            # Nền thẻ súng
            draw.rounded_rectangle((wx, wy, wx + col_w, wy + weapon_card_h), radius=6, fill=(16, 21, 30), outline=(28, 36, 50), width=1)
            # Vạch màu bậc súng
            draw.rounded_rectangle((wx, wy, wx + 4, wy + weapon_card_h), radius=2, fill=t_color)

            # Tên súng
            w_name = w.get("name", "Skin")
            if len(w_name) > 22:
                w_name = w_name[:20] + ".."
            draw.text((wx + 12, wy + 9), w_name, font=fonts["bold"], fill=(240, 245, 255))
            draw.text((wx + 12, wy + 31), f"{tier} • {w_type}", font=fonts["tiny"], fill=t_color)

            # Hình ảnh súng 3D
            w_icon = get_cached_icon(w.get("icon"), max_size=(132, 42))
            if w_icon:
                ix = wx + col_w - w_icon.width - 10
                iy = wy + (weapon_card_h - w_icon.height) // 2
                img.paste(w_icon, (ix, iy), w_icon)

        weapon_rows = (len(weapons) + 1) // 2
        y += weapon_rows * (weapon_card_h + 6) + 8
    else:
        draw.text((margin + 10, y + 8), "Chưa phát hiện skin súng nào trong log.", font=fonts["regular"], fill=(150, 165, 185))
        y += 40

    # -----------------------------
    # 4. Footer
    # -----------------------------
    draw.line([(margin, y), (margin + inner_w, y)], fill=(30, 40, 58), width=1)
    y += 14
    f_text = f"DTFF SHOP • Hệ thống tra cứu kho đồ tự động  |  Mã đơn: #{order_code}"
    draw.text((margin + 10, y), f_text, font=fonts["small"], fill=(130, 145, 165))
    draw.text((margin + inner_w - 200, y), "Bấm \"Tải File HTML\" để mở 3D", font=fonts["small_bold"], fill=(0, 210, 106))

    return img


def generate_inventory_image_bytes(acc: dict, order_code: str = "") -> bytes:
    """Tạo ảnh kèm đầy đủ icon skin và trả về dạng bytes PNG."""
    img = generate_inventory_image(acc, order_code)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()
