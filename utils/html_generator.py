import re
import html
import json
import os
from datetime import datetime

CACHE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "valorant_skins_cache.json")
SKINS_CACHE = {}
if os.path.exists(CACHE_PATH):
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            SKINS_CACHE = json.load(f)
    except Exception as e:
        print(f"Lưu ý: Không đọc được file cache: {e}")

RANK_ICONS = {
    'UNRANKED': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/0/smallicon.png',
    'IRON 1': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/3/smallicon.png',
    'IRON 2': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/4/smallicon.png',
    'IRON 3': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/5/smallicon.png',
    'BRONZE 1': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/6/smallicon.png',
    'BRONZE 2': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/7/smallicon.png',
    'BRONZE 3': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/8/smallicon.png',
    'SILVER 1': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/9/smallicon.png',
    'SILVER 2': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/10/smallicon.png',
    'SILVER 3': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/11/smallicon.png',
    'GOLD 1': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/12/smallicon.png',
    'GOLD 2': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/13/smallicon.png',
    'GOLD 3': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/14/smallicon.png',
    'PLATINUM 1': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/15/smallicon.png',
    'PLATINUM 2': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/16/smallicon.png',
    'PLATINUM 3': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/17/smallicon.png',
    'DIAMOND 1': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/18/smallicon.png',
    'DIAMOND 2': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/19/smallicon.png',
    'DIAMOND 3': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/20/smallicon.png',
    'ASCENDANT 1': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/21/smallicon.png',
    'ASCENDANT 2': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/22/smallicon.png',
    'ASCENDANT 3': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/23/smallicon.png',
    'IMMORTAL 1': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/24/smallicon.png',
    'IMMORTAL 2': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/25/smallicon.png',
    'IMMORTAL 3': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/26/smallicon.png',
    'RADIANT': 'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04/27/smallicon.png',
}

def detect_weapon_type(name: str) -> str:
    n = name.lower()
    melee_keywords = ['knife', 'karambit', 'blade', 'sword', 'axe', 'dagger', 'mace', 'cane', 'bat', 'melee', 'arc', 'sparkswitch', 'scythe', 'anchor', 'claw', 'fan', 'kunai', 'hammer', 'whip', 'gauntlet']
    if any(k in n for k in melee_keywords):
        return 'Cận Chiến'
    for w in ['Vandal', 'Phantom', 'Operator', 'Sheriff', 'Spectre', 'Ghost', 'Classic', 'Marshal', 'Judge', 'Frenzy', 'Ares', 'Odin', 'Bulldog', 'Guardian', 'Stinger', 'Bucky', 'Shorty', 'Outlaw']:
        if w.lower() in n:
            return w
    return 'Khác'

def get_rank_icon(rank_str: str) -> str:
    r = rank_str.upper()
    for k, v in RANK_ICONS.items():
        if k in r:
            return v
    return RANK_ICONS['UNRANKED']

