import json
import os


# =========================================================
# PATH
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

MENUS_FILE = os.path.join(ROOT_DIR, "data", "menus.json")
TICKET_FILE = os.path.join(ROOT_DIR, "data", "tickets.json")
ADMINS_FILE = os.path.join(ROOT_DIR, "Admins.json")
ACCOUNT_FOLDER = os.path.join(ROOT_DIR, "data")
ASSETS_DIR = os.path.join(ROOT_DIR, "assets")

VALORANT_LOGO_PATH = os.path.join(ASSETS_DIR, "valorant_logo.png")
CS2_LOGO_PATH = os.path.join(ASSETS_DIR, "cs2_logo.png")
STEAM_LOGO_PATH = os.path.join(ASSETS_DIR, "steam_logo.png")


def get_game_logo_path(game: str = "valorant") -> str:
    """Trả về đường dẫn file logo tương ứng với tựa game ('valorant', 'csgo2' hoặc 'steam')."""
    g = str(game).lower()
    if g in ("csgo2", "cs2", "cs2_prime", "csgo"):
        return CS2_LOGO_PATH
    if g in ("steam", "steam_game"):
        return STEAM_LOGO_PATH
    return VALORANT_LOGO_PATH


def get_game_logo_filename(game: str = "valorant") -> str:
    """Trả về tên file attachment cho logo ('cs2_logo.png', 'steam_logo.png' hoặc 'valorant_logo.png')."""
    g = str(game).lower()
    if g in ("csgo2", "cs2", "cs2_prime", "csgo"):
        return "cs2_logo.png"
    if g in ("steam", "steam_game"):
        return "steam_logo.png"
    return "valorant_logo.png"


VALORANT_EMOJI_ID = 1556597871720013824
CS2_EMOJI_ID = 1556597873662099467
STEAM_EMOJI_ID = 1556773313886298123


def get_game_emoji(game: str = "valorant"):
    """Trả về PartialEmoji hoặc Unicode emoji logo game để hiển thị trong SelectOption."""
    import discord
    g = str(game).lower()
    if g in ("csgo2", "cs2", "cs2_prime", "csgo"):
        return discord.PartialEmoji(name="dtff_cs2", id=CS2_EMOJI_ID)
    if g in ("steam", "steam_game"):
        return discord.PartialEmoji(name="dtff_steam", id=STEAM_EMOJI_ID)
    return discord.PartialEmoji(name="dtff_valorant", id=VALORANT_EMOJI_ID)


# =========================================================
# GIÁ TÀI KHOẢN (MẶC ĐỊNH - ĐỒNG BỘ QUA prices.json)
# =========================================================

PRICE_MAP = {
    # =========================================================
    # VALORANT - TỪNG BẬC RANK RIÊNG BIỆT (GÓI THƯỜNG)
    # =========================================================
    "valo_unranked": 10000,
    "valo_iron": 10000,
    "valo_bronze": 12000,
    "valo_silver": 15000,
    "valo_gold": 20000,
    "valo_platinum": 25000,
    "valo_diamond": 35000,
    "valo_ascendant": 50000,
    "valo_immortal": 70000,
    "valo_radiant": 100000,

    # =========================================================
    # VALORANT - TỪNG BẬC RANK RIÊNG BIỆT (GÓI CHỦ OFF - x2 GIÁ)
    # =========================================================
    "valo_unranked_off": 20000,
    "valo_iron_off": 20000,
    "valo_bronze_off": 24000,
    "valo_silver_off": 30000,
    "valo_gold_off": 40000,
    "valo_platinum_off": 50000,
    "valo_diamond_off": 70000,
    "valo_ascendant_off": 100000,
    "valo_immortal_off": 140000,
    "valo_radiant_off": 200000,

    # CSGO 2
    "cs2_prime": 50000,

    # STEAM TIERS (giá theo số game)
    "steam_tier_1": 5000,
    "steam_tier_2": 15000,
    "steam_tier_3": 25000,
    "pubg_plus": 50000,

    # Legacy fallbacks
    "valo_iron_gold": 10000,
    "valo_gold_plat": 15000,
    "valo_plat_dia": 25000,
    "valo_dia_imt": 35000,
    "valo_iron_gold_off": 20000,
    "valo_gold_plat_off": 30000,
    "valo_plat_dia_off": 50000,
    "valo_dia_imt_off": 70000,
    "5k": 5000,
    "10k": 10000,
    "7k": 7000,
    "14k": 14000,
    "20k": 20000,
    "40koff": 40000,
    "40k": 40000,
    "80koff": 80000,
    "50k": 50000,
    "100koff": 100000,
}


