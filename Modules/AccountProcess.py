import os
import re
import tempfile

from utils.constants import get_account_file_path


_count_cache = {}


def split_raw_accounts(text: str) -> list[str]:
    """
    Tự động nhận diện dữ liệu kho:
    1. Nếu là định dạng log của tool check (có '---------------------------' hoặc 'Username:'):
       Tách theo từng khối tài khoản hoàn chỉnh.
    2. Nếu là danh sách dòng user:pass thông thường:
       Tách theo từng dòng.
    """
    text = text.strip()
    if not text:
        return []

    if "---------------------------" in text or re.search(r"-{10,}", text) or "Username:" in text:
        blocks = re.split(r"-{10,}", text)
        result = []
        for b in blocks:
            b_clean = b.strip()
            if b_clean and ("Username:" in b_clean or ":" in b_clean):
                result.append(b_clean)
        return result
    else:
        return [line.strip() for line in text.splitlines() if line.strip()]


def get_acc_count(file_path):
    """Đếm số tài khoản trong kho, hỗ trợ cả định dạng log và tk:mk từng dòng."""
    try:
        stat = os.stat(file_path)
        signature = (stat.st_mtime_ns, stat.st_size)
        cached = _count_cache.get(file_path)
        if cached is not None and cached[0] == signature:
            return cached[1]
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        count = len(split_raw_accounts(content))
        _count_cache[file_path] = (signature, count)
        return count
    except FileNotFoundError:
        _count_cache.pop(file_path, None)
        return 0


def get_random_acc(account_type: str, quantity: int):
    """
    Lấy `quantity` acc từ kho của loại `account_type`.
    Hỗ trợ cả file log của tool check (khối) và file user:pass (dòng).
    """
    file_path = get_account_file_path(account_type)

    if file_path is None or quantity <= 0:
        return []

    if not os.path.exists(file_path):
        return []

    dir_name = os.path.dirname(file_path)
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix="acc_tmp_", text=True)
    try:
        with open(file_path, "r", encoding="utf-8") as source:
            content = source.read()

        all_accs = split_raw_accounts(content)
        if len(all_accs) < quantity:
            os.close(fd)
            return []

        selected = all_accs[:quantity]
        remaining = all_accs[quantity:]

        is_log_format = "---------------------------" in content or any("Username:" in a for a in all_accs)

        with os.fdopen(fd, "w", encoding="utf-8") as target:
            for acc in remaining:
                if is_log_format:
                    target.write(acc + "\n---------------------------\n")
                else:
                    target.write(acc + "\n")

        os.replace(tmp_path, file_path)
        stat = os.stat(file_path)
        _count_cache[file_path] = ((stat.st_mtime_ns, stat.st_size), len(remaining))
        return selected
    except Exception as e:
        print(f"Lỗi khi lấy acc từ kho: {e}")
        return []
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