def parse_checker_text(raw_text: str):
    """
    Bóc tách dữ liệu từ text xuất ra của tool check Valorant thành danh sách dict.
    Hỗ trợ định dạng phân cách bằng '---------------------------' hoặc từng block.
    """
    if not raw_text or not raw_text.strip():
        return []

    raw_blocks = re.split(r'-{10,}', raw_text)
    accounts = []

    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue

        def get_field(pattern, default=""):
            m = re.search(pattern, block, re.IGNORECASE | re.MULTILINE)
            return m.group(1).strip() if m else default

        username = get_field(r"^\s*Username:\s*([^\r\n]+)")
        password = get_field(r"^\s*Password:\s*([^\r\n]+)")

        if not username and ":" in block and "\n" not in block:
            parts = block.split(":", 1)
            username = parts[0].strip()
            password = parts[1].strip()

        if not username:
            continue

        riot_id = get_field(r"^\s*Riot ID:\s*([^\r\n]+)", username)
        region = get_field(r"^\s*Region:\s*([^\r\n]+)", "NA")
        level = get_field(r"^\s*Level:\s*(\d+)", "1")
        vp = get_field(r"^\s*Valorant Points:\s*(\d+)", "0")
        rp = get_field(r"^\s*Radianite Points:\s*(\d+)", "0")
        kc = get_field(r"^\s*Kingdom Credits:\s*(\d+)", "0")
        email_verified = get_field(r"^\s*Email Verified:\s*([^\r\n]+)", "False").lower() == "true"
        phone_verified = get_field(r"^\s*Phone Verified:\s*([^\r\n]+)", "False").lower() == "true"
        current_rank = get_field(r"^\s*Current Rank:\s*([^\r\n]+)", "Unranked")
        peak_rank = get_field(r"^\s*Peak Rank:\s*([^\r\n]+)", current_rank or "Unranked")
        last_game = get_field(r"^\s*Last Game Date:\s*([^\r\n]+)", "N/A")

        # Bóc danh sách Knives (Dao) - chỉ lấy các dòng bắt đầu bằng dấu gạch ngang '-' và không chứa nhãn ':'
        knives_match = re.search(r"Knives\s*\(\d+\):([\s\S]*?)(?:Current Rank|Peak Rank|Previous|Penalty|Last Game|\Z)", block, re.IGNORECASE)
        raw_knives = []
        if knives_match:
            lines = knives_match.group(1).strip().split("\n")
            for line in lines:
                line_str = line.strip()
                if line_str.startswith("-"):
                    clean_line = re.sub(r"^-\s*", "", line_str).strip()
                    if clean_line and clean_line != "-" and ":" not in clean_line:
                        raw_knives.append(clean_line)

        clean_knives = []
        for k in raw_knives:
            base_k = re.sub(r"\s+Level\s+\d+", "", k, flags=re.IGNORECASE).strip()
            if base_k and base_k not in clean_knives:
                clean_knives.append(base_k)

        # Bóc danh sách Weapons (Súng) - chỉ lấy các dòng bắt đầu bằng dấu gạch ngang '-' và không chứa nhãn ':'
        weapons_match = re.search(r"Weapons\s*\(\d+\):([\s\S]*?)(?:Knives|\Z)", block, re.IGNORECASE)
        clean_weapons = []
        if weapons_match:
            lines = weapons_match.group(1).strip().split("\n")
            seen = set()
            for line in lines:
                line_str = line.strip()
                if line_str.startswith("-"):
                    clean_line = re.sub(r"^-\s*", "", line_str).strip()
                    if not clean_line or clean_line == "-" or ":" in clean_line:
                        continue
                    base_name = re.sub(r"\s+Level\s+\d+", "", clean_line, flags=re.IGNORECASE).strip()
                    if base_name and base_name not in seen:
                        seen.add(base_name)
                        clean_weapons.append(base_name)

        # Gộp tất cả skin (Dao + Súng) và tra cứu hình ảnh từ cache
        all_skin_items = []
        tier_counts = {"Ultra": 0, "Exclusive": 0, "Premium": 0, "Deluxe": 0, "Select": 0, "Standard": 0}

        for k in clean_knives:
            ck = re.sub(r'[^a-z0-9]', '', k.lower())
            cached = SKINS_CACHE.get(ck)
            if cached:
                t = cached["tier"]
                tier_counts[t] = tier_counts.get(t, 0) + 1
                all_skin_items.append({
                    "name": cached["name"],
                    "icon": cached["icon"],
                    "tier": t,
                    "tierColor": cached["tierColor"],
                    "tierOrder": cached["tierOrder"],
                    "price": cached["price"],
                    "weaponType": "Cận Chiến"
                })
            else:
                tier_counts["Exclusive"] += 1
                all_skin_items.append({
                    "name": k,
                    "icon": "",
                    "tier": "Exclusive",
                    "tierColor": "#f5955b",
                    "tierOrder": 1,
                    "price": 2175,
                    "weaponType": "Cận Chiến"
                })

        for w in clean_weapons:
            cw = re.sub(r'[^a-z0-9]', '', w.lower())
            cached = SKINS_CACHE.get(cw)
            wtype = detect_weapon_type(w)
            if cached:
                t = cached["tier"]
                tier_counts[t] = tier_counts.get(t, 0) + 1
                all_skin_items.append({
                    "name": cached["name"],
                    "icon": cached["icon"],
                    "tier": t,
                    "tierColor": cached["tierColor"],
                    "tierOrder": cached["tierOrder"],
                    "price": cached["price"],
                    "weaponType": wtype
                })
            else:
                tier_counts["Standard"] += 1
                all_skin_items.append({
                    "name": w,
                    "icon": "",
                    "tier": "Standard",
                    "tierColor": "#8b9bb4",
                    "tierOrder": 5,
                    "price": 0,
                    "weaponType": wtype
                })

        all_skin_items.sort(key=lambda x: (x["tierOrder"], x["name"]))

        try:
            vp_int = int(vp)
        except ValueError:
            vp_int = 0
        try:
            rp_int = int(rp)
        except ValueError:
            rp_int = 0

        if "#" in riot_id:
            r_name, r_tag = riot_id.split("#", 1)
            r_tag = "#" + r_tag
        else:
            r_name = riot_id
            r_tag = "#1234"

        clean_rank = peak_rank.split("(")[0].strip() if "(" in peak_rank else peak_rank.strip()

        accounts.append({
            "username": username,
            "password": password,
            "riot_name": r_name,
            "riot_tag": r_tag,
            "riot_id": riot_id,
            "region": region,
            "level": level,
            "vp": vp_int,
            "rp": rp_int,
            "kc": kc,
            "email_verified": email_verified,
            "phone_verified": phone_verified,
            "current_rank": current_rank,
            "peak_rank": clean_rank,
            "rank_icon": get_rank_icon(clean_rank or current_rank),
            "last_game": last_game,
            "knives_count": len(clean_knives),
            "weapons_count": len(clean_weapons),
            "total_skins": len(all_skin_items),
            "tier_counts": tier_counts,
            "skins": all_skin_items
        })

    return accounts


