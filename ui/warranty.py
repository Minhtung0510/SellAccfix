"""Warranty interactions: persistent order button, paged account selection, file uploads, manual admin approval."""
import hashlib
import io
import logging
import os
import re
from pathlib import Path

import discord

from utils.constants import ACCOUNT_TYPE_NAME
from utils.storage import get_warranty_channel_id, load_admin_ids
from utils.warranty import WarrantyError

log = logging.getLogger('discord.warranty')
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_BATCH_BYTES = 100 * 1024 * 1024


def media_extension(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return '.png'
    if data.startswith(b'\xff\xd8\xff'):
        return '.jpg'
    if data.startswith((b'GIF87a', b'GIF89a')):
        return '.gif'
    if data[:4] == b'RIFF' and data[8:12] in (b'WEBP', b'AVI '):
        return '.webp' if data[8:12] == b'WEBP' else '.avi'
    if data[4:8] == b'ftyp':
        return '.mp4'
    if data.startswith(b'\x1a\x45\xdf\xa3'):
        return '.webm'
    raise WarrantyError('Chỉ nhận ảnh PNG/JPG/GIF/WebP hoặc video MP4/MOV/WebM/AVI.')


async def save_evidence(attachments, folder):
    if not attachments or len(attachments) > 10:
        raise WarrantyError('Cần tải từ 1 đến 10 ảnh/video mỗi đợt.')
    if any(a.size <= 0 or a.size > MAX_FILE_BYTES for a in attachments):
        raise WarrantyError('Mỗi file phải có dữ liệu và không quá 25 MB.')
    if sum(a.size for a in attachments) > MAX_BATCH_BYTES:
        raise WarrantyError('Tổng file mỗi đợt không quá 100 MB; hãy chia thành nhiều đợt.')
    Path(folder).mkdir(parents=True, exist_ok=True)
    evidence = []
    seen = set()
    for attachment in attachments:
        data = await attachment.read()
        if not data or len(data) > MAX_FILE_BYTES:
            raise WarrantyError('File trống hoặc vượt 25 MB.')
        extension = media_extension(data)
        digest = hashlib.sha256(data).hexdigest()
        if digest in seen:
            raise WarrantyError('Không dùng cùng một ảnh/video cho nhiều acc.')
        seen.add(digest)
        target = Path(folder) / (digest + extension)
        if not target.exists():
            temporary = target.with_suffix(extension + '.tmp')
            with temporary.open('wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        evidence.append({'hash': digest, 'path': str(target)})
        del data
    return evidence


def _clean_acc_display(raw_text):
    m_u = re.search(r'Username:\s*([^\r\n]+)', raw_text, re.IGNORECASE)
    m_p = re.search(r'Password:\s*([^\r\n]+)', raw_text, re.IGNORECASE)
    if m_u and m_p:
        return f"{m_u.group(1).strip()}:{m_p.group(1).strip()}"
    return raw_text.strip().splitlines()[0] if raw_text.strip() else ""


def warranty_embed(order, claim, accounts):
    rows = [f"Acc #{position} → {_clean_acc_display(account)}" for position, account in zip(claim['positions'], accounts)]
    text = '\n'.join(rows)
    as_file = len(text) + 8 > 1024 or '`' in text
    embed = discord.Embed(title='🛡️ TÀI KHOẢN BẢO HÀNH', color=0x2ECC71,
                          description='Acc thay thế miễn phí, đúng loại của đơn đã mua.')
    embed.set_author(name='DTFF SHOP • BẢO HÀNH')
    embed.add_field(name='🎮 Loại tài khoản', value=ACCOUNT_TYPE_NAME.get(order['account_type'], order['account_type']), inline=False)
    embed.add_field(name='🔄 Lượt bảo hành', value=f"{claim.get('attempt', 1)}/3", inline=True)
    embed.add_field(name='📦 Số lượng đổi', value=str(len(accounts)), inline=True)
    embed.add_field(name='🧾 Đơn gốc', value=order['code'], inline=True)
    embed.add_field(name='🔑 Acc thay thế', value='Danh sách và số thứ tự acc gốc nằm trong file TXT đính kèm.' if as_file else f'```\n{text}\n```', inline=False)
    embed.set_footer(text='Bảo hành tối đa 3 lượt • Lượt 3 Admin check tay • Giữ riêng thông tin đăng nhập')
    return embed, text if as_file else None


async def send_claim_result(interaction, store, code, claim_id):
    """Fallback helper retained for compatibility."""
    order = store.order(code, interaction.user.id)
    accounts = store.allocate(claim_id, interaction.user.id)
    if not accounts:
        await interaction.followup.send('🕒 Đã lưu yêu cầu và bằng chứng. Đang chờ duyệt.', ephemeral=True)
        return
    orders_cog = interaction.client.get_cog('OrdersCog')
    if orders_cog:
        orders_cog.request_menu_refresh()
    claim = next(c for c in store.claims(code, interaction.user.id) if c['id'] == claim_id)
    embed, file_text = warranty_embed(order, claim, accounts)
    if file_text is None:
        await interaction.followup.send(embed=embed, view=delivery_warranty_view(code, claim_id), ephemeral=True)
    else:
        attachment = discord.File(io.BytesIO(file_text.encode('utf-8')), filename=f'bao-hanh-{claim_id[:8]}.txt')
        try:
            await interaction.followup.send(embed=embed, file=attachment, view=delivery_warranty_view(code, claim_id), ephemeral=True)
        finally:
            attachment.close()


async def notify_replacement(client, claim, embed, file_text):
    async def send(target, **kwargs):
        attachment = None
        if file_text is not None:
            attachment = discord.File(io.BytesIO(file_text.encode('utf-8')), filename=f"bao-hanh-{claim['id'][:8]}.txt")
            kwargs['file'] = attachment
        try:
            await target.send(embed=embed, view=delivery_warranty_view(claim['code'], claim['id']), **kwargs)
        finally:
            if attachment:
                attachment.close()

    channel_id = claim.get('ticket_channel_id')
    if channel_id:
        try:
            channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
            await send(channel, content=f"<@{claim['buyer']}>")
        except Exception:
            log.exception('Failed to deliver warranty %s to ticket', claim['id'])
    try:
        user = await client.fetch_user(claim['buyer'])
        await send(user)
    except Exception:
        log.exception('Failed to DM warranty %s', claim['id'])


async def send_warranty_to_admin_channel(client, code, claim_id):
    """Sends the warranty claim card to the designated Admin Warranty Channel."""
    admin_channel_id = get_warranty_channel_id()
    if not admin_channel_id:
        log.warning("Chưa cấu hình kênh Admin để nhận duyệt bảo hành (WARRANTY_CHANNEL_ID).")
        return False

    admin_channel = client.get_channel(admin_channel_id)
    if not admin_channel:
        try:
            admin_channel = await client.fetch_channel(admin_channel_id)
        except Exception:
            log.error("Không thể tìm thấy kênh Admin Warranty Channel ID: %s", admin_channel_id)
            return False

    claim = client.warranty_store.get_claim(claim_id)
    if not claim:
        return False

    current_order = client.warranty_store.order(code, claim['buyer'])
    claim['order_accounts'] = current_order['current_accounts']
    claimed_strs = []
    for p in claim['positions']:
        if 0 < p <= len(claim['order_accounts']):
            claimed_strs.append(f"#{p} • `{_clean_acc_display(claim['order_accounts'][p-1])}`")

    attempt = claim.get('attempt') or 1
    acc_type = claim.get('account_type', '')
    is_rare = acc_type in ('cs2_prime', 'pubg_plus')

    if is_rare:
        embed = discord.Embed(
            title=f"👑 PHIẾU BẢO HÀNH HÀNG HIẾM ({ACCOUNT_TYPE_NAME.get(acc_type, acc_type)}) • #{code}",
            description="👑 **ĐÂY LÀ ĐƠN HÀNG HÀNG HIẾM (CS2 PRIME / PUBG PLUS)!**\n"
                        "Loại tài khoản này có giá trị cao và khó tìm hơn, hệ thống **không tự động trừ kho**.\n"
                        "👉 **Admin vui lòng check tay tài khoản sống rồi bấm [Check tay & Bù acc] để gửi cho khách.**",
            color=0x9B59B6
        )
    elif attempt >= 3:
        embed = discord.Embed(
            title=f"🚨 PHIẾU BẢO HÀNH (LẦN 3 - CHẠM NGƯỠNG) • #{code}",
            description="🚨 **ĐƠN HÀNG NÀY ĐÃ ĐỔI 2 LẦN TRƯỚC ĐÓ NHƯNG VẪN LỖI!**\n"
                        "Hệ thống đã **KHÓA nút duyệt từ kho** để bảo vệ kho của shop.\n"
                        "👉 **Admin vui lòng check tay 1 acc sống 100% rồi bấm [Check tay & Bù acc] hoặc bấm [Từ chối].**",
            color=0xE74C3C
        )
    elif attempt == 2:
        embed = discord.Embed(
            title=f"⚠️ PHIẾU BẢO HÀNH (LẦN 2) • #{code}",
            description="⚠️ **Acc bù lần 1 của khách báo lỗi tiếp.**\n"
                        "Khuyến nghị Admin nên kiểm tra kỹ kho hoặc check tay trước khi duyệt.",
            color=0xE67E22
        )
    else:
        embed = discord.Embed(
            title=f"🛡️ PHIẾU BẢO HÀNH CẦN DUYỆT • #{code}",
            description="Khách hàng vừa gửi yêu cầu bảo hành. Vui lòng kiểm tra bằng chứng và duyệt.",
            color=0xF39C12
        )

    embed.add_field(name="👤 Khách hàng", value=f"<@{claim['buyer']}> (`{claim['buyer']}`)", inline=True)
    embed.add_field(name="🧾 Mã đơn", value=f"`{code}`", inline=True)
    embed.add_field(name="🎮 Loại tài khoản", value=ACCOUNT_TYPE_NAME.get(acc_type, acc_type), inline=True)
    if claim.get('steam_game'):
        embed.add_field(name="🎯 Tựa game mua", value=f"**{claim['steam_game']}**", inline=True)
    embed.add_field(name="⚠️ Acc báo lỗi", value="\n".join(claimed_strs) or "Không xác định", inline=False)
    embed.add_field(name="📝 Lý do khách báo", value=claim['note'] or "Không có ghi chú", inline=False)

    if claim.get('previous_history'):
        hist_lines = []
        for h in claim['previous_history']:
            att_n = h.get('attempt') or '?'
            for r in h.get('replacements', []):
                hist_lines.append(f"• Acc bù đợt trước (Lần {att_n}): `{_clean_acc_display(r)}`")
        if hist_lines:
            embed.add_field(name="📜 Lịch sử các acc bù trước đó", value="\n".join(hist_lines), inline=False)

    ticket_chan_id = claim.get('ticket_channel_id')
    if ticket_chan_id:
        embed.add_field(name="📍 Kênh Ticket", value=f"<#{ticket_chan_id}>", inline=True)
    else:
        embed.add_field(name="📍 Nơi mua", value="DM Bot", inline=True)

    embed.set_footer(text=f"Mã claim: {claim_id} • Đợt bảo hành: {attempt}/3 • Chỉ Admin mới có quyền thao tác")

    files = []
    image_attached = False
    for idx, item in enumerate(claim['evidence']):
        p = Path(item['evidence_path'])
        if p.is_file():
            ext = p.suffix.lower()
            fname = f"proof_{idx}{ext}"
            files.append(discord.File(str(p), filename=fname))
            if not image_attached and ext in ('.png', '.jpg', '.jpeg', '.webp'):
                embed.set_image(url=f"attachment://{fname}")
                image_attached = True

    view = AdminWarrantyActionView(claim_id, attempt=attempt, account_type=acc_type)
    await admin_channel.send(embed=embed, files=files, view=view)
    return True



class EvidenceModal(discord.ui.Modal):
    def __init__(self, code, buyer, positions, panel=None):
        super().__init__(title='Bằng chứng tài khoản lỗi', timeout=600)
        self.code, self.buyer, self.positions = code, buyer, list(positions)
        self.panel = panel
        self.upload = discord.ui.FileUpload(required=True, min_values=len(positions), max_values=len(positions))
        self.add_item(discord.ui.Label(text=f'Tải {len(positions)} ảnh/video cho {len(positions)} acc',
                                      description='1 file / acc, theo thứ tự đã chọn. Mỗi file ≤25 MB, tổng ≤100 MB.', component=self.upload))
        self.note = discord.ui.TextInput(style=discord.TextStyle.paragraph, required=True, max_length=1000,
                                         placeholder='Ví dụ: acc #1 sai mật khẩu, acc #3 không đăng nhập được.')
        self.add_item(discord.ui.Label(text='Mô tả lỗi và số thứ tự acc', component=self.note))

    async def on_submit(self, interaction):
        if interaction.user.id != self.buyer:
            await interaction.response.send_message('Yêu cầu không thuộc về bạn.', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = interaction.client.warranty_store
        try:
            order = store.order(self.code, self.buyer, require_active=True)
            if len(self.upload.values) != len(self.positions):
                raise WarrantyError('Số ảnh/video phải bằng số acc đã chọn.')
            evidence = await save_evidence(self.upload.values, store.path.parent / 'warranty_evidence')
            
            from utils.storage import is_ticket_channel
            ticket_channel_id = None
            if interaction.channel and is_ticket_channel(interaction.channel.id):
                ticket_channel_id = interaction.channel.id
            elif order.get('channel_id'):
                ticket_channel_id = order.get('channel_id')

            claim_id = store.create_claim(self.code, self.buyer, self.positions, evidence,
                                          note=self.note.value, ticket_channel_id=ticket_channel_id)

            # 1. Ephemeral response to the buyer: ONLY says waiting for admin approval
            await interaction.followup.send(
                f"⏳ **Yêu cầu bảo hành cho đơn `{self.code}` đã được gửi thành công!**\n"
                f"**Trạng thái:** *Đang đợi Admin xét duyệt...*\n"
                f"Admin sẽ kiểm tra hình ảnh bằng chứng và xử lý cho bạn sớm nhất.",
                ephemeral=True
            )

            # 2. In Ticket channel (if applicable), send a clean waiting notification (NO buttons)
            if interaction.channel and is_ticket_channel(interaction.channel.id):
                ticket_embed = discord.Embed(
                    title="🛡️ YÊU CẦU BẢO HÀNH ĐÃ ĐƯỢC TIẾP NHẬN",
                    description=f"Khách hàng <@{self.buyer}> vừa gửi yêu cầu bảo hành cho đơn `{self.code}`.\n"
                                f"**Trạng thái:** ⏳ *Đang đợi Admin xét duyệt...*",
                    color=0xF39C12
                )
                ticket_embed.add_field(name="📦 Mã đơn", value=f"`{self.code}`", inline=True)
                ticket_embed.add_field(name="🎮 Loại acc", value=ACCOUNT_TYPE_NAME.get(order['account_type'], order['account_type']), inline=True)
                if order.get('steam_game'):
                    ticket_embed.add_field(name="🎯 Game", value=f"**{order['steam_game']}**", inline=True)
                ticket_embed.add_field(name="📝 Ghi chú lỗi", value=self.note.value[:400] or "Không có", inline=False)
                ticket_embed.set_footer(text="Vui lòng đợi Admin kiểm tra bằng chứng và duyệt yêu cầu.")
                try:
                    await interaction.channel.send(embed=ticket_embed)
                except Exception:
                    pass

            # 3. Send ticket card to Admin Warranty Channel (with evidence image and Approve/Reject buttons)
            sent_admin = await send_warranty_to_admin_channel(interaction.client, self.code, claim_id)
            if not sent_admin:
                log.warning("Đơn bảo hành %s chưa thể gửi vào kênh Admin (chưa set kênh hoặc bot thiếu quyền).", self.code)

            if self.panel is not None and interaction.message is not None:
                self.panel.refresh()
                try:
                    await interaction.message.edit(content=self.panel.summary(), view=self.panel)
                except discord.HTTPException:
                    pass

        except WarrantyError as exc:
            await interaction.followup.send(f'❗ {exc}', ephemeral=True)
        except Exception:
            log.exception('Warranty submit failed for order %s', self.code)
            await interaction.followup.send('Đã lưu yêu cầu của bạn. Admin sẽ kiểm tra đơn bảo hành này.', ephemeral=True)


class AccountPicker(discord.ui.Select):
    def __init__(self, panel, options):
        super().__init__(placeholder='Chọn tối đa 10 acc lỗi trong trang này',
                         min_values=1, max_values=min(10, len(options)), options=options)
        self.panel = panel

    async def callback(self, interaction):
        self.panel.selected = sorted(int(v) for v in self.values)
        await interaction.response.edit_message(content=self.panel.summary(), view=self.panel)


class WarrantyPanel(discord.ui.View):
    def __init__(self, store, code, buyer):
        super().__init__(timeout=600)
        self.store, self.code, self.buyer = store, code, buyer
        self.page = 0
        self.selected = []
        self.refresh()

    async def interaction_check(self, interaction):
        if interaction.user.id == self.buyer:
            return True
        await interaction.response.send_message('Bảng này không thuộc về bạn.', ephemeral=True)
        return False

    def refresh(self):
        self.order = self.store.order(self.code, self.buyer)
        for child in list(self.children):
            if isinstance(child, AccountPicker):
                self.remove_item(child)

        pending_positions = self.order.get('pending_positions', set())
        approved_counts = self.order.get('approved_counts', {})
        # An account is eligible for warranty if it is not currently pending review and has been approved < 3 times
        available = [
            (i, account) for i, account in enumerate(self.order.get('current_accounts', self.order['accounts']), 1)
            if i not in pending_positions and approved_counts.get(i, 0) < 3
        ]
        self.pages = max(1, (len(available) + 24) // 25)
        self.page = min(max(0, self.page), self.pages - 1)


        def _get_acc_label(acc_text, index):
            m = re.search(r'Username:\s*([^\r\n]+)', acc_text, re.IGNORECASE)
            uname = m.group(1).strip()[:50] if m else (acc_text.strip().splitlines()[0].split(':', 1)[0][:50] if acc_text.strip() else "")
            att_cnt = approved_counts.get(index, 0)
            tag = f" (Lần {att_cnt + 1})" if att_cnt > 0 else ""
            return f"#{index}{tag} • {uname}"


        # If only 1 account in entire order, auto-select it for maximum simplicity
        if len(available) == 1:
            self.selected = [available[0][0]]
        else:
            self.selected = []

        options = [discord.SelectOption(label=_get_acc_label(account, i), value=str(i))
                   for i, account in available[self.page * 25:(self.page + 1) * 25]]
        if options and len(available) > 1:
            picker = AccountPicker(self, options)
            picker.row = 0
            self.add_item(picker)

        self.previous.disabled = self.page == 0
        self.next_page.disabled = self.page >= self.pages - 1
        self.upload_button.disabled = not available

    def summary(self):
        kind = ACCOUNT_TYPE_NAME[self.order['account_type']]
        selected = ', '.join(f'#{p}' for p in self.selected) or 'Chưa chọn'
        total_accounts = len(self.order['accounts'])
        used_count = len(self.order.get('pending_positions', set()) | {p for p, count in self.order.get('approved_counts', {}).items() if count >= 3})
        return (f"🛡️ **Bảo hành {kind}** · Đơn `{self.code}`\n"
                f"Hạn gửi yêu cầu: <t:{int(self.order['expires_at'])}:f> (<t:{int(self.order['expires_at'])}:R>).\n"
                f"**Trang {self.page + 1}/{self.pages}** · Đã khóa/chờ duyệt: {used_count}/{total_accounts} acc\n"
                f"Đã chọn: **{selected}**\n"
                "Tải ảnh/video bằng chứng → Admin duyệt → Nhận acc thay thế.\n"
                "💡 *Hệ thống hỗ trợ bảo hành tối đa 3 lần nếu acc bù gặp sự cố.*")


    @discord.ui.button(label='Trang trước', style=discord.ButtonStyle.secondary, row=1)
    async def previous(self, interaction, button):
        self.page -= 1
        self.refresh()
        await interaction.response.edit_message(content=self.summary(), view=self)

    @discord.ui.button(label='Trang sau', style=discord.ButtonStyle.secondary, row=1)
    async def next_page(self, interaction, button):
        self.page += 1
        self.refresh()
        await interaction.response.edit_message(content=self.summary(), view=self)

    @discord.ui.button(label='Tải bằng chứng', emoji='📎', style=discord.ButtonStyle.primary, row=1)
    async def upload_button(self, interaction, button):
        try:
            self.store.order(self.code, self.buyer, require_active=True)
            if not self.selected:
                raise WarrantyError('Hãy chọn các acc lỗi trước khi tải bằng chứng.')
            await interaction.response.send_modal(EvidenceModal(self.code, self.buyer, self.selected, panel=self))
        except WarrantyError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)

    @discord.ui.button(label='Trạng thái / Đã gửi', emoji='📦', style=discord.ButtonStyle.success, row=2)
    async def history(self, interaction, button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            claims = self.store.claims(self.code, self.buyer)
            if not claims:
                await interaction.followup.send('Bạn chưa gửi yêu cầu bảo hành nào cho đơn này.', ephemeral=True)
                return

            embed = discord.Embed(
                title=f"📋 LỊCH SỬ BẢO HÀNH • ĐƠN #{self.code}",
                color=0x3498DB
            )
            lines = []
            files_to_send = []
            for idx, claim in enumerate(claims, 1):
                st = claim.get('state')
                c_time = f"<t:{int(claim['created_at'])}:R>"
                pos_str = ', '.join(f'#{p}' for p in claim['positions'])
                if st == 'pending':
                    embed.add_field(
                        name=f"Yêu cầu #{idx} ({pos_str}) • {c_time}",
                        value="⏳ **Trạng thái:** Đang đợi Admin xét duyệt.\n*Vui lòng kiên nhẫn chờ Admin kiểm tra.*",
                        inline=False
                    )
                elif st == 'rejected':
                    reason = claim.get('admin_note') or "Không có lý do chi tiết."
                    embed.add_field(
                        name=f"Yêu cầu #{idx} ({pos_str}) • {c_time}",
                        value=f"❌ **Trạng thái:** Bị từ chối.\n**Lý do:** {reason}",
                        inline=False
                    )
                elif st in ('ready', 'approved'):
                    replacements = claim.get('replacements') or []
                    if not replacements:
                        replacements = self.store.allocate(claim['id'], self.buyer)
                    acc_lines = "\n".join(f"Acc #{pos} → {_clean_acc_display(acc)}" for pos, acc in zip(claim['positions'], replacements))
                    embed.add_field(
                        name=f"Yêu cầu #{idx} ({pos_str}) • {c_time}",
                        value=f"✅ **Trạng thái:** Đã duyệt!\n```\n{acc_lines}\n```",
                        inline=False
                    )
                    lines.extend(f"Yêu cầu {claim['id']} | {ACCOUNT_TYPE_NAME[self.order['account_type']]}")
                    lines.extend(f"Acc #{pos} -> {acc}" for pos, acc in zip(claim['positions'], replacements))

            if lines:
                attachment = discord.File(io.BytesIO('\n'.join(lines).encode('utf-8')), filename=f'bao-hanh-{self.code}.txt')
                await interaction.followup.send(embed=embed, file=attachment, ephemeral=True)
                attachment.close()
            else:
                await interaction.followup.send(embed=embed, ephemeral=True)

        except WarrantyError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
        except Exception:
            log.exception('Warranty retrieval failed for order %s', self.code)
            await interaction.followup.send('Chưa lấy được kết quả. Vui lòng liên hệ Admin.', ephemeral=True)
        finally:
            self.refresh()
            try:
                await interaction.message.edit(content=self.summary(), view=self)
            except discord.HTTPException:
                pass


# =========================================================
# ADMIN CONTROLS (Manual Approval & Rejection)
# =========================================================

class ManualWarrantyModal(discord.ui.Modal):
    def __init__(self, claim_id, original_message):
        super().__init__(title='Bù tài khoản thủ công', timeout=600)
        self.claim_id = claim_id
        self.original_message = original_message
        self.acc_input = discord.ui.TextInput(
            label="Tài khoản thay thế (User:Pass hoặc log)",
            style=discord.TextStyle.paragraph,
            required=True,
            placeholder="Dán thông tin tài khoản bù tại đây..."
        )
        self.add_item(self.acc_input)
        self.note_input = discord.ui.TextInput(
            label="Ghi chú gửi kèm cho khách (tùy chọn)",
            style=discord.TextStyle.short,
            required=False,
            placeholder="VD: Shop bù cho bạn acc VIP hơn..."
        )
        self.add_item(self.note_input)

    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = interaction.client.warranty_store
        claim = store.get_claim(self.claim_id)
        if not claim:
            await interaction.followup.send("❌ Không tìm thấy yêu cầu bảo hành.", ephemeral=True)
            return

        from Modules.AccountProcess import split_raw_accounts
        raw_text = self.acc_input.value.strip()
        repl_accs = split_raw_accounts(raw_text)
        if not repl_accs:
            repl_accs = [raw_text]

        try:
            store.allocate_manual(self.claim_id, repl_accs, admin_id=interaction.user.id, note=self.note_input.value)
        except WarrantyError as exc:
            await interaction.followup.send(f"⚠️ {exc}", ephemeral=True)
            return

        # Update Admin Channel message
        try:
            if self.original_message:
                embed = self.original_message.embeds[0]
                embed.color = 0x2ECC71
                embed.title = f"🛡️ PHIẾU BẢO HÀNH • ĐÃ DUYỆT (NHẬP TAY) • #{claim['code']}"
                embed.add_field(
                    name="✅ Kết quả",
                    value=f"Đã duyệt và cấp {len(repl_accs)} acc (bù tay) bởi <@{interaction.user.id}>\n**Ghi chú:** {self.note_input.value or 'Không có'}",
                    inline=False
                )
                await self.original_message.edit(embed=embed, view=None)
        except Exception as e:
            log.warning("Không thể cập nhật tin nhắn Admin: %s", e)

        # Notify Customer in Ticket Channel
        cust_embed, file_text = warranty_embed(
            dict(code=claim['code'], account_type=claim['account_type']),
            claim,
            repl_accs
        )
        if self.note_input.value:
            cust_embed.add_field(name="💬 Lời nhắn từ Shop", value=self.note_input.value, inline=False)

        await notify_replacement(interaction.client, claim, cust_embed, file_text)

        await interaction.followup.send(f"✅ Đã duyệt và gửi acc bù thủ công cho <@{claim['buyer']}>!", ephemeral=True)


class RejectWarrantyModal(discord.ui.Modal):
    def __init__(self, claim_id, original_message):
        super().__init__(title='Từ chối bảo hành', timeout=600)
        self.claim_id = claim_id
        self.original_message = original_message
        self.reason_input = discord.ui.TextInput(
            label="Lý do từ chối",
            style=discord.TextStyle.paragraph,
            required=True,
            placeholder="VD: Ảnh không khớp, acc đã bị đổi pass sau khi nhận..."
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = interaction.client.warranty_store
        claim = store.get_claim(self.claim_id)
        if not claim:
            await interaction.followup.send("❌ Không tìm thấy yêu cầu bảo hành.", ephemeral=True)
            return

        reason = self.reason_input.value.strip()
        try:
            store.reject_claim(self.claim_id, admin_id=interaction.user.id, reason=reason)
        except WarrantyError as exc:
            await interaction.followup.send(f"⚠️ {exc}", ephemeral=True)
            return

        # Update Admin Channel message
        try:
            if self.original_message:
                embed = self.original_message.embeds[0]
                embed.color = 0xE74C3C
                embed.title = f"🛡️ PHIẾU BẢO HÀNH • ĐÃ TỪ CHỐI • #{claim['code']}"
                embed.add_field(
                    name="❌ Kết quả",
                    value=f"Đã từ chối bởi <@{interaction.user.id}>\n**Lý do:** {reason}",
                    inline=False
                )
                await self.original_message.edit(embed=embed, view=None)
        except Exception as e:
            log.warning("Không thể cập nhật tin nhắn Admin: %s", e)

        # Notify Customer in Ticket Channel
        rej_embed = discord.Embed(
            title="❌ YÊU CẦU BẢO HÀNH BỊ TỪ CHỐI",
            description=f"Yêu cầu bảo hành cho đơn `{claim['code']}` của bạn đã bị Admin từ chối.",
            color=0xE74C3C
        )
        rej_embed.add_field(name="📝 Lý do từ Admin", value=reason, inline=False)
        rej_embed.set_footer(text="Nếu có thắc mắc, vui lòng trao đổi trực tiếp với Admin tại ticket này.")

        ticket_chan_id = claim.get('ticket_channel_id')
        if ticket_chan_id:
            chan = interaction.client.get_channel(ticket_chan_id)
            if chan:
                try:
                    await chan.send(content=f"<@{claim['buyer']}>", embed=rej_embed)
                except Exception:
                    pass

        try:
            user = await interaction.client.fetch_user(claim['buyer'])
            if user:
                await user.send(embed=rej_embed)
        except Exception:
            pass

        await interaction.followup.send(f"❌ Đã từ chối yêu cầu của <@{claim['buyer']}>.", ephemeral=True)


class ApproveStockWarrantyButton(discord.ui.DynamicItem[discord.ui.Button], template=r'w_app_stock:(?P<claim_id>[A-Za-z0-9_-]{1,64})'):
    def __init__(self, claim_id):
        super().__init__(discord.ui.Button(
            label="Duyệt (Từ kho)",
            emoji="✅",
            style=discord.ButtonStyle.success,
            custom_id=f"w_app_stock:{claim_id}"
        ))
        self.claim_id = claim_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match['claim_id'])

    async def callback(self, interaction):
        if interaction.user.id not in load_admin_ids():
            await interaction.response.send_message("❌ Bạn không có quyền duyệt bảo hành!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        store = interaction.client.warranty_store
        claim = store.get_claim(self.claim_id)
        if not claim:
            await interaction.followup.send("❌ Không tìm thấy yêu cầu bảo hành.", ephemeral=True)
            return

        if claim.get('account_type') in ('cs2_prime', 'pubg_plus'):
            await interaction.followup.send(
                "👑 Đơn hàng CS2 Prime và PUBG Plus là hàng hiếm, hệ thống bắt buộc Admin phải check tay!\n"
                "Vui lòng bấm nút **[Check tay & Bù acc]** để gửi acc cho khách.",
                ephemeral=True
            )
            return

        if claim.get('attempt', 1) >= 3:
            await interaction.followup.send(
                "🚨 Đơn này đã bảo hành đến lần thứ 3! Hệ thống đã khóa duyệt từ kho tự động.\n"
                "Vui lòng dùng nút **[Check tay & Bù acc]** để giao acc sống chuẩn cho khách.",
                ephemeral=True
            )
            return

        if claim['state'] in ('ready', 'approved'):
            await interaction.followup.send("⚠️ Yêu cầu bảo hành này đã được duyệt trước đó rồi!", ephemeral=True)
            return
        if claim['state'] == 'rejected':
            await interaction.followup.send("⚠️ Yêu cầu bảo hành này đã bị từ chối trước đó!", ephemeral=True)
            return

        try:
            accounts = store.allocate(self.claim_id, buyer=claim['buyer'], admin_id=interaction.user.id)
        except WarrantyError as exc:
            await interaction.followup.send(f"⚠️ {exc}", ephemeral=True)
            return

        if not accounts:
            game_hint = f" có game **{claim.get('steam_game')}**" if claim.get('steam_game') else ""
            await interaction.followup.send(
                f"❌ Kho hiện không còn đủ tài khoản{game_hint} thuộc gói này để bù!\n"
                "Vui lòng nạp thêm acc vào kho rồi bấm duyệt lại, hoặc bấm nút **[Duyệt (Nhập tay)]** để bù acc khác.",
                ephemeral=True
            )
            return

        # Update Admin Channel message
        try:
            if interaction.message:
                embed = interaction.message.embeds[0]
                embed.color = 0x2ECC71
                embed.title = f"🛡️ PHIẾU BẢO HÀNH • ĐÃ DUYỆT (KHO) • #{claim['code']}"
                embed.add_field(
                    name="✅ Kết quả",
                    value=f"Đã duyệt và cấp {len(accounts)} acc từ kho bởi <@{interaction.user.id}>",
                    inline=False
                )
                await interaction.message.edit(embed=embed, view=None)
        except Exception as e:
            log.warning("Không thể cập nhật tin nhắn Admin: %s", e)

        # Notify Customer in Ticket Channel
        cust_embed, file_text = warranty_embed(
            dict(code=claim['code'], account_type=claim['account_type']),
            claim,
            accounts
        )

        await notify_replacement(interaction.client, claim, cust_embed, file_text)

        orders_cog = interaction.client.get_cog('OrdersCog')
        if orders_cog:
            orders_cog.request_menu_refresh()

        await interaction.followup.send(f"✅ Đã duyệt và gửi {len(accounts)} acc cho <@{claim['buyer']}>!", ephemeral=True)


class ApproveManualWarrantyButton(discord.ui.DynamicItem[discord.ui.Button], template=r'w_app_man:(?P<claim_id>[A-Za-z0-9_-]{1,64})'):
    def __init__(self, claim_id, label="Duyệt (Nhập tay)"):
        super().__init__(discord.ui.Button(
            label=label,
            emoji="✏️",
            style=discord.ButtonStyle.primary,
            custom_id=f"w_app_man:{claim_id}"
        ))
        self.claim_id = claim_id
        self.label = label

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match['claim_id'])

    async def callback(self, interaction):
        if interaction.user.id not in load_admin_ids():
            await interaction.response.send_message("❌ Bạn không có quyền duyệt bảo hành!", ephemeral=True)
            return

        store = interaction.client.warranty_store
        claim = store.get_claim(self.claim_id)
        if not claim:
            await interaction.response.send_message("❌ Không tìm thấy yêu cầu bảo hành.", ephemeral=True)
            return
        if claim['state'] in ('ready', 'approved'):
            await interaction.response.send_message("⚠️ Yêu cầu này đã được duyệt rồi!", ephemeral=True)
            return
        if claim['state'] == 'rejected':
            await interaction.response.send_message("⚠️ Yêu cầu này đã bị từ chối rồi!", ephemeral=True)
            return

        await interaction.response.send_modal(ManualWarrantyModal(self.claim_id, interaction.message))


class RejectWarrantyButton(discord.ui.DynamicItem[discord.ui.Button], template=r'w_rej:(?P<claim_id>[A-Za-z0-9_-]{1,64})'):
    def __init__(self, claim_id):
        super().__init__(discord.ui.Button(
            label="Từ chối",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            custom_id=f"w_rej:{claim_id}"
        ))
        self.claim_id = claim_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match['claim_id'])

    async def callback(self, interaction):
        if interaction.user.id not in load_admin_ids():
            await interaction.response.send_message("❌ Bạn không có quyền duyệt bảo hành!", ephemeral=True)
            return

        store = interaction.client.warranty_store
        claim = store.get_claim(self.claim_id)
        if not claim:
            await interaction.response.send_message("❌ Không tìm thấy yêu cầu bảo hành.", ephemeral=True)
            return
        if claim['state'] in ('ready', 'approved'):
            await interaction.response.send_message("⚠️ Yêu cầu này đã được duyệt rồi!", ephemeral=True)
            return
        if claim['state'] == 'rejected':
            await interaction.response.send_message("⚠️ Yêu cầu này đã bị từ chối rồi!", ephemeral=True)
            return

        await interaction.response.send_modal(RejectWarrantyModal(self.claim_id, interaction.message))


class AdminWarrantyActionView(discord.ui.View):
    def __init__(self, claim_id, attempt=1, account_type=None):
        super().__init__(timeout=None)
        is_rare = account_type in ("cs2_prime", "pubg_plus")
        if attempt >= 3 or is_rare:
            label = "Check tay & Bù acc (Hàng hiếm)" if is_rare else "Check tay & Bù acc"
            self.add_item(ApproveManualWarrantyButton(claim_id, label=label))
            self.add_item(RejectWarrantyButton(claim_id))
        else:
            self.add_item(ApproveStockWarrantyButton(claim_id))
            self.add_item(ApproveManualWarrantyButton(claim_id))
            self.add_item(RejectWarrantyButton(claim_id))



# =========================================================
# CUSTOMER ENTRY POINT (Persistent Button on Delivery Card)
# =========================================================

class WarrantyButton(discord.ui.DynamicItem[discord.ui.Button], template=r'warranty:(?P<code>[A-Za-z0-9_-]{1,64})'):
    def __init__(self, code):
        super().__init__(discord.ui.Button(label='Bảo hành', emoji='🛡️', style=discord.ButtonStyle.primary,
                                           custom_id=f'warranty:{code}'))
        self.code = code

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match['code'])

    async def callback(self, interaction):
        try:
            panel = WarrantyPanel(interaction.client.warranty_store, self.code, interaction.user.id)
            await interaction.response.send_message(panel.summary(), view=panel, ephemeral=True)
        except WarrantyError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)


def delivery_warranty_view(code, claim_id=None):
    from ui.check_acc import CheckAccButton
    from ui.feedback import FeedbackButton
    view = discord.ui.View(timeout=None)
    view.add_item(CheckAccButton(code, claim_id))
    view.add_item(WarrantyButton(code))
    view.add_item(FeedbackButton(code))
    return view
