# -*- coding: utf-8 -*-
"""
Drop-in replacement for previous PayOS module, switched to Web2M.

Exports the same names used in your project:
- set_payos_instance(...)           -> kept for backward compatibility (initializes Web2M env)
- generate_random_code(n=8)
- CreatePayment(item_name, item_price, item_description)
- check_payment_status(order_dict)  -> optional helper if you need it

You should now embed `payment.qrUrl` in your message to users.
"""
import os
import random
import string
import requests
from urllib.parse import quote

# --- Web2M config (read from environment) ---
import os

BANK_CODE = None
ACCOUNT_NO = None
ACCOUNT_NAME = None
WEB2M_PASSWORD = None
WEB2M_TOKEN = None

def payment_test_mode():
    return os.getenv("PAYMENT_TEST_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}

def load_config(bank_code=None, account_no=None, account_name=None, password=None, token=None):
    global BANK_CODE, ACCOUNT_NO, ACCOUNT_NAME, WEB2M_PASSWORD, WEB2M_TOKEN

    # Nếu không truyền thì đọc từ .env
    if bank_code is None:
        from dotenv import load_dotenv
        load_dotenv()
        bank_code = os.getenv("BANK_CODE")
        account_no = os.getenv("ACCOUNT_NO")
        account_name = os.getenv("ACCOUNT_NAME")
        password = os.getenv("WEB2M_PASSWORD")
        token = os.getenv("WEB2M_TOKEN")

    BANK_CODE = bank_code
    ACCOUNT_NO = account_no
    ACCOUNT_NAME = account_name
    WEB2M_PASSWORD = password
    WEB2M_TOKEN = token
    print(f"[WEB2M] Config loaded: BANK_CODE={BANK_CODE}, ACCOUNT_NO={ACCOUNT_NO}, ACCOUNT_NAME={ACCOUNT_NAME}, PASSWORD={'***' if WEB2M_PASSWORD else None}, TOKEN={'***' if WEB2M_TOKEN else None}")

def set_payos_instance(*_args, **_kwargs):
    """Backward compatible no-op. Ensures env vars above are loaded by your .env."""
    # No action needed — we read config directly from environment.
    return True

def generate_random_code(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))

class _PaymentObject:
    def __init__(self, order_code: str, amount: int, memo: str, qr_url: str,
                 item_name: str, item_description: str):
        # tên cũ bạn đang dùng
        self.orderCode = order_code
        # alias dự phòng nếu ở nơi khác dùng snake_case
        self.order_code = order_code

        self.amount = amount
        self.memo = memo
        self.qrUrl = qr_url        # camelCase
        self.qr_url = qr_url       # snake_case
        self.checkoutUrl = qr_url  # giữ tương thích

        self.item_name = item_name
        self.item_description = item_description

def CreatePayment(item_name: str, item_price: int, item_description: str):
    order_code = generate_random_code()
    memo = f"ACC-{order_code}"

    # Encode tên tài khoản để không lỗi dấu cách/ký tự
    name_enc = quote(ACCOUNT_NAME or "", safe="")
    bank = (BANK_CODE or "MBB").upper()
    acc  = ACCOUNT_NO or ""

    qr_url = (
        f"https://apiqr.web2m.com/api/generate/{bank}/{acc}/{name_enc}"
        f"?amount={int(item_price)}&memo={memo}"
    )

    # print(BANK_CODE, ACCOUNT_NO, ACCOUNT_NAME)
    # print("[WEB2M] memo:", memo)
    # print("[WEB2M] qr_url:", qr_url)

    return _PaymentObject(
        order_code=order_code,
        amount=int(item_price),
        memo=memo,
        qr_url=qr_url,
        item_name=item_name,
        item_description=item_description,
    )

def _fetch_history():
    if not (WEB2M_PASSWORD and ACCOUNT_NO and WEB2M_TOKEN):
        return None
    url = f"https://api.web2m.com/historyapimb/{WEB2M_PASSWORD}/{ACCOUNT_NO}/{WEB2M_TOKEN}"
    #print("[WEB2M] Fetching history from:", url)
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        print("[WEB2M] History fetched successfully.")
        #print("[WEB2M] History response:", resp.status_code, resp.text)
        return resp.json()
    except Exception:
        return None

def check_payment_status(order: dict, history=None) -> bool:
    """
    OPTIONAL helper: Return True if a transaction with memo (order_code) is found.
    If 'amount' exists in order, require exact amount too; otherwise match by code only.
    """
    data = history if history is not None else _fetch_history()
    if not data or not data.get("status"):
        return False

    code = (order.get("order_code") or "").upper()
    need_amount = order.get("amount")
    try:
        need_amount = int(need_amount) if need_amount is not None else None
    except Exception:
        need_amount = None

    for tx in data.get("data", []):
        #desc = f"{tx.get('description','')} {tx.get('addDescription','')}".upper()
        desc = f"{tx.get('description','')} {tx.get('addDescription','')}".upper().replace(" ", "")
        if code and code in desc:
            if need_amount is None:
                return True
            try:
                credit = int(str(tx.get("creditAmount", "0")).replace(",", "").strip())
            except Exception:
                credit = 0
            if credit >= need_amount:
                return True
    return False

