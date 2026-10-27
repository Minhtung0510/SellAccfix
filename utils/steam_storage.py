import os
import re
import tempfile
from typing import Optional

from utils.constants import ROOT_DIR, PRICE_MAP, DISPLAY_PRICE

STEAM_ACCOUNTS_FILE = os.path.join(ROOT_DIR, "data", "steam.txt")

def sync_steam_tiers():
    """Đồng bộ giá từ PRICE_MAP vào STEAM_TIERS khi giá thay đổi."""
    from utils.constants import PRICE_MAP, DISPLAY_PRICE
    if "steam_tier_1" in STEAM_TIERS:
        STEAM_TIERS["steam_tier_1"]["price"] = PRICE_MAP.get("steam_tier_1", 5000)
        STEAM_TIERS["steam_tier_1"]["display_price"] = DISPLAY_PRICE.get("steam_tier_1", "5k")
    if "steam_tier_2" in STEAM_TIERS:
        STEAM_TIERS["steam_tier_2"]["price"] = PRICE_MAP.get("steam_tier_2", 15000)
        STEAM_TIERS["steam_tier_2"]["display_price"] = DISPLAY_PRICE.get("steam_tier_2", "15k")
    if "steam_tier_3" in STEAM_TIERS:
        STEAM_TIERS["steam_tier_3"]["price"] = PRICE_MAP.get("steam_tier_3", 25000)
        STEAM_TIERS["steam_tier_3"]["display_price"] = DISPLAY_PRICE.get("steam_tier_3", "25k")
    if "pubg_plus" in STEAM_TIERS:
        STEAM_TIERS["pubg_plus"]["price"] = PRICE_MAP.get("pubg_plus", 50000)
        STEAM_TIERS["pubg_plus"]["display_price"] = DISPLAY_PRICE.get("pubg_plus", "50k")


STEAM_TIERS = {
    "steam_tier_1": {
        "id": "steam_tier_1",
        "name": "0 - 10 Games",
        "min_games": 0,
        "max_games": 10,
        "price": PRICE_MAP.get("steam_tier_1", 5000),
        "display_price": DISPLAY_PRICE.get("steam_tier_1", "5k"),
        "emoji": "🟢",
        "badge": "0-10 Games",
        "description": "Acc từ 0 - 10 games • Tiết kiệm nhất",
    },
    "steam_tier_2": {
        "id": "steam_tier_2",
        "name": "11 - 40 Games",
        "min_games": 11,
        "max_games": 40,
        "price": PRICE_MAP.get("steam_tier_2", 15000),
        "display_price": DISPLAY_PRICE.get("steam_tier_2", "15k"),
        "emoji": "🟡",
        "badge": "11-40 Games",
        "description": "Acc từ 11 - 40 games • Kèm nhiều game phụ",
    },
    "steam_tier_3": {
        "id": "steam_tier_3",
        "name": "41+ Games",
        "min_games": 41,
        "max_games": 999999,
        "price": PRICE_MAP.get("steam_tier_3", 25000),
        "display_price": DISPLAY_PRICE.get("steam_tier_3", "25k"),
        "emoji": "🔴",
        "badge": "41+ Games",
        "description": "Acc từ 41+ games • Kho game khủng",
    },
    "pubg_plus": {
        "id": "pubg_plus",
        "name": "PUBG Plus",
        "min_games": 0,
        "max_games": 999999,
        "price": PRICE_MAP.get("pubg_plus", 50000),
        "display_price": DISPLAY_PRICE.get("pubg_plus", "50k"),
        "emoji": "👑",
        "badge": "PUBG Plus",
        "description": "Acc PUBG đã nâng cấp gói BATTLEGROUNDS Plus (Bắn Rank)",
    },
}

