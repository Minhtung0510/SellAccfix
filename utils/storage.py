import json
import os
from .constants import MENUS_FILE, TICKET_FILE, ADMINS_FILE

# ===== Menus =====
def load_menus():
    if not os.path.exists(MENUS_FILE):
        return []
    try:
        with open(MENUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_menus(menus):
    os.makedirs(os.path.dirname(MENUS_FILE), exist_ok=True)
    temp = MENUS_FILE + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(menus, f, ensure_ascii=False, indent=2)
    os.replace(temp, MENUS_FILE)


def add_menu(message_id: int, channel_id: int):
    menus = load_menus()
    menus.append({"message_id": message_id, "channel_id": channel_id})
    save_menus(menus)

# ===== Tickets =====
def load_tickets():
    if not os.path.exists(TICKET_FILE):
        return []
    try:
        with open(TICKET_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_tickets(tickets):
    os.makedirs(os.path.dirname(TICKET_FILE), exist_ok=True)
    temp = TICKET_FILE + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(tickets, f, ensure_ascii=False, indent=2)
    os.replace(temp, TICKET_FILE)


def is_ticket_channel(channel_id: int) -> bool:
    tickets = load_tickets()
    return channel_id in tickets

# ===== Admins =====
def load_admin_ids():
    try:
        with open(ADMINS_FILE, "r", encoding="utf-8") as f:
            return [int(line.strip()) for line in f if line.strip()]
    except Exception:
        return []


def save_admin_ids(admin_ids):
    os.makedirs(os.path.dirname(ADMINS_FILE), exist_ok=True)
    temp = ADMINS_FILE + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        for admin_id in admin_ids:
            f.write(f"{admin_id}\n")
    os.replace(temp, ADMINS_FILE)


# Persist the channel rename cooldown across bot restarts.
STOCK_STATE_FILE = os.path.join(os.path.dirname(MENUS_FILE), "stock_channel_state.json")
SETTINGS_FILE = os.path.join(os.path.dirname(MENUS_FILE), "settings.json")


def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(settings):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    temp = SETTINGS_FILE + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    os.replace(temp, SETTINGS_FILE)


def get_warranty_channel_id():
    settings = load_settings()
    if settings.get("warranty_channel_id"):
        try:
            return int(settings["warranty_channel_id"])
        except (ValueError, TypeError):
            pass
    env_id = os.getenv("WARRANTY_CHANNEL_ID")
    if env_id and env_id.strip().isdigit():
        return int(env_id.strip())
    return None


def set_warranty_channel_id(channel_id: int):
    settings = load_settings()
    settings["warranty_channel_id"] = channel_id
    save_settings(settings)


def get_feedback_channel_id():
    value = load_settings().get('feedback_channel_id') or os.getenv('FEEDBACK_CHANNEL_ID')
    try:
        return int(value) if value else None
    except (ValueError, TypeError):
        return None


def set_feedback_channel_id(channel_id):
    settings = load_settings()
    settings['feedback_channel_id'] = channel_id
    save_settings(settings)


def load_stock_cooldown(channel_id):
    try:
        with open(STOCK_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("channel_id") == channel_id:
            value = float(data["next_edit_at"])
            import math
            if math.isfinite(value):
                return value
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        pass
    return None


def save_stock_cooldown(channel_id, next_edit_at):
    os.makedirs(os.path.dirname(STOCK_STATE_FILE), exist_ok=True)
    temporary = STOCK_STATE_FILE + ".tmp"
    with open(temporary, "w", encoding="utf-8") as f:
        json.dump({"channel_id": channel_id, "next_edit_at": next_edit_at}, f)
    os.replace(temporary, STOCK_STATE_FILE)