# =========================================================
# GIÁ HIỂN THỊ TRÊN DISCORD
# =========================================================

DISPLAY_PRICE = {
    # VALORANT TỪNG RANK (GÓI THƯỜNG)
    "valo_unranked": "10k",
    "valo_iron": "10k",
    "valo_bronze": "12k",
    "valo_silver": "15k",
    "valo_gold": "20k",
    "valo_platinum": "25k",
    "valo_diamond": "35k",
    "valo_ascendant": "50k",
    "valo_immortal": "70k",
    "valo_radiant": "100k",

    # VALORANT TỪNG RANK (CHỦ OFF)
    "valo_unranked_off": "20k",
    "valo_iron_off": "20k",
    "valo_bronze_off": "24k",
    "valo_silver_off": "30k",
    "valo_gold_off": "40k",
    "valo_platinum_off": "50k",
    "valo_diamond_off": "70k",
    "valo_ascendant_off": "100k",
    "valo_immortal_off": "140k",
    "valo_radiant_off": "200k",

    # CSGO 2
    "cs2_prime": "50k",

    # STEAM TIERS
    "steam_tier_1": "5k",
    "steam_tier_2": "15k",
    "steam_tier_3": "25k",
    "pubg_plus": "50k",

    # Legacy fallbacks
    "valo_iron_gold": "10k",
    "valo_gold_plat": "15k",
    "valo_plat_dia": "25k",
    "valo_dia_imt": "35k",
    "valo_iron_gold_off": "20k",
    "valo_gold_plat_off": "30k",
    "valo_plat_dia_off": "50k",
    "valo_dia_imt_off": "70k",
    "5k": "5k",
    "10k": "10k",
    "7k": "7k",
    "14k": "14k",
    "20k": "20k",
    "40koff": "40k",
    "40k": "40k",
    "80koff": "80k",
    "50k": "50k",
    "100koff": "100k",
}


# =========================================================
# TÊN LOẠI TÀI KHOẢN
# =========================================================

ACCOUNT_TYPE_NAME = {
    # VALORANT TỪNG RANK (GÓI THƯỜNG)
    "valo_unranked": "Unranked",
    "valo_iron": "Iron",
    "valo_bronze": "Bronze",
    "valo_silver": "Silver",
    "valo_gold": "Gold",
    "valo_platinum": "Platinum",
    "valo_diamond": "Diamond",
    "valo_ascendant": "Ascendant",
    "valo_immortal": "Immortal",
    "valo_radiant": "Radiant",

    # VALORANT TỪNG RANK (CHỦ OFF)
    "valo_unranked_off": "Unranked Chủ Off",
    "valo_iron_off": "Iron Chủ Off",
    "valo_bronze_off": "Bronze Chủ Off",
    "valo_silver_off": "Silver Chủ Off",
    "valo_gold_off": "Gold Chủ Off",
    "valo_platinum_off": "Platinum Chủ Off",
    "valo_diamond_off": "Diamond Chủ Off",
    "valo_ascendant_off": "Ascendant Chủ Off",
    "valo_immortal_off": "Immortal Chủ Off",
    "valo_radiant_off": "Radiant Chủ Off",

    # CSGO 2
    "cs2_prime": "CSGO 2 Prime (Chơi được Rank)",

    # STEAM TIERS
    "steam_tier_1": "Steam (0 - 10 Games)",
    "steam_tier_2": "Steam (11 - 40 Games)",
    "steam_tier_3": "Steam (41+ Games)",
    "pubg_plus": "PUBG Plus (BATTLEGROUNDS Plus)",

    # Legacy fallbacks
    "valo_iron_gold": "Iron - Bronze - Silver - Gold",
    "valo_gold_plat": "Gold - Platinum",
    "valo_plat_dia": "Platinum - Diamond",
    "valo_dia_imt": "Diamond - Ascendant - Immortal",
    "valo_iron_gold_off": "Iron - Bronze - Silver - Gold Chủ Off",
    "valo_gold_plat_off": "Gold - Platinum Chủ Off",
    "valo_plat_dia_off": "Platinum - Diamond Chủ Off",
    "valo_dia_imt_off": "Diamond - Ascendant - Immortal Chủ Off",
    "5k": "0 Skin",
    "10k": "0 Skin Chủ Off",
    "7k": "1 - 20 Skins",
    "14k": "1 - 20 Skins Chủ Off",
    "20k": "21 - 60 Skins",
    "40koff": "21 - 60 Skins Chủ Off",
    "40k": "61 - 100 Skins",
    "80koff": "61 - 100 Skins Chủ Off",
    "50k": "101 - 1000 Skins",
    "100koff": "101 - 1000 Skins Chủ Off",
}