GAME_ALIASES = {
    # Bắn súng / FPS
    "cs2": ["counter-strike 2", "counter strike 2", "cs:go", "counter-strike"],
    "csgo": ["counter-strike", "counter-strike 2", "cs:go"],
    "cs": ["counter-strike 2", "counter-strike"],
    "cod": ["call of duty"],
    "mw3": ["call of duty®: modern warfare® iii", "call of duty"],
    "mw2": ["call of duty®: modern warfare® ii", "call of duty"],
    "mw": ["call of duty"],
    "bo3": ["call of duty: black ops iii", "call of duty"],
    "warzone": ["call of duty"],
    "pubg": ["pubg: battlegrounds", "pubg", "battlegrounds"],
    "r6": ["rainbow six", "tom clancy's rainbow six siege"],
    "r6s": ["rainbow six", "tom clancy's rainbow six siege"],
    "rainbow six": ["rainbow six", "tom clancy's rainbow six siege"],
    "bf": ["battlefield"],
    "bf6": ["battlefield® 6", "battlefield"],
    "bf2042": ["battlefield® 2042", "battlefield"],
    "tarkov": ["escape from tarkov"],
    "l4d2": ["left 4 dead 2", "left 4 dead"],
    "l4d": ["left 4 dead 2", "left 4 dead"],
    "payday": ["payday 2"],

    # Hành động / Thế giới mở / AAA
    "gta": ["grand theft auto"],
    "gta5": ["grand theft auto v", "grand theft auto 5"],
    "gta 5": ["grand theft auto v", "grand theft auto 5"],
    "gtav": ["grand theft auto v", "grand theft auto 5"],
    "gta v": ["grand theft auto v", "grand theft auto 5"],
    "gta4": ["grand theft auto iv", "grand theft auto 4"],
    "gta 4": ["grand theft auto iv", "grand theft auto 4"],
    "gta iv": ["grand theft auto iv", "grand theft auto 4"],
    "rdr2": ["red dead redemption 2"],
    "rdr": ["red dead redemption 2"],
    "wukong": ["black myth: wukong"],
    "black myth": ["black myth: wukong"],
    "gow": ["god of war"],
    "cp2077": ["cyberpunk 2077"],
    "cyberpunk": ["cyberpunk 2077"],
    "witcher": ["the witcher 3", "the witcher"],
    "witcher3": ["the witcher 3", "the witcher"],
    "tlou": ["the last of us"],
    "tlou1": ["the last of us"],
    "pal": ["palworld"],
    "palworld": ["palworld"],
    "silksong": ["hollow knight: silksong", "hollow knight"],

    # Đua xe / Mô phỏng
    "forza": ["forza horizon"],
    "fh5": ["forza horizon 5"],
    "fh4": ["forza horizon 4"],
    "ets2": ["euro truck simulator 2"],
    "ets": ["euro truck simulator 2"],
    "ats": ["american truck simulator"],
    "beamng": ["beamng.drive"],
    "beam": ["beamng.drive"],

    # Thể thao
    "fifa": ["ea sports fc", "fifa"],
    "fc": ["ea sports fc"],
    "fc24": ["ea sports fc® 24", "ea sports fc 24"],
    "fc25": ["ea sports fc® 25", "ea sports fc 25"],
    "fc26": ["ea sports fc® 26", "ea sports fc 26"],
    "nba": ["nba 2k"],
    "nba2k": ["nba 2k"],

    # Kinh dị / Đối kháng
    "re": ["resident evil"],
    "re4": ["resident evil 4"],
    "re8": ["resident evil village"],
    "re7": ["resident evil 7"],
    "re2": ["resident evil 2"],
    "mk": ["mortal kombat"],
    "mk1": ["mortal kombat 1"],
    "mk11": ["mortal kombat 11"],
    "dbd": ["dead by daylight"],

    # Sinh tồn / Khác
    "ark": ["ark: survival evolved", "ark: survival of the fittest", "ark: survival ascended"],
    "pz": ["project zomboid"],
    "gmod": ["garry's mod"],
    "dota": ["dota 2"],
    "mh": ["monster hunter"],
    "mhr": ["monster hunter rise"],
}


def get_tier_for_count(count: int) -> str:
    """Xác định ID tier dựa trên số lượng game trong account."""
    if count <= 10:
        return "steam_tier_1"
    elif count <= 40:
        return "steam_tier_2"
    else:
        return "steam_tier_3"