HTML_APP_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>__SHOP_NAME__ - Tra Cứu Kho Skin Đơn Hàng #__ORDER_CODE__</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com">
    <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-body: #0a0d14;
            --bg-card: #121721;
            --bg-card-hover: #19202e;
            --border-subtle: rgba(255, 255, 255, 0.07);
            --border-highlight: rgba(255, 255, 255, 0.16);
            --primary-red: #ff4655;
            --primary-red-glow: rgba(255, 70, 85, 0.4);
            --text-main: #f3f5f8;
            --text-muted: #8492a6;
            --accent-green: #00d26a;
            --badge-green-bg: rgba(0, 210, 106, 0.12);
            --badge-green-border: rgba(0, 210, 106, 0.35);

            /* Valorant Tier Colors */
            --tier-ultra: #fad663;
            --tier-exclusive: #f5955b;
            --tier-premium: #d1548d;
            --tier-deluxe: #009587;
            --tier-select: #5a9fe2;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
        body { background-color: var(--bg-body); color: var(--text-main); line-height: 1.4; padding: 20px; min-height: 100vh; }
        .app-container { max-width: 1240px; margin: 0 auto; }

        /* Top Bar */
        .top-nav {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border-subtle);
            flex-wrap: wrap;
            gap: 12px;
        }
        .header-title { font-size: 15px; font-weight: 500; color: #a4b3c6; }
        .header-title b { color: white; font-weight: 700; }
        .header-actions { display: flex; gap: 10px; align-items: center; }

        .btn-action {
            background: var(--bg-card);
            color: #d8e2ef;
            border: 1px solid var(--border-subtle);
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .btn-action:hover {
            background: var(--bg-card-hover);
            border-color: var(--border-highlight);
            color: white;
            transform: translateY(-1px);
        }
        .btn-primary {
            background: var(--primary-red);
            border-color: var(--primary-red);
            color: white;
        }
        .btn-primary:hover {
            background: #e03240;
            box-shadow: 0 0 15px var(--primary-red-glow);
        }

        /* VIEW 1: ACCOUNTS LIST GRID (Hình 1) */
        #viewAccountsList { display: block; }
        .accounts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 18px;
        }
        .acc-summary-card {
            background: var(--bg-card);
            border: 1px solid var(--border-subtle);
            border-radius: 14px;
            padding: 18px;
            display: flex;
            flex-direction: column;
            gap: 14px;
            transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
            position: relative;
        }
        .acc-summary-card:hover {
            border-color: rgba(255, 70, 85, 0.45);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
            transform: translateY(-2px);
        }

        .acc-card-top {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .v-avatar {
            width: 44px;
            height: 44px;
            background: #0f121a;
            border: 1px solid var(--border-subtle);
            border-radius: 10px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }
        .v-avatar svg { width: 22px; height: 18px; fill: var(--primary-red); }
        .v-avatar-lvl { font-size: 10px; font-weight: 700; color: #8e9db3; margin-top: 2px; }

        .acc-name-box { flex: 1; min-width: 0; }
        .acc-riot-name { font-weight: 700; font-size: 16px; color: white; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .acc-riot-tag { font-size: 12px; color: var(--text-muted); }

        .acc-rank-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--border-subtle);
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            color: #d1d9e6;
            text-transform: uppercase;
        }
        .acc-rank-pill img { width: 16px; height: 16px; object-fit: contain; }

        /* Currency VP & RP Row */
        .currency-row {
            display: flex;
            background: rgba(0, 0, 0, 0.35);
            border-radius: 8px;
            padding: 8px 12px;
            justify-content: space-around;
            border: 1px solid rgba(255, 255, 255, 0.04);
        }
        .cur-item { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; }
        .cur-label { color: #8492a6; font-size: 11px; }
        .cur-vp { color: #ff5569; font-weight: 700; }
        .cur-rp { color: #ffd13b; font-weight: 700; }

        /* Total Skins & Tier Breakdown */
        .skins-count-box {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-subtle);
            border-radius: 8px;
            padding: 10px 12px;
        }
        .skins-count-header { font-size: 11px; font-weight: 700; color: #8492a6; margin-bottom: 6px; text-transform: uppercase; }
        .skins-count-header b { color: white; font-size: 13px; }
        .tier-icons-row {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 12px;
            font-weight: 700;
        }
        .tier-icon-item { display: flex; align-items: center; gap: 4px; }
        .tier-dot { width: 10px; height: 10px; border-radius: 2px; }
        .dot-ultra { background: var(--tier-ultra); transform: rotate(45deg); }
        .dot-exclusive { background: var(--tier-exclusive); transform: rotate(45deg); }
        .dot-premium { background: var(--tier-premium); border-radius: 0; clip-path: polygon(50% 100%, 0 0, 100% 0); }
        .dot-deluxe { background: var(--tier-deluxe); transform: rotate(45deg); }
        .dot-select { background: var(--tier-select); border-radius: 50%; }

        /* Meta details */
        .acc-meta-row {
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            color: #79889b;
        }
        .region-tag { font-weight: 700; color: #adbccc; }

        .acc-status-line { font-size: 11px; color: #6d7c8f; display: flex; align-items: center; gap: 6px; }
        .status-badge {
            font-size: 10px;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 4px;
            display: inline-block;
        }
        .status-safe { background: var(--badge-green-bg); color: var(--accent-green); border: 1px solid var(--badge-green-border); }

        .btn-view-skin {
            width: 100%;
            background: #171f2c;
            border: 1px solid rgba(255, 255, 255, 0.08);
            color: #e2e8f0;
            padding: 10px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            margin-top: auto;
        }
        .btn-view-skin:hover {
            background: var(--primary-red);
            border-color: var(--primary-red);
            color: white;
            box-shadow: 0 0 15px var(--primary-red-glow);
        }

        /* VIEW 2: INVENTORY DETAIL (Hình 2) */
        #viewInventoryDetail { display: none; }

        .back-nav-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .btn-back {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-subtle);
            color: #cdd6e3;
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.15s;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .btn-back:hover { background: rgba(255, 255, 255, 0.12); color: white; }

        /* Detail Header Banner */
        .detail-header-card {
            background: #131822;
            border: 1px solid var(--border-subtle);
            border-radius: 12px;
            padding: 16px 20px;
            margin-bottom: 20px;
        }
        .detail-top-info {
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 12px;
            padding-bottom: 14px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            margin-bottom: 14px;
        }
        .detail-user-group { display: flex; align-items: center; gap: 10px; }
        .detail-rank-avatar { width: 28px; height: 28px; object-fit: contain; }
        .detail-username { font-size: 18px; font-weight: 700; color: white; }
        .detail-scan-info { font-size: 12px; color: #7f8fa4; }

        .detail-banner-stats {
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 16px;
        }
        .rank-stat-item {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 13px;
            font-weight: 600;
        }
        .rank-stat-item img { width: 32px; height: 32px; object-fit: contain; }
        .rank-text-group { display: flex; flex-direction: column; }
        .rank-sub { font-size: 10px; color: #8492a6; text-transform: uppercase; }
        .rank-main { font-size: 14px; font-weight: 700; color: #e5ecf5; }

        .skins-stat-middle { display: flex; align-items: center; gap: 12px; }
        .skins-count-big { font-family: 'Rajdhani', sans-serif; font-size: 20px; font-weight: 700; color: white; }
        .tier-pills-row { display: flex; gap: 6px; }
        .tier-pill-box {
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid var(--border-subtle);
        }

        .lvl-badge-box {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--border-subtle);
            border-radius: 8px;
            padding: 6px 14px;
            font-size: 13px;
            font-weight: 700;
            color: #d1d9e6;
        }
        .lvl-badge-box b { color: var(--primary-red); }

        /* Navigation Tabs: [ℹ️ THÔNG TIN] [🎒 KHO ĐỒ] */
        .main-tabs-nav {
            display: flex;
            gap: 8px;
            margin-bottom: 20px;
        }
        .main-tab-btn {
            background: transparent;
            border: 1px solid transparent;
            color: #8e9cb0;
            padding: 8px 18px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .main-tab-btn:hover { color: white; }
        .main-tab-btn.active {
            background: #00b05b;
            color: #ffffff;
            font-weight: 700;
            border-radius: 20px;
            box-shadow: 0 4px 14px rgba(0, 176, 91, 0.35);
        }

        /* Sub-controls: Search & Weapon Type Filter Pills */
        .inventory-controls {
            display: flex;
            flex-direction: column;
            gap: 14px;
            margin-bottom: 22px;
        }
        .search-and-subtabs {
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }
        .inv-search-input {
            background: #111621;
            border: 1px solid var(--border-subtle);
            border-radius: 8px;
            padding: 9px 14px;
            color: white;
            font-size: 13px;
            min-width: 260px;
            outline: none;
            transition: border-color 0.2s;
        }
        .inv-search-input:focus { border-color: var(--accent-green); }

        .weapon-pills-row {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            align-items: center;
        }
        .weapon-pill {
            background: #131822;
            border: 1px solid var(--border-subtle);
            color: #8b99ac;
            padding: 5px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s;
        }
        .weapon-pill:hover { color: white; border-color: var(--border-highlight); }
        .weapon-pill.active {
            background: rgba(0, 210, 106, 0.15);
            border-color: rgba(0, 210, 106, 0.5);
            color: #00d26a;
            font-weight: 700;
        }

        .tier-select-dropdown {
            margin-left: auto;
            background: #111621;
            border: 1px solid var(--border-subtle);
            color: #b5c3d4;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            outline: none;
            cursor: pointer;
        }

        /* SKINS GRID BY TIER */
        .tier-group-section {
            margin-bottom: 28px;
        }
        .tier-group-title {
            font-size: 14px;
            font-weight: 700;
            color: #ced6e2;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .tier-group-title span { font-weight: 500; color: #738295; font-size: 12px; }

        .skins-cards-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
            gap: 14px;
        }

        .skin-item-card {
            background: #131822;
            border: 1px solid var(--border-subtle);
            border-radius: 10px;
            padding: 12px;
            display: flex;
            flex-direction: column;
            position: relative;
            overflow: hidden;
            transition: all 0.2s;
        }
        .skin-item-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.4);
        }

        .skin-item-card.tier-Ultra { border-color: rgba(250, 214, 99, 0.4); }
        .skin-item-card.tier-Ultra:hover { border-color: var(--tier-ultra); box-shadow: 0 0 16px rgba(250, 214, 99, 0.3); }

        .skin-item-card.tier-Exclusive { border-color: rgba(245, 149, 91, 0.4); }
        .skin-item-card.tier-Exclusive:hover { border-color: var(--tier-exclusive); box-shadow: 0 0 16px rgba(245, 149, 91, 0.3); }

        .skin-item-card.tier-Premium { border-color: rgba(209, 84, 141, 0.4); }
        .skin-item-card.tier-Premium:hover { border-color: var(--tier-premium); box-shadow: 0 0 16px rgba(209, 84, 141, 0.3); }

        .skin-item-card.tier-Deluxe { border-color: rgba(0, 149, 135, 0.35); }
        .skin-item-card.tier-Deluxe:hover { border-color: var(--tier-deluxe); box-shadow: 0 0 14px rgba(0, 149, 135, 0.25); }

        .skin-item-card.tier-Select { border-color: rgba(90, 159, 226, 0.3); }
        .skin-item-card.tier-Select:hover { border-color: var(--tier-select); box-shadow: 0 0 14px rgba(90, 159, 226, 0.2); }

        .skin-tier-tag {
            align-self: flex-start;
            font-size: 10px;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 4px;
            border: 1px solid transparent;
            margin-bottom: 8px;
        }
        .tag-Ultra { color: var(--tier-ultra); border-color: var(--tier-ultra); background: rgba(250, 214, 99, 0.1); }
        .tag-Exclusive { color: var(--tier-exclusive); border-color: var(--tier-exclusive); background: rgba(245, 149, 91, 0.1); }
        .tag-Premium { color: var(--tier-premium); border-color: var(--tier-premium); background: rgba(209, 84, 141, 0.1); }
        .tag-Deluxe { color: #00d5c0; border-color: #00d5c0; background: rgba(0, 149, 135, 0.1); }
        .tag-Select { color: var(--tier-select); border-color: var(--tier-select); background: rgba(90, 159, 226, 0.1); }
        .tag-Standard { color: #8e9cb0; border-color: #8e9cb0; background: rgba(142, 156, 176, 0.08); }

        .skin-img-wrapper {
            height: 90px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 6px 0 10px;
        }
        .skin-img-wrapper img {
            max-width: 95%;
            max-height: 85px;
            object-fit: contain;
            filter: drop-shadow(0 4px 10px rgba(0, 0, 0, 0.6));
            transition: transform 0.2s;
        }
        .skin-item-card:hover .skin-img-wrapper img { transform: scale(1.05); }

        .skin-name-label {
            font-size: 13px;
            font-weight: 700;
            color: #f1f4f8;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .skin-bottom-meta {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 4px;
            font-size: 11px;
            color: #7b8b9f;
        }
        .skin-vp-price { color: #a4b3c6; font-weight: 600; }

        /* TAB: [ℹ️ THÔNG TIN ĐĂNG NHẬP] */
        #tabContentInfo { display: none; }
        .info-card-panel {
            background: #131822;
            border: 1px solid var(--border-subtle);
            border-radius: 12px;
            padding: 24px;
            max-width: 750px;
        }
        .credential-row {
            display: flex;
            gap: 14px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .cred-item-box {
            flex: 1;
            min-width: 220px;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border-subtle);
            border-radius: 8px;
            padding: 12px 16px;
        }
        .cred-label { font-size: 11px; color: #8492a6; text-transform: uppercase; font-weight: 700; margin-bottom: 4px; }
        .cred-val-row { display: flex; align-items: center; justify-content: space-between; }
        .cred-val { font-family: monospace; font-size: 15px; font-weight: 700; color: white; }

        .toast {
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: #00d26a;
            color: #0c1a12;
            font-weight: 700;
            font-size: 13px;
            padding: 10px 18px;
            border-radius: 8px;
            box-shadow: 0 8px 24px rgba(0, 210, 106, 0.4);
            display: none;
            z-index: 9999;
        }
    </style>
</head>
<body>

<div class="app-container">

    <!-- VIEW 1: DANH SÁCH TÀI KHOẢN (GIỐNG HÌNH 1) -->
    <div id="viewAccountsList">
        <div class="top-nav">
            <div class="header-title">
                <b>__TOTAL_ACCS__ tài khoản</b> • Tìm trong kho skin của các lần quét đã lưu.
            </div>
            <div class="header-actions">
                <button class="btn-action btn-primary" onclick="copyAllCombos()">📋 Copy Toàn Bộ TK:MK</button>
            </div>
        </div>

        <div class="accounts-grid" id="accountsGridContainer">
            <!-- Cards will be populated by JavaScript -->
        </div>
    </div>

    <!-- VIEW 2: CHI TIẾT KHO ĐỒ SKINS CỦA TÀI KHOẢN (GIỐNG HÌNH 2) -->
    <div id="viewInventoryDetail">
        <div class="back-nav-bar">
            <button class="btn-back" onclick="backToList()">← Quay lại danh sách tài khoản</button>
            <div style="font-size: 13px; color: #7f8fa4;">Đơn hàng: <b>#__ORDER_CODE__</b></div>
        </div>

        <div class="detail-header-card">
            <div class="detail-top-info">
                <div class="detail-user-group">
                    <img id="detailRankIconTop" class="detail-rank-avatar" src="" alt="rank">
                    <span id="detailRiotIdTop" class="detail-username">Yukiii#rtrd</span>
                    <span class="status-badge status-safe">KHÔNG CÓ HẠN CHẾ</span>
                </div>
                <div class="detail-scan-info">
                    REGION: <span id="detailRegionTop">AP</span> • LẦN QUÉT: <span id="detailScanDate">05/10/2026</span> • Dữ liệu tại thời điểm quét, chưa tự cập nhật.
                </div>
            </div>

            <div class="detail-banner-stats">
                <div class="rank-stat-item">
                    <img id="detailRankIconBanner" src="" alt="rank">
                    <div class="rank-text-group">
                        <span class="rank-sub">RANK • XEM LỊCH SỬ</span>
                        <span id="detailRankTextBanner" class="rank-main">ASCENDANT 1</span>
                    </div>
                </div>

                <div class="skins-stat-middle">
                    <span id="detailTotalSkinsBanner" class="skins-count-big">33 SKINS</span>
                    <div class="tier-pills-row" id="detailTierPillsBanner">
                        <!-- Populated by JS -->
                    </div>
                </div>

                <div class="lvl-badge-box">
                    CẤP ĐỘ <b id="detailLvlBanner">117</b>
                </div>
            </div>
        </div>

        <!-- Main Tabs -->
        <div class="main-tabs-nav">
            <button class="main-tab-btn" id="tabBtnInfo" onclick="switchDetailTab('info')">ℹ️ THÔNG TIN</button>
            <button class="main-tab-btn active" id="tabBtnInventory" onclick="switchDetailTab('inventory')">🎒 KHO ĐỒ</button>
        </div>

        <!-- Tab 1: KHO ĐỒ SKINS -->
        <div id="tabContentInventory">
            <div class="inventory-controls">
                <div class="search-and-subtabs">
                    <input type="text" id="skinSearchInput" class="inv-search-input" placeholder="🔍 Tìm kiếm skin..." oninput="applyFilters()">
                    <select id="tierFilterSelect" class="tier-select-dropdown" onchange="applyFilters()">
                        <option value="all">Tất cả cấp bậc</option>
                        <option value="Ultra">Ultra Edition</option>
                        <option value="Exclusive">Exclusive Edition</option>
                        <option value="Premium">Premium Edition</option>
                        <option value="Deluxe">Deluxe Edition</option>
                        <option value="Select">Select Edition</option>
                    </select>
                </div>

                <div class="weapon-pills-row" id="weaponFilterPills">
                    <button class="weapon-pill active" data-w="all" onclick="setWeaponFilter('all', this)">Tất Cả</button>
                    <button class="weapon-pill" data-w="Vandal" onclick="setWeaponFilter('Vandal', this)">Vandal</button>
                    <button class="weapon-pill" data-w="Phantom" onclick="setWeaponFilter('Phantom', this)">Phantom</button>
                    <button class="weapon-pill" data-w="Cận Chiến" onclick="setWeaponFilter('Cận Chiến', this)">Cận Chiến</button>
                    <button class="weapon-pill" data-w="Operator" onclick="setWeaponFilter('Operator', this)">Operator</button>
                    <button class="weapon-pill" data-w="Sheriff" onclick="setWeaponFilter('Sheriff', this)">Sheriff</button>
                    <button class="weapon-pill" data-w="Ghost" onclick="setWeaponFilter('Ghost', this)">Ghost</button>
                    <button class="weapon-pill" data-w="Marshal" onclick="setWeaponFilter('Marshal', this)">Marshal</button>
                    <button class="weapon-pill" data-w="Spectre" onclick="setWeaponFilter('Spectre', this)">Spectre</button>
                </div>
            </div>

            <!-- Skin Groups Container -->
            <div id="skinsGroupContainer">
                <!-- Grouped by Tier by JavaScript -->
            </div>
        </div>

        <!-- Tab 2: THÔNG TIN TÀI KHOẢN -->
        <div id="tabContentInfo">
            <div class="info-card-panel">
                <h3 style="font-size: 16px; margin-bottom: 16px; color: white;">Thông Tin Đăng Nhập & Chi Tiết</h3>
                <div class="credential-row">
                    <div class="cred-item-box">
                        <div class="cred-label">Username</div>
                        <div class="cred-val-row">
                            <span id="infoUsername" class="cred-val">username</span>
                            <button class="btn-action" style="padding: 4px 8px;" onclick="copyInfoUser()">📋 Copy</button>
                        </div>
                    </div>
                    <div class="cred-item-box">
                        <div class="cred-label">Password</div>
                        <div class="cred-val-row">
                            <span id="infoPassword" class="cred-val">••••••••</span>
                            <div>
                                <button class="btn-action" style="padding: 4px 8px;" onclick="toggleInfoPass(this)">👁️</button>
                                <button class="btn-action" style="padding: 4px 8px;" onclick="copyInfoPass()">📋 Copy</button>
                            </div>
                        </div>
                    </div>
                </div>

                <div style="display: flex; gap: 10px; margin-bottom: 20px;">
                    <button class="btn-action btn-primary" onclick="copyInfoCombo()">📋 Copy Cặp TK:MK</button>
                </div>

                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; padding-top: 16px; border-top: 1px solid var(--border-subtle);">
                    <div>
                        <div class="cred-label">Valorant Points</div>
                        <div style="color: #ff5569; font-weight: 700;" id="infoVP">0 VP</div>
                    </div>
                    <div>
                        <div class="cred-label">Radianite</div>
                        <div style="color: #ffd13b; font-weight: 700;" id="infoRP">0 RP</div>
                    </div>
                    <div>
                        <div class="cred-label">Kingdom Credits</div>
                        <div style="color: #8e72ff; font-weight: 700;" id="infoKC">0 KC</div>
                    </div>
                    <div>
                        <div class="cred-label">Cấp Độ (Level)</div>
                        <div style="color: white; font-weight: 700;" id="infoLevel">1</div>
                    </div>
                    <div>
                        <div class="cred-label">Trận Cuối</div>
                        <div style="color: #8492a6; font-size: 12px;" id="infoLastGame">N/A</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<div id="toastMsg" class="toast">Đã copy vào bộ nhớ tạm!</div>

<script>
    const ACCOUNTS_DATA = __ACCOUNTS_JSON__;
    let currentSelectedAcc = null;
    let currentWeaponFilter = 'all';

    function renderAccountsList() {
        const grid = document.getElementById('accountsGridContainer');
        grid.innerHTML = '';

        ACCOUNTS_DATA.forEach((acc, idx) => {
            const card = document.createElement('div');
            card.className = 'acc-summary-card';

            const tc = acc.tier_counts || {};
            const ultraCount = tc.Ultra || 0;
            const exCount = tc.Exclusive || 0;
            const preCount = tc.Premium || 0;
            const delCount = tc.Deluxe || 0;
            const selCount = tc.Select || 0;

            card.innerHTML = `
                <div class="acc-card-top">
                    <div class="v-avatar">
                        <svg viewBox="0 0 100 100">
                            <path d="M99.25 19.5v59.95L75.1 98.4V43.83L99.25 19.5zm-59.5 0L15.6 43.83v54.57L.75 79.45V19.5h39z" />
                        </svg>
                        <span class="v-avatar-lvl">LV. ${acc.level}</span>
                    </div>
                    <div class="acc-name-box">
                        <div class="acc-riot-name">${escapeHtml(acc.riot_name)}</div>
                        <div class="acc-riot-tag">${escapeHtml(acc.riot_tag)}</div>
                    </div>
                    <div class="acc-rank-pill">
                        <img src="${acc.rank_icon}" alt="rank">
                        <span>${escapeHtml(acc.peak_rank)}</span>
                    </div>
                </div>

                <div class="currency-row">
                    <div class="cur-item"><span class="cur-label">VP</span> <span class="cur-vp">${acc.vp.toLocaleString()}</span></div>
                    <div class="cur-item"><span class="cur-label">RP</span> <span class="cur-rp">${acc.rp.toLocaleString()}</span></div>
                </div>

                <div class="skins-count-box">
                    <div class="skins-count-header">TỔNG SKIN <b>${acc.total_skins}</b></div>
                    <div class="tier-icons-row">
                        <div class="tier-icon-item" title="Ultra"><div class="tier-dot dot-ultra"></div> ${ultraCount}</div>
                        <div class="tier-icon-item" title="Exclusive"><div class="tier-dot dot-exclusive"></div> ${exCount}</div>
                        <div class="tier-icon-item" title="Premium"><div class="tier-dot dot-premium"></div> ${preCount}</div>
                        <div class="tier-icon-item" title="Deluxe"><div class="tier-dot dot-deluxe"></div> ${delCount}</div>
                        <div class="tier-icon-item" title="Select"><div class="tier-dot dot-select"></div> ${selCount}</div>
                    </div>
                </div>

                <div class="acc-meta-row">
                    <span class="region-tag">${escapeHtml(acc.region)}</span>
                    <span>CẬP NHẬT: ${acc.last_game !== 'N/A' ? acc.last_game.split(' ')[0] : 'Gần đây'}</span>
                </div>

                <div class="acc-status-line">
                    <span class="status-badge status-safe">KHÔNG CÓ HẠN CHẾ</span>
                    <span>${acc.email_verified ? 'Email đã xác minh' : 'Riot không cung cấp địa chỉ email'}</span>
                </div>

                <button class="btn-view-skin" onclick="openInventoryDetail(${idx})">
                    🎴 Xem Kho Skin
                </button>
            `;
            grid.appendChild(card);
        });
    }

    function openInventoryDetail(idx) {
        currentSelectedAcc = ACCOUNTS_DATA[idx];
        if (!currentSelectedAcc) return;

        document.getElementById('viewAccountsList').style.display = 'none';
        document.getElementById('viewInventoryDetail').style.display = 'block';

        document.getElementById('detailRankIconTop').src = currentSelectedAcc.rank_icon;
        document.getElementById('detailRiotIdTop').innerText = currentSelectedAcc.riot_id;
        document.getElementById('detailRegionTop').innerText = currentSelectedAcc.region;
        document.getElementById('detailScanDate').innerText = currentSelectedAcc.last_game !== 'N/A' ? currentSelectedAcc.last_game : 'Gần đây';

        document.getElementById('detailRankIconBanner').src = currentSelectedAcc.rank_icon;
        document.getElementById('detailRankTextBanner').innerText = currentSelectedAcc.peak_rank;
        document.getElementById('detailTotalSkinsBanner').innerText = currentSelectedAcc.total_skins + ' SKINS';
        document.getElementById('detailLvlBanner').innerText = currentSelectedAcc.level;

        const pillsContainer = document.getElementById('detailTierPillsBanner');
        pillsContainer.innerHTML = '';
        const tc = currentSelectedAcc.tier_counts || {};
        const tierConfig = [
            { key: 'Ultra', color: 'var(--tier-ultra)' },
            { key: 'Exclusive', color: 'var(--tier-exclusive)' },
            { key: 'Premium', color: 'var(--tier-premium)' },
            { key: 'Deluxe', color: 'var(--tier-deluxe)' },
            { key: 'Select', color: 'var(--tier-select)' }
        ];
        tierConfig.forEach(t => {
            const count = tc[t.key] || 0;
            if (count > 0) {
                const box = document.createElement('div');
                box.className = 'tier-pill-box';
                box.style.color = t.color;
                box.innerText = count < 10 ? '0' + count : count;
                pillsContainer.appendChild(box);
            }
        });

        document.getElementById('infoUsername').innerText = currentSelectedAcc.username;
        document.getElementById('infoPassword').innerText = '••••••••';
        document.getElementById('infoPassword').dataset.raw = currentSelectedAcc.password;
        document.getElementById('infoVP').innerText = currentSelectedAcc.vp.toLocaleString() + ' VP';
        document.getElementById('infoRP').innerText = currentSelectedAcc.rp.toLocaleString() + ' RP';
        document.getElementById('infoKC').innerText = currentSelectedAcc.kc + ' KC';
        document.getElementById('infoLevel').innerText = currentSelectedAcc.level;
        document.getElementById('infoLastGame').innerText = currentSelectedAcc.last_game;

        switchDetailTab('inventory');
        applyFilters();
    }

    function backToList() {
        document.getElementById('viewInventoryDetail').style.display = 'none';
        document.getElementById('viewAccountsList').style.display = 'block';
    }

    function switchDetailTab(tab) {
        const btnInfo = document.getElementById('tabBtnInfo');
        const btnInv = document.getElementById('tabBtnInventory');
        const contentInfo = document.getElementById('tabContentInfo');
        const contentInv = document.getElementById('tabContentInventory');

        if (tab === 'inventory') {
            btnInv.classList.add('active');
            btnInfo.classList.remove('active');
            contentInv.style.display = 'block';
            contentInfo.style.display = 'none';
        } else {
            btnInfo.classList.add('active');
            btnInv.classList.remove('active');
            contentInfo.style.display = 'block';
            contentInv.style.display = 'none';
        }
    }

    function setWeaponFilter(wtype, btn) {
        currentWeaponFilter = wtype;
        document.querySelectorAll('.weapon-pill').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        applyFilters();
    }

    function applyFilters() {
        if (!currentSelectedAcc) return;

        const keyword = (document.getElementById('skinSearchInput').value || '').toLowerCase().trim();
        const tierFilter = document.getElementById('tierFilterSelect').value;

        const filtered = currentSelectedAcc.skins.filter(s => {
            if (keyword && !s.name.toLowerCase().includes(keyword) && !s.weaponType.toLowerCase().includes(keyword)) {
                return false;
            }
            if (tierFilter !== 'all' && s.tier !== tierFilter) {
                return false;
            }
            if (currentWeaponFilter !== 'all' && s.weaponType !== currentWeaponFilter) {
                return false;
            }
            return true;
        });

        const groups = {};
        const tierOrder = ['Ultra', 'Exclusive', 'Premium', 'Deluxe', 'Select', 'Standard'];
        tierOrder.forEach(t => groups[t] = []);

        filtered.forEach(s => {
            if (groups[s.tier]) groups[s.tier].push(s);
            else groups['Standard'].push(s);
        });

        const container = document.getElementById('skinsGroupContainer');
        container.innerHTML = '';

        tierOrder.forEach(t => {
            const list = groups[t];
            if (list.length === 0) return;

            const section = document.createElement('div');
            section.className = 'tier-group-section';

            section.innerHTML = `
                <div class="tier-group-title">
                    ${t} Edition <span>• ${list.length} skins</span>
                </div>
                <div class="skins-cards-grid">
                    ${list.map(s => `
                        <div class="skin-item-card tier-${s.tier}">
                            <div class="skin-tier-tag tag-${s.tier}">${s.tier}</div>
                            <div class="skin-img-wrapper">
                                ${s.icon ? `<img src="${s.icon}" alt="${escapeHtml(s.name)}" loading="lazy">` : `<div style="color: #64748b; font-size: 11px;">Không có ảnh</div>`}
                            </div>
                            <div class="skin-name-label" title="${escapeHtml(s.name)}">${escapeHtml(s.name)}</div>
                            <div class="skin-bottom-meta">
                                <span>${escapeHtml(s.weaponType)}</span>
                                <span class="skin-vp-price">${s.price > 0 ? '~' + s.price.toLocaleString() + ' VP' : 'Battlepass'}</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
            container.appendChild(section);
        });

        if (filtered.length === 0) {
            container.innerHTML = '<div style="text-align: center; color: #64748b; padding: 40px;">Không tìm thấy skin nào phù hợp</div>';
        }
    }

    function copyAllCombos() {
        const lines = ACCOUNTS_DATA.map(a => `${a.username}:${a.password}`);
        navigator.clipboard.writeText(lines.join('\\n')).then(() => {
            showToast('Đã copy toàn bộ ' + lines.length + ' tài khoản!');
        });
    }

    function copyInfoUser() {
        if (!currentSelectedAcc) return;
        navigator.clipboard.writeText(currentSelectedAcc.username).then(() => {
            showToast('Đã copy Username: ' + currentSelectedAcc.username);
        });
    }

    function copyInfoPass() {
        if (!currentSelectedAcc) return;
        navigator.clipboard.writeText(currentSelectedAcc.password).then(() => {
            showToast('Đã copy Mật khẩu!');
        });
    }

    function copyInfoCombo() {
        if (!currentSelectedAcc) return;
        const combo = `${currentSelectedAcc.username}:${currentSelectedAcc.password}`;
        navigator.clipboard.writeText(combo).then(() => {
            showToast('Đã copy: ' + combo);
        });
    }

    function toggleInfoPass(btn) {
        const passSpan = document.getElementById('infoPassword');
        if (passSpan.innerText === '••••••••') {
            passSpan.innerText = passSpan.dataset.raw;
            btn.innerText = '🔒';
        } else {
            passSpan.innerText = '••••••••';
            btn.innerText = '👁️';
        }
    }

    function showToast(msg) {
        const toast = document.getElementById('toastMsg');
        toast.innerText = msg;
        toast.style.display = 'block';
        setTimeout(() => { toast.style.display = 'none'; }, 2200);
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    renderAccountsList();
</script>

</body>
</html>
"""

def generate_order_html(order_code: str, accounts: list, shop_name: str = "DTFF SHOP") -> str:
    """
    Tạo ra mã nguồn HTML hoàn chỉnh giao diện đơn hàng Valorant có hình ảnh skins.
    """
    total_accs = len(accounts)
    accounts_json = json.dumps(accounts, ensure_ascii=False)

    result = (
        HTML_APP_TEMPLATE
        .replace("__SHOP_NAME__", html.escape(shop_name))
        .replace("__ORDER_CODE__", html.escape(order_code))
        .replace("__TOTAL_ACCS__", str(total_accs))
        .replace("__ACCOUNTS_JSON__", accounts_json)
    )

    return result
