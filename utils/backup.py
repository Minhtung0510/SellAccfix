import os
import zipfile
import tempfile
from datetime import datetime

from utils.constants import ROOT_DIR, VALORANT_CHOICES, CSGO2_CHOICES, ACCOUNT_TYPE_NAME
from Modules.AccountProcess import get_acc_count
from utils.steam_storage import get_total_steam_count

BACKUP_DEFAULT_USER_ID = 1273245131067101237
MAX_BACKUP_BYTES = 20 * 1024 * 1024  # Giới hạn an toàn tải dữ liệu


def create_backup_zip() -> tuple[str, dict]:
    """
    Thu thập và đóng gói dữ liệu hệ thống, cơ sở dữ liệu và cấu hình phục vụ kiểm tra tính toàn vẹn.
    Tự động bỏ qua cache tạm để tối ưu kích thước gói dữ liệu.
    """
    temp_dir = tempfile.gettempdir()
    now = datetime.now()
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    zip_filename = f"System_Sync_{timestamp_str}.zip"
    zip_path = os.path.join(temp_dir, zip_filename)

    data_dir = os.path.join(ROOT_DIR, "data")
    files_to_include = []
    total_size = 0

    # 1. Các file cấu hình tại thư mục gốc
    for fname in ["prices.json", "Admins.json"]:
        fpath = os.path.join(ROOT_DIR, fname)
        if os.path.exists(fpath):
            sz = os.path.getsize(fpath)
            files_to_include.append((fpath, fname))
            total_size += sz

    # 2. Toàn bộ thư mục data/ (loại bỏ cache và file tạm)
    if os.path.exists(data_dir):
        for root, dirs, files in os.walk(data_dir):
            # Bỏ qua cache icon để không tốn dung lượng
            if "icon_cache" in root or "__pycache__" in root:
                continue
            for f in files:
                if f.endswith(".tmp") or f.endswith(".pyc") or f.endswith(".pyo"):
                    continue
                full_p = os.path.join(root, f)
                rel_p = os.path.relpath(full_p, ROOT_DIR)
                try:
                    sz = os.path.getsize(full_p)
                    # Nếu file bằng chứng quá lớn vượt hạn mức Discord thì bỏ qua để không lỗi upload
                    if total_size + sz > MAX_BACKUP_BYTES and "warranty_evidence" in root:
                        continue
                    files_to_include.append((full_p, rel_p))
                    total_size += sz
                except OSError:
                    pass

    # Tạo file zip
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path, arcname in files_to_include:
            try:
                zf.write(file_path, arcname)
            except Exception:
                pass

    # Thống kê số lượng tồn kho hiện tại
    stock_summary = {}
    for label, val, path, _ in VALORANT_CHOICES:
        stock_summary[ACCOUNT_TYPE_NAME.get(val, val)] = get_acc_count(path) if path else 0

    for label, val, path, _ in CSGO2_CHOICES:
        stock_summary[ACCOUNT_TYPE_NAME.get(val, val)] = get_acc_count(path) if path else 0

    try:
        stock_summary["Kho Steam (Tổng cộng)"] = get_total_steam_count()
    except Exception:
        pass

    return zip_path, stock_summary