def parse_steam_account_line(line: str) -> Optional[dict]:
    """
    Parse một dòng dữ liệu tài khoản Steam.
    Hỗ trợ cả format tiếng Anh lẫn tiếng Việt, có hoặc không có số giờ:
    - [349/77356] ✅ user:pass | SteamID: xxx | Lvl:0 | Games:3 | Wallet:$0.00 USD | Country:Pakistan | Games: [A, B] || CS2 Prime : Not Active ❌ || VAC : Clean ✅
    - ✅ user:pass | SteamID: xxx | Lvl: 14 | Ví: $18.50 USD | Quốc gia: US | Games (12): [CS2 (920.5h), PUBG (415h)] || CS2 Prime : Active ✅ || PUBG Plus : Active ✅
    - user:pass | SteamID: xxx | Lvl:0 | Games:3 | Wallet:0 | Country:Vietnam | Games: [A, B]
    """
    if not line:
        return None
    raw = line.strip()
    if not raw or raw.startswith("---"):
        return None

    # 1. Loại bỏ các prefix như [349/77356], ✅, ❌ ở đầu dòng
    clean = re.sub(r"^(?:\[\d+/\d+\]\s*)?[✅❌]?\s*", "", raw).strip()

    # 2. Tách phần credentials (user:pass) trước dấu |
    parts = clean.split(" | ")
    first_part = parts[0].strip().lstrip("✅❌ ").strip()
    if ":" not in first_part:
        return None

    # Có thể user:pass có nhiều dấu : nếu pass chứa :
    u_p = first_part.split(":", 1)
    username = u_p[0].strip().lstrip("✅❌ ").strip()
    password = u_p[1].strip()

    # 3. SteamID
    steam_id_m = re.search(r"SteamID:\s*(\d+)", clean, re.IGNORECASE)
    steam_id = steam_id_m.group(1) if steam_id_m else ""

    # 4. Level / Lvl
    lvl_m = re.search(r"(?:Lvl|Level):\s*(\d+)", clean, re.IGNORECASE)
    level = int(lvl_m.group(1)) if lvl_m else 0

    # 5. Danh sách game trong ngoặc vuông Games: [...] hoặc Games (12): [...]
    games_m = re.search(r"Games(?:\s*\(\d+\))?:\s*\[(.*?)\]", clean, re.IGNORECASE)
    games = []
    if games_m:
        raw_games = games_m.group(1).strip()
        if raw_games:
            games = [g.strip() for g in raw_games.split(",") if g.strip()]

    # 6. Số lượng game (từ Games (12): hoặc Games: 12 | hoặc đếm len(games))
    cnt_m = (
        re.search(r"Games\s*\((\d+)\):", clean, re.IGNORECASE)
        or re.search(r"Games:\s*(\d+)\s*\|", clean, re.IGNORECASE)
        or re.search(r"Games:\s*(\d+)", clean, re.IGNORECASE)
    )
    if cnt_m:
        game_count = int(cnt_m.group(1))
    else:
        game_count = len(games)

    # 7. Wallet / Ví / Số dư
    wallet_m = re.search(r"(?:Wallet|Ví|Số dư):\s*([^|]+)", clean, re.IGNORECASE)
    wallet = wallet_m.group(1).strip() if wallet_m else "0"

    # 8. Country / Quốc gia / Khu vực
    country_m = re.search(r"(?:Country|Quốc gia|Khu vực):\s*([^|]+)", clean, re.IGNORECASE)
    country = country_m.group(1).strip() if country_m else "Unknown"

    # 9. CS2 Prime
    prime_m = re.search(r"CS2 Prime\s*:\s*([^|]+)", clean, re.IGNORECASE)
    cs2_prime = prime_m.group(1).strip() if prime_m else ""

    # 10. PUBG Plus
    pubg_plus_m = re.search(r"PUBG Plus\s*:\s*([^|]+)", clean, re.IGNORECASE)
    if pubg_plus_m:
        val = pubg_plus_m.group(1).strip().lower()
        is_pubg_plus = "active" in val and "not active" not in val
    else:
        is_pubg_plus = any(
            ("plus" in g.lower() and ("pubg" in g.lower() or "battlegrounds" in g.lower()))
            for g in games
        ) or bool(re.search(r"BATTLEGROUNDS\s*Plus|PUBG\s*Plus", clean, re.IGNORECASE))

    # 11. VAC
    vac_m = re.search(r"VAC\s*:\s*([^|]+)", clean, re.IGNORECASE)
    vac = vac_m.group(1).strip() if vac_m else ""

    tier_id = get_tier_for_count(game_count)

    return {
        "raw_line": raw,
        "username": username,
        "password": password,
        "steam_id": steam_id,
        "level": level,
        "game_count": game_count,
        "wallet": wallet,
        "country": country,
        "games": games,
        "cs2_prime": cs2_prime,
        "is_pubg_plus": is_pubg_plus,
        "vac": vac,
        "tier_id": tier_id,
    }


def load_steam_accounts(file_path: Optional[str] = None) -> list[dict]:
    """Tải và parse tất cả tài khoản Steam từ file kho."""
    path = file_path or STEAM_ACCOUNTS_FILE
    if not os.path.exists(path):
        return []

    accounts = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parsed = parse_steam_account_line(line)
                if parsed:
                    accounts.append(parsed)
    except Exception as e:
        print(f"Lỗi khi đọc kho Steam từ {path}: {e}")
    return accounts


def get_total_steam_count(file_path: Optional[str] = None) -> int:
    """Trả về tổng số tài khoản Steam còn trong kho."""
    return len(load_steam_accounts(file_path))


def get_steam_tier_counts(file_path: Optional[str] = None) -> dict[str, int]:
    """Trả về số lượng acc theo từng tier trong toàn bộ kho."""
    accs = load_steam_accounts(file_path)
    counts = {"steam_tier_1": 0, "steam_tier_2": 0, "steam_tier_3": 0}
    for a in accs:
        t = a["tier_id"]
        if t in counts:
            counts[t] += 1
    return counts


