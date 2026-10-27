# -*- coding: utf-8 -*-
"""
Đơn hàng lưu local file + kiểm tra thanh toán qua Web2M.
Giữ nguyên API như project cũ:
- load_orders(), save_orders(list)
- add_order(dict), find_order(code), remove_order(code)
- check_order(index) -> "PAID" | "CANCELLED" | "TimeOut" | "PENDING"
"""
import os
import json
import time
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
ORDERS_FILE = os.path.join(ROOT_DIR, "data", "orders.json")

PENDING_TTL_SECONDS = int(os.getenv("PENDING_TTL_SECONDS", "1800"))

def _now_ts() -> int:
    return int(time.time())

def load_orders():
    if not os.path.exists(ORDERS_FILE):
        return []
    try:
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_orders(orders):
    os.makedirs(os.path.dirname(ORDERS_FILE), exist_ok=True)
    temp = ORDERS_FILE + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)
    os.replace(temp, ORDERS_FILE)

def add_order(order_dict: dict):
    orders = load_orders()
    order_dict = dict(order_dict)
    if "created_at" not in order_dict:
        order_dict["created_at"] = _now_ts()
    orders.append(order_dict)
    save_orders(orders)

def find_order(order_code: str):
    orders = load_orders()
    for o in orders:
        if o.get("order_code") == order_code:
            return o
    return None

def remove_order(order_code: str):
    orders = load_orders()
    new_orders = [o for o in orders if o.get("order_code") != order_code]
    save_orders(new_orders)

# --- Web2M check ---
from .pay import check_payment_status as _check_payment_status

def check_order(index: int):
    orders = load_orders()
    if index < 0 or index >= len(orders):
        return "PENDING"
    order = orders[index]

    # Timeout?
    created_at = int(order.get("created_at", _now_ts()))

    if _now_ts() - created_at > PENDING_TTL_SECONDS:
        return "TimeOut"

    matched = _check_payment_status(order)
    if matched:
        return "PAID"

    return "PENDING"