# =========================================================
# MAPPING ID LOẠI ACC -> TÊN FILE .txt   (NGUỒN DUY NHẤT)
# =========================================================

ACCOUNT_FILES = {
    # VALORANT TỪNG RANK (GÓI THƯỜNG)
    "valo_unranked": "rank_unranked.txt",
    "valo_iron": "rank_iron.txt",
    "valo_bronze": "rank_bronze.txt",
    "valo_silver": "rank_silver.txt",
    "valo_gold": "rank_gold.txt",
    "valo_platinum": "rank_platinum.txt",
    "valo_diamond": "rank_diamond.txt",
    "valo_ascendant": "rank_ascendant.txt",
    "valo_immortal": "rank_immortal.txt",
    "valo_radiant": "rank_radiant.txt",

    # VALORANT TỪNG RANK (CHỦ OFF)
    "valo_unranked_off": "rank_unranked_off.txt",
    "valo_iron_off": "rank_iron_off.txt",
    "valo_bronze_off": "rank_bronze_off.txt",
    "valo_silver_off": "rank_silver_off.txt",
    "valo_gold_off": "rank_gold_off.txt",
    "valo_platinum_off": "rank_platinum_off.txt",
    "valo_diamond_off": "rank_diamond_off.txt",
    "valo_ascendant_off": "rank_ascendant_off.txt",
    "valo_immortal_off": "rank_immortal_off.txt",
    "valo_radiant_off": "rank_radiant_off.txt",

    # CSGO 2
    "cs2_prime": "cs2_prime.txt",

    # STEAM TIERS
    "steam_tier_1": "steam.txt",
    "steam_tier_2": "steam.txt",
    "steam_tier_3": "steam.txt",
    "pubg_plus": "steam.txt",

    # Legacy fallbacks
    "valo_iron_gold": "rank_iron.txt",
    "valo_gold_plat": "rank_gold.txt",
    "valo_plat_dia": "rank_platinum.txt",
    "valo_dia_imt": "rank_diamond.txt",
    "valo_iron_gold_off": "rank_iron_off.txt",
    "valo_gold_plat_off": "rank_gold_off.txt",
    "valo_plat_dia_off": "rank_platinum_off.txt",
    "valo_dia_imt_off": "rank_diamond_off.txt",
    "5k": "5k.txt",
    "10k": "10koff.txt",
    "7k": "7k.txt",
    "14k": "14koff.txt",
    "20k": "20k.txt",
    "40koff": "40koff.txt",
    "40k": "40k.txt",
    "80koff": "80koff.txt",
    "50k": "50k.txt",
    "100koff": "100koff.txt",
}


def get_account_file_path(account_type: str):
    """
    Trả về đường dẫn tuyệt đối tới file chứa acc của loại `account_type`.
    Trả về None nếu loại acc không tồn tại.

    Dùng đường dẫn tuyệt đối nên không phụ thuộc thư mục chạy bot.
    """
    filename = ACCOUNT_FILES.get(account_type)

    if filename is None:
        return None

    return os.path.join(ACCOUNT_FOLDER, filename)


# =========================================================
# DANH SÁCH GAME HỖ TRỢ
# =========================================================