def _account_matches_query(acc: dict, query_lower: str, alias_targets: list[str]) -> bool:
    """Kiểm tra acc có chứa game theo query hoặc alias hay không."""
    # 0. Nếu đang tìm kiếm CS2/CSGO -> LOẠI acc CS2 Prime Active (để dành bán riêng gói Prime 50k)
    is_cs2_search = any(k in query_lower for k in ("cs2", "csgo", "counter-strike", "counter strike", "cs:go")) or query_lower == "cs"
    if is_cs2_search:
        prime_status = str(acc.get("cs2_prime", "")).lower()
        if "active" in prime_status and "not active" not in prime_status:
            return False

    # 1. Nếu khách tìm cụ thể "pubg plus" -> Chỉ lấy acc có PUBG Plus
    if query_lower in ("pubg plus", "pubg+", "pubgplus"):
        return bool(acc.get("is_pubg_plus"))

    games_lower = [g.lower() for g in acc["games"]]

    # 2. Khớp trực tiếp query
    for g in games_lower:
        if query_lower in g:
            return True

    # 3. Khớp qua alias
    for target in alias_targets:
        for g in games_lower:
            if target in g:
                return True

    return False


def search_steam_accounts(game_query: str, file_path: Optional[str] = None) -> dict[str, list[dict]]:
    """
    Tìm kiếm tài khoản chứa game_query và gom nhóm theo tier.
    Trong MỖI tier, danh sách được sắp xếp TĂNG DẦN theo game_count
    để bot luôn ưu tiên giao acc ít game nhất (tối ưu nhất).
    """
    query = game_query.strip().lower()
    if not query:
        return {"steam_tier_1": [], "steam_tier_2": [], "steam_tier_3": []}

    alias_targets = GAME_ALIASES.get(query, [])

    all_accs = load_steam_accounts(file_path)
    results = {
        "steam_tier_1": [],
        "steam_tier_2": [],
        "steam_tier_3": [],
    }

    is_pubg_search = any(k in query for k in ("pubg", "battlegrounds"))
    if is_pubg_search:
        results["pubg_plus"] = []

    for acc in all_accs:
        if _account_matches_query(acc, query, alias_targets):
            if is_pubg_search and acc.get("is_pubg_plus"):
                results["pubg_plus"].append(acc)
            else:
                tier = acc["tier_id"]
                if tier in results:
                    results[tier].append(acc)

    # Sắp xếp từng tier theo số game tăng dần (tối ưu tài sản kho)
    for tier in results:
        results[tier].sort(key=lambda a: (a["game_count"], a["level"]))

    return results


def allocate_steam_accounts(
    game_query: str,
    tier_id: str,
    quantity: int,
    file_path: Optional[str] = None
) -> list[dict]:
    """
    Rút `quantity` tài khoản từ kho Steam thỏa mãn:
    1. Chứa game_query
    2. Thuộc tier_id
    3. Ưu tiên acc ít game nhất trước (đã sắp xếp ASC).
    Xóa tài khoản đã lấy khỏi file kho an toàn.
    Trả về danh sách dict tài khoản được cấp phát.
    """
    if quantity <= 0:
        return []

    path = file_path or STEAM_ACCOUNTS_FILE
    if not os.path.exists(path):
        return []

    query = game_query.strip().lower()
    alias_targets = GAME_ALIASES.get(query, [])

    # Đọc tất cả các dòng
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = [line.rstrip("\r\n") for line in f if line.strip() and not line.strip().startswith("---")]

    # Parse và lọc candidates
    candidates = []
    for line in lines:
        parsed = parse_steam_account_line(line)
        if not parsed:
            continue
        if tier_id == "pubg_plus":
            if parsed.get("is_pubg_plus") and _account_matches_query(parsed, query, alias_targets):
                candidates.append(parsed)
        elif parsed["tier_id"] == tier_id:
            # Nếu acc có PUBG Plus thì không xuất nhầm ở tier thường khi mua PUBG thường
            if "pubg" in query and parsed.get("is_pubg_plus"):
                continue
            if _account_matches_query(parsed, query, alias_targets):
                candidates.append(parsed)

    # Tối ưu: sắp xếp ít game nhất trước
    candidates.sort(key=lambda a: (a["game_count"], a["level"]))

    if len(candidates) < quantity:
        return []

    selected = candidates[:quantity]
    selected_raw_set = {s["raw_line"] for s in selected}

    # Ghi lại file kho không còn các acc đã chọn
    remaining_lines = [l for l in lines if l not in selected_raw_set]

    dir_name = os.path.dirname(path)
    fd, tmp_file = tempfile.mkstemp(dir=dir_name, prefix="steam_tmp_", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tf:
            for l in remaining_lines:
                tf.write(l + "\n")
        os.replace(tmp_file, path)
    except Exception as e:
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except OSError:
                pass
        raise e

    return selected
