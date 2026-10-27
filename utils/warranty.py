"""Durable warranty ledger; all public mutations are synchronous and transactional."""
import hashlib
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from utils.constants import ROOT_DIR, get_account_file_path, ACCOUNT_TYPE_NAME


class WarrantyError(ValueError):
    pass


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


class WarrantyStore:
    def __init__(self, path=None, stock_path=None, normal_ttl=7200, off_ttl=18000):
        self.path = Path(path or Path(ROOT_DIR) / 'data' / 'warranty.sqlite3')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stock_path = stock_path or get_account_file_path
        self.normal_ttl = normal_ttl
        self.off_ttl = off_ttl
        with self.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS deliveries (
                    code TEXT PRIMARY KEY, buyer INTEGER NOT NULL, account_type TEXT NOT NULL,
                    accounts TEXT NOT NULL, amount INTEGER, delivered_at REAL NOT NULL, expires_at REAL NOT NULL,
                    channel_id INTEGER, steam_game TEXT
                );
                CREATE TABLE IF NOT EXISTS claims (
                    id TEXT PRIMARY KEY, code TEXT NOT NULL REFERENCES deliveries(code),
                    created_at REAL NOT NULL, note TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
                    replacements TEXT, stock_file TEXT, staged_file TEXT,
                    before_hash TEXT, after_hash TEXT,
                    admin_id INTEGER, admin_note TEXT, resolved_at REAL, ticket_channel_id INTEGER,
                    attempt INTEGER DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS claim_items (
                    code TEXT NOT NULL, position INTEGER NOT NULL,
                    claim_id TEXT NOT NULL REFERENCES claims(id),
                    evidence_hash TEXT NOT NULL, evidence_path TEXT NOT NULL,
                    PRIMARY KEY(claim_id, position)
                );
                CREATE INDEX IF NOT EXISTS claims_by_order ON claims(code);
                CREATE INDEX IF NOT EXISTS idx_claim_items_code_pos ON claim_items(code, position);
            ''')
            # Remove legacy global evidence uniqueness without losing existing claims.
            pk_cols = [r['name'] for r in db.execute('PRAGMA table_info(claim_items)') if r['pk'] > 0]
            global_unique = any(
                [r['name'] for r in db.execute('PRAGMA index_info("' + index['name'] + '")')] == ['evidence_hash']
                for index in db.execute('PRAGMA index_list(claim_items)') if index['unique']
            )
            if pk_cols == ['code', 'position'] or global_unique:
                db.execute('BEGIN IMMEDIATE')
                db.execute("""CREATE TABLE claim_items_v3 (
                    code TEXT NOT NULL, position INTEGER NOT NULL,
                    claim_id TEXT NOT NULL REFERENCES claims(id),
                    evidence_hash TEXT NOT NULL, evidence_path TEXT NOT NULL,
                    PRIMARY KEY(claim_id, position))""")
                db.execute('INSERT INTO claim_items_v3 SELECT code, position, claim_id, evidence_hash, evidence_path FROM claim_items')
                db.execute('DROP TABLE claim_items')
                db.execute('ALTER TABLE claim_items_v3 RENAME TO claim_items')
                db.execute('CREATE INDEX idx_claim_items_code_pos ON claim_items(code, position)')
            db.execute('CREATE INDEX IF NOT EXISTS claim_items_evidence ON claim_items(evidence_hash)')

            for table, col, col_type in [
                ("deliveries", "channel_id", "INTEGER"),
                ("deliveries", "test_order", "INTEGER NOT NULL DEFAULT 0"),
                ("deliveries", "steam_game", "TEXT"),
                ("claims", "admin_id", "INTEGER"),
                ("claims", "admin_note", "TEXT"),
                ("claims", "resolved_at", "REAL"),
                ("claims", "ticket_channel_id", "INTEGER"),
                ("claims", "attempt", "INTEGER DEFAULT 1"),
            ]:
                try:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                except sqlite3.OperationalError:
                    pass

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def record_delivery(self, order, accounts):
        if len(accounts) != int(order['quantity']):
            raise WarrantyError('Số lượng giao không khớp đơn hàng.')
        payload = json.dumps(accounts, ensure_ascii=False)
        code = order.get('order_code') or order.get('code')
        user_id = order.get('user_id') or order.get('buyer')
        channel_id = order.get('channel_id')
        steam_game = order.get('steam_game') or order.get('game_query') or ''
        with self.connection() as db:
            old = db.execute('SELECT * FROM deliveries WHERE code=?', (code,)).fetchone()
            if old:
                if (old['buyer'], old['account_type'], old['accounts']) != (user_id, order['account_type'], payload):
                    raise WarrantyError('Đơn đã lưu có dữ liệu khác. Cần admin kiểm tra.')
                return
            db.execute('''
                INSERT INTO deliveries(code, buyer, account_type, accounts, amount, delivered_at, expires_at, channel_id, steam_game)
                VALUES(?,?,?,?,?,?,?,?,?)
            ''', (code, user_id, order['account_type'], payload,
                  order.get('amount'), 0, 0, channel_id, steam_game))
            db.execute('UPDATE deliveries SET test_order=? WHERE code=?', (int(bool(order.get('test_order'))), code))

    def mark_delivered(self, code):
        with self.connection() as db:
            row = db.execute('SELECT * FROM deliveries WHERE code=?', (code,)).fetchone()
            if row is None:
                raise WarrantyError('Không tìm thấy đơn để ghi nhận đã giao.')
            if not row['delivered_at']:
                now = time.time()
                ttl = self.off_ttl if 'Chủ Off' in ACCOUNT_TYPE_NAME.get(row['account_type'], '') else self.normal_ttl
                db.execute('UPDATE deliveries SET delivered_at=?, expires_at=? WHERE code=?', (now, now + ttl, code))

    def order(self, code, buyer, *, require_active=False):
        with self.connection() as db:
            row = db.execute('SELECT * FROM deliveries WHERE code=?', (code,)).fetchone()
            if not row:
                raise WarrantyError('Đơn này chưa có trong sổ bảo hành. Hãy liên hệ admin.')
            if row['buyer'] != buyer:
                raise WarrantyError('Chỉ người đã mua đơn này được sử dụng bảo hành.')
            if not row['delivered_at']:
                raise WarrantyError('Đơn đang được giao. Vui lòng thử lại sau vài giây.')
            result = dict(row)
            result['accounts'] = json.loads(result['accounts'])
            result['used'] = {r[0] for r in db.execute('SELECT position FROM claim_items WHERE code=?', (code,))}

            pending_positions = {r[0] for r in db.execute('''
                SELECT ci.position FROM claim_items ci JOIN claims c ON ci.claim_id = c.id
                WHERE ci.code=? AND c.state IN ('pending', 'prepared', 'ready')
            ''', (code,))}

            approved_counts = {}
            for r in db.execute('''
                SELECT ci.position, COUNT(*) FROM claim_items ci JOIN claims c ON ci.claim_id = c.id
                WHERE ci.code=? AND c.state='approved'
                GROUP BY ci.position
            ''', (code,)):
                approved_counts[r[0]] = r[1]

            result['approved_counts'] = approved_counts
            result['pending_positions'] = pending_positions
            result['current_accounts'] = list(result['accounts'])
            for claim in db.execute("SELECT id, replacements FROM claims WHERE code=? AND state='approved' ORDER BY created_at, rowid", (code,)):
                positions = [r[0] for r in db.execute('SELECT position FROM claim_items WHERE claim_id=? ORDER BY rowid', (claim['id'],))]
                for position, account in zip(positions, json.loads(claim['replacements'] or '[]')):
                    result['current_accounts'][position - 1] = account

        if require_active and time.time() > result['expires_at']:
            raise WarrantyError('Đơn đã hết thời hạn bảo hành. Hãy liên hệ admin.')
        return result


    def create_claim(self, code, buyer, positions, evidence, note="", ticket_channel_id=None):
        if not positions or len(positions) > 10 or len(positions) != len(evidence):
            raise WarrantyError('Mỗi acc lỗi phải có đúng 1 ảnh/video; tối đa 10 acc mỗi đợt.')
        if len(set(positions)) != len(positions):
            raise WarrantyError('Danh sách chọn bị trùng acc.')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM deliveries WHERE code=?', (code,)).fetchone()
            if row is None or row['buyer'] != buyer:
                raise WarrantyError('Đơn không thuộc về bạn hoặc không tồn tại.')
            if not row['delivered_at'] or time.time() > row['expires_at']:
                raise WarrantyError('Đơn đã hết thời hạn bảo hành.')
            size = len(json.loads(row['accounts']))
            if any(type(p) is not int or p < 1 or p > size for p in positions):
                raise WarrantyError('Có acc không thuộc đơn hàng này.')

            attempt = 1
            for p in positions:
                is_pending = db.execute('''
                    SELECT 1 FROM claim_items ci JOIN claims c ON ci.claim_id = c.id
                    WHERE ci.code=? AND ci.position=? AND c.state IN ('pending', 'prepared', 'ready')
                ''', (code, p)).fetchone()
                if is_pending:
                    raise WarrantyError(f'Acc #{p} đang có một yêu cầu bảo hành chờ duyệt. Vui lòng đợi Admin xử lý xong.')
                approved_count = db.execute('''
                    SELECT COUNT(*) FROM claim_items ci JOIN claims c ON ci.claim_id = c.id
                    WHERE ci.code=? AND ci.position=? AND c.state='approved'
                ''', (code, p)).fetchone()[0]
                if approved_count >= 3:
                    raise WarrantyError(f'Acc #{p} đã đạt giới hạn tối đa 3 lần bảo hành. Hãy liên hệ trực tiếp Admin.')
                attempt = max(attempt, approved_count + 1)
            attempt = min(attempt, 3)

            if len({item['hash'] for item in evidence}) != len(evidence):
                raise WarrantyError('Không dùng cùng một ảnh/video cho nhiều acc trong một yêu cầu.')
            if not row['test_order']:
                for item in evidence:
                    if db.execute('SELECT 1 FROM claim_items WHERE evidence_hash=?', (item['hash'],)).fetchone():
                        raise WarrantyError('Ảnh/video này đã được dùng trước đó. Yêu cầu chưa được gửi; hãy tải bằng chứng mới của acc đang lỗi.')

            claim_id = uuid.uuid4().hex
            chan_id = ticket_channel_id or (row['channel_id'] if 'channel_id' in row.keys() else None)
            db.execute('''
                INSERT INTO claims(id, code, created_at, note, state, ticket_channel_id, attempt)
                VALUES(?,?,?,?,'pending',?,?)
            ''', (claim_id, code, time.time(), note[:1000], chan_id, attempt))
            try:
                for position, item in zip(positions, evidence):
                    if not Path(item['path']).is_file() or file_hash(item['path']) != item['hash']:
                        raise WarrantyError('Bằng chứng chưa được lưu đầy đủ. Hãy tải lại.')
                    db.execute('INSERT INTO claim_items VALUES(?,?,?,?,?)',
                               (code, position, claim_id, item['hash'], item['path']))
            except sqlite3.IntegrityError as exc:
                raise WarrantyError('Không lưu được yêu cầu bảo hành do dữ liệu trùng. Yêu cầu chưa được gửi; hãy mở lại bảng bảo hành.') from exc
        return claim_id

    def claims(self, code, buyer):
        self.order(code, buyer)
        with self.connection() as db:
            rows = db.execute('SELECT * FROM claims WHERE code=? ORDER BY created_at', (code,)).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item['positions'] = [r[0] for r in db.execute('SELECT position FROM claim_items WHERE claim_id=? ORDER BY rowid', (row['id'],))]
                item['replacements'] = json.loads(item['replacements'] or '[]')
                result.append(item)
            return result

    def get_claim(self, claim_id):
        with self.connection() as db:
            row = db.execute('''
                SELECT c.*, d.buyer, d.account_type, d.accounts as order_accounts, d.channel_id as order_channel_id, d.steam_game
                FROM claims c JOIN deliveries d ON c.code=d.code 
                WHERE c.id=?
            ''', (claim_id,)).fetchone()
            if not row:
                return None
            result = dict(row)
            result['order_accounts'] = json.loads(result['order_accounts'])
            result['replacements'] = json.loads(result['replacements'] or '[]')
            result['positions'] = [r[0] for r in db.execute('SELECT position FROM claim_items WHERE claim_id=? ORDER BY rowid', (claim_id,))]
            result['evidence'] = [dict(r) for r in db.execute('SELECT * FROM claim_items WHERE claim_id=? ORDER BY rowid', (claim_id,))]
            result['attempt'] = result.get('attempt') or 1

            prev_history = []
            for p in result['positions']:
                hist_rows = db.execute('''
                    SELECT c.id, c.created_at, c.replacements, c.state, c.attempt 
                    FROM claim_items ci JOIN claims c ON ci.claim_id = c.id
                    WHERE ci.code=? AND ci.position=? AND c.id != ? AND c.state='approved'
                    ORDER BY c.created_at
                ''', (result['code'], p, claim_id)).fetchall()
                for h in hist_rows:
                    repls = json.loads(h['replacements'] or '[]')
                    prev_history.append({
                        'position': p,
                        'replacements': repls,
                        'attempt': h['attempt'],
                        'created_at': h['created_at']
                    })
            result['previous_history'] = prev_history
            return result


    def recover_allocations(self):
        # Journal protects against a crash between updating stock and recording replacements.
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            for row in db.execute("SELECT * FROM claims WHERE state='prepared'").fetchall():
                if not row['staged_file']:
                    db.execute("UPDATE claims SET state='ready' WHERE id=?", (row['id'],))
                    continue
                current = file_hash(row['stock_file'])
                if current == row['before_hash']:
                    if file_hash(row['staged_file']) != row['after_hash']:
                        raise WarrantyError('File kho bảo hành tạm không khớp. Cần admin kiểm tra.')
                    os.replace(row['staged_file'], row['stock_file'])
                elif current != row['after_hash']:
                    raise WarrantyError('Kho đã thay đổi khi đang cấp bảo hành. Tạm dừng để tránh giao trùng; liên hệ admin.')
                db.execute("UPDATE claims SET state='ready' WHERE id=?", (row['id'],))

    def allocate(self, claim_id, buyer=None, admin_id=None):
        self.recover_allocations()
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('''
                SELECT c.*, d.buyer, d.account_type, d.steam_game 
                FROM claims c JOIN deliveries d ON c.code=d.code 
                WHERE c.id=?
            ''', (claim_id,)).fetchone()
            if not row:
                raise WarrantyError('Không tìm thấy yêu cầu bảo hành.')
            if buyer is not None and row['buyer'] != buyer:
                raise WarrantyError('Yêu cầu bảo hành không thuộc về bạn.')
            if row['state'] in ('ready', 'approved'):
                return json.loads(row['replacements'])
            if row['state'] == 'rejected':
                raise WarrantyError('Yêu cầu này đã bị từ chối.')
            if (row['attempt'] or 1) >= 3:
                raise WarrantyError('Lần bảo hành thứ 3 cần Admin check tay và bù acc.')

            # CS2 Prime và PUBG Plus: Bắt buộc Admin check tay và bù acc thủ công
            if row['account_type'] in ('cs2_prime', 'pubg_plus'):
                raise WarrantyError('Đơn hàng CS2 Prime và PUBG Plus bắt buộc Admin phải check tay và bù acc thủ công.')

            needed = db.execute('SELECT COUNT(*) FROM claim_items WHERE claim_id=?', (claim_id,)).fetchone()[0]
            source_path = self.stock_path(row['account_type'])
            if not source_path or not Path(source_path).exists():
                return []

            # Bảo hành acc Steam: Bù đúng game khách đã mua và đúng gói
            if str(row['account_type']).startswith('steam_tier_'):
                steam_game = row['steam_game'] or ''
                from utils.steam_storage import allocate_steam_accounts
                replacements = allocate_steam_accounts(
                    game_query=steam_game,
                    tier_id=row['account_type'],
                    quantity=needed,
                    file_path=str(source_path)
                )
                if len(replacements) < needed:
                    return []
                selected = [a['raw_line'] for a in replacements]
                now = time.time()
                db.execute("UPDATE claims SET state='prepared', replacements=?, stock_file=?, staged_file=NULL, before_hash=NULL, after_hash=NULL, admin_id=?, resolved_at=? WHERE id=?",
                           (json.dumps(selected), str(source_path), admin_id, now, claim_id))
                db.execute("UPDATE claims SET state='approved' WHERE id=? AND state='prepared'", (claim_id,))
                return selected

            target_path = str(source_path) + '.warranty-' + claim_id + '.tmp'
            before = file_hash(source_path)
            from Modules.AccountProcess import split_raw_accounts
            with open(source_path, 'r', encoding='utf-8') as source:
                content = source.read()
            all_accs = split_raw_accounts(content)
            if len(all_accs) < needed:
                return []
            selected = all_accs[:needed]
            remaining = all_accs[needed:]
            is_log_format = "---------------------------" in content or any("Username:" in a for a in all_accs)
            with open(target_path, 'w', encoding='utf-8', newline='\n') as target:
                for acc in remaining:
                    if is_log_format:
                        target.write(acc + "\n---------------------------\n")
                    else:
                        target.write(acc + "\n")
                target.flush()
                os.fsync(target.fileno())
            now = time.time()
            db.execute("UPDATE claims SET state='prepared', replacements=?, stock_file=?, staged_file=?, before_hash=?, after_hash=?, admin_id=?, resolved_at=? WHERE id=?",
                       (json.dumps(selected), str(source_path), target_path, before, file_hash(target_path), admin_id, now, claim_id))
        self.recover_allocations()
        with self.connection() as db:
            db.execute("UPDATE claims SET state='approved' WHERE id=? AND state='ready'", (claim_id,))
        return selected

    def allocate_manual(self, claim_id, replacements, admin_id=None, note=""):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM claims WHERE id=?', (claim_id,)).fetchone()
            if not row:
                raise WarrantyError('Không tìm thấy yêu cầu bảo hành.')
            if row['state'] in ('ready', 'approved'):
                raise WarrantyError('Yêu cầu này đã được duyệt trước đó.')
            if row['state'] == 'rejected':
                raise WarrantyError('Yêu cầu này đã bị từ chối trước đó.')
            needed = db.execute('SELECT COUNT(*) FROM claim_items WHERE claim_id=?', (claim_id,)).fetchone()[0]
            if len(replacements) != needed or any(not a.strip() for a in replacements):
                raise WarrantyError(f'Cần nhập đúng {needed} acc thay thế.')
            db.execute('''
                UPDATE claims 
                SET state='approved', replacements=?, admin_id=?, admin_note=?, resolved_at=? 
                WHERE id=?
            ''', (json.dumps(replacements, ensure_ascii=False), admin_id, note[:1000], time.time(), claim_id))

    def reject_claim(self, claim_id, admin_id=None, reason=""):
        with self.connection() as db:
            row = db.execute('SELECT * FROM claims WHERE id=?', (claim_id,)).fetchone()
            if not row:
                raise WarrantyError('Không tìm thấy yêu cầu bảo hành.')
            if row['state'] in ('ready', 'approved'):
                raise WarrantyError('Yêu cầu này đã được duyệt trước đó.')
            if row['state'] == 'rejected':
                raise WarrantyError('Yêu cầu này đã bị từ chối trước đó.')
            db.execute('''
                UPDATE claims 
                SET state='rejected', admin_id=?, admin_note=?, resolved_at=? 
                WHERE id=?
            ''', (admin_id, reason[:1000], time.time(), claim_id))