GAMES = [
    ("Valorant", "valorant", get_game_emoji("valorant"), "Acc Valorant Iron, Bronze, Silver, Gold, Plat, Dia, Asc, Imt, Radiant..."),
    ("CSGO 2", "csgo2", get_game_emoji("csgo2"), "Acc CSGO 2 Prime (Chơi được Rank)..."),
    ("Game Steam", "steam", get_game_emoji("steam"), "Acc Game Steam tự chọn game, giá theo số game..."),
]


# =========================================================
# DANH SÁCH TÀI KHOẢN THEO GAME
# =========================================================

VALORANT_CHOICES = [
    # Gói thường
    ("Unranked", "valo_unranked", get_account_file_path("valo_unranked"), 0x7F8C8D),
    ("Iron", "valo_iron", get_account_file_path("valo_iron"), 0x6C7A89),
    ("Bronze", "valo_bronze", get_account_file_path("valo_bronze"), 0xA0744B),
    ("Silver", "valo_silver", get_account_file_path("valo_silver"), 0xBDC3C7),
    ("Gold", "valo_gold", get_account_file_path("valo_gold"), 0xF6C744),
    ("Platinum", "valo_platinum", get_account_file_path("valo_platinum"), 0x45A6B8),
    ("Diamond", "valo_diamond", get_account_file_path("valo_diamond"), 0xB36CEB),
    ("Ascendant", "valo_ascendant", get_account_file_path("valo_ascendant"), 0x1ABC9C),
    ("Immortal", "valo_immortal", get_account_file_path("valo_immortal"), 0xE74C3C),
    ("Radiant", "valo_radiant", get_account_file_path("valo_radiant"), 0xFFF099),

    # Gói Chủ Off (x2 giá - Bảo hành 5 giờ)
    ("Unranked Chủ Off", "valo_unranked_off", get_account_file_path("valo_unranked_off"), 0x7F8C8D),
    ("Iron Chủ Off", "valo_iron_off", get_account_file_path("valo_iron_off"), 0x6C7A89),
    ("Bronze Chủ Off", "valo_bronze_off", get_account_file_path("valo_bronze_off"), 0xA0744B),
    ("Silver Chủ Off", "valo_silver_off", get_account_file_path("valo_silver_off"), 0xBDC3C7),
    ("Gold Chủ Off", "valo_gold_off", get_account_file_path("valo_gold_off"), 0xF6C744),
    ("Platinum Chủ Off", "valo_platinum_off", get_account_file_path("valo_platinum_off"), 0x45A6B8),
    ("Diamond Chủ Off", "valo_diamond_off", get_account_file_path("valo_diamond_off"), 0xB36CEB),
    ("Ascendant Chủ Off", "valo_ascendant_off", get_account_file_path("valo_ascendant_off"), 0x1ABC9C),
    ("Immortal Chủ Off", "valo_immortal_off", get_account_file_path("valo_immortal_off"), 0xE74C3C),
    ("Radiant Chủ Off", "valo_radiant_off", get_account_file_path("valo_radiant_off"), 0xFFF099),
]

CSGO2_CHOICES = [
    (
        "ACC CSGO 2 Prime (Chơi được Rank)",
        "cs2_prime",
        get_account_file_path("cs2_prime"),
        0xDE9B35
    ),
]

STEAM_CHOICES = [
    (
        "ACC Steam (0 - 10 Games)",
        "steam_tier_1",
        get_account_file_path("steam_tier_1"),
        0x1B2838
    ),
    (
        "ACC Steam (11 - 40 Games)",
        "steam_tier_2",
        get_account_file_path("steam_tier_2"),
        0x1B2838
    ),
    (
        "ACC Steam (41+ Games)",
        "steam_tier_3",
        get_account_file_path("steam_tier_3"),
        0x1B2838
    ),
]

GAME_CHOICES = {
    "valorant": VALORANT_CHOICES,
    "csgo2": CSGO2_CHOICES,
    "steam": STEAM_CHOICES,
}

ACCOUNT_CHOICES = VALORANT_CHOICES + CSGO2_CHOICES + STEAM_CHOICES


# =========================================================
# QUẢN LÝ GIÁ TỰ ĐỘNG QUA FILE prices.json
# =========================================================
PRICES_FILE = os.path.join(ROOT_DIR, "prices.json")

def load_prices_from_file():
    """Tải giá từ file prices.json nếu có, cập nhật PRICE_MAP & DISPLAY_PRICE."""
    if not os.path.exists(PRICES_FILE):
        save_prices_to_file()
        return

    try:
        with open(PRICES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for k, v in data.items():
                if k.startswith("_"):
                    continue
                try:
                    price_val = int(v)
                    PRICE_MAP[k] = price_val
                    if price_val >= 1000 and price_val % 1000 == 0:
                        DISPLAY_PRICE[k] = f"{price_val // 1000}k"
                    else:
                        DISPLAY_PRICE[k] = f"{price_val:,}đ"
                except (ValueError, TypeError):
                    pass
    except Exception as e:
        print(f"[WARN] Lỗi khi đọc prices.json: {e}")

    try:
        from utils.steam_storage import sync_steam_tiers
        sync_steam_tiers()
    except (ImportError, Exception):
        pass

def save_prices_to_file():
    """Lưu toàn bộ giá ra file prices.json để người dùng dễ sửa bằng Notepad."""
    data = {
        "_huong_dan": "Sửa số tiền (VNĐ) tương ứng bên dưới rồi bấm Ctrl + S để lưu lại. Bot sẽ tự nhận giá mới mà không cần đụng vào code!",
        "valo_unranked": PRICE_MAP.get("valo_unranked", 10000),
        "valo_iron": PRICE_MAP.get("valo_iron", 10000),
        "valo_bronze": PRICE_MAP.get("valo_bronze", 12000),
        "valo_silver": PRICE_MAP.get("valo_silver", 15000),
        "valo_gold": PRICE_MAP.get("valo_gold", 20000),
        "valo_platinum": PRICE_MAP.get("valo_platinum", 25000),
        "valo_diamond": PRICE_MAP.get("valo_diamond", 35000),
        "valo_ascendant": PRICE_MAP.get("valo_ascendant", 50000),
        "valo_immortal": PRICE_MAP.get("valo_immortal", 70000),
        "valo_radiant": PRICE_MAP.get("valo_radiant", 100000),
        "valo_unranked_off": PRICE_MAP.get("valo_unranked_off", 20000),
        "valo_iron_off": PRICE_MAP.get("valo_iron_off", 20000),
        "valo_bronze_off": PRICE_MAP.get("valo_bronze_off", 24000),
        "valo_silver_off": PRICE_MAP.get("valo_silver_off", 30000),
        "valo_gold_off": PRICE_MAP.get("valo_gold_off", 40000),
        "valo_platinum_off": PRICE_MAP.get("valo_platinum_off", 50000),
        "valo_diamond_off": PRICE_MAP.get("valo_diamond_off", 70000),
        "valo_ascendant_off": PRICE_MAP.get("valo_ascendant_off", 100000),
        "valo_immortal_off": PRICE_MAP.get("valo_immortal_off", 140000),
        "valo_radiant_off": PRICE_MAP.get("valo_radiant_off", 200000),
        "cs2_prime": PRICE_MAP.get("cs2_prime", 50000),
        "steam_tier_1": PRICE_MAP.get("steam_tier_1", 5000),
        "steam_tier_2": PRICE_MAP.get("steam_tier_2", 15000),
        "steam_tier_3": PRICE_MAP.get("steam_tier_3", 25000),
        "pubg_plus": PRICE_MAP.get("pubg_plus", 50000),
    }
    try:
        with open(PRICES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARN] Lỗi khi lưu prices.json: {e}")

def update_single_price(key: str, price: int):
    """Cập nhật 1 mức giá và lưu ra file prices.json."""
    PRICE_MAP[key] = int(price)
    if price >= 1000 and price % 1000 == 0:
        DISPLAY_PRICE[key] = f"{price // 1000}k"
    else:
        DISPLAY_PRICE[key] = f"{price:,}đ"
    save_prices_to_file()
    try:
        from utils.steam_storage import sync_steam_tiers
        sync_steam_tiers()
    except (ImportError, Exception):
        pass

load_prices_from_file()
