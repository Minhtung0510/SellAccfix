"""Buyer-only, persistent feedback entry point and public review cards."""
import logging
import sqlite3

import discord

from utils.constants import ACCOUNT_TYPE_NAME
from utils.storage import get_feedback_channel_id
from utils.warranty import WarrantyError

log = logging.getLogger(__name__)


def build_feedback_embed(order, rating, comment, display_name, avatar_url=None):
    embed = discord.Embed(
        title='Cảm nhận từ khách hàng',
        description=f"{'⭐' * rating}{'☆' * (5 - rating)}  **{rating}/5**\n\n"
                    + discord.utils.escape_markdown(discord.utils.escape_mentions(comment.strip())),
        color=0x2ECC71, timestamp=discord.utils.utcnow(),
    )
    author = {'name': display_name}
    if avatar_url:
        author['icon_url'] = avatar_url
    embed.set_author(**author)
    embed.add_field(name='🎮 Sản phẩm', value=ACCOUNT_TYPE_NAME.get(order['account_type'], order['account_type']), inline=False)
    embed.set_footer(text='DTFF SHOP • 🧪 Đánh giá thử nghiệm' if order.get('test_order')
                     else 'DTFF SHOP • ✓ Đã nhận hàng')
    return embed


def init_feedback(store):
    with store.connection() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS feedback (
            code TEXT PRIMARY KEY REFERENCES deliveries(code),
            rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            comment TEXT NOT NULL, message_id INTEGER, channel_id INTEGER NOT NULL
        )''')


def check_feedback(store, code, buyer):
    order = store.order(code, buyer)
    init_feedback(store)
    with store.connection() as db:
        if db.execute('SELECT 1 FROM feedback WHERE code=?', (code,)).fetchone():
            raise WarrantyError('Đơn này đã gửi đánh giá hoặc đang được đăng. Mỗi đơn chỉ đánh giá một lần.')
    return order


def reserve_feedback(store, code, buyer, rating, comment, channel_id):
    order = check_feedback(store, code, buyer)
    if rating not in range(1, 6) or not comment.strip() or len(comment) > 1000:
        raise WarrantyError('Chọn từ 1–5 sao và nhập nhận xét tối đa 1000 ký tự.')
    try:
        with store.connection() as db:
            db.execute('INSERT INTO feedback(code,rating,comment,channel_id) VALUES(?,?,?,?)',
                       (code, rating, comment.strip(), channel_id))
    except sqlite3.IntegrityError as exc:
        raise WarrantyError('Đơn này đã gửi đánh giá. Mỗi đơn chỉ đánh giá một lần.') from exc
    return order


class FeedbackModal(discord.ui.Modal):
    def __init__(self, code):
        super().__init__(title='Đánh giá đơn hàng', timeout=600)
        self.code = code
        self.rating = discord.ui.TextInput(label='Số sao (1–5)', placeholder='5', min_length=1, max_length=1)
        self.comment = discord.ui.TextInput(
            label='Nhận xét công khai', style=discord.TextStyle.paragraph,
            placeholder='Trải nghiệm của bạn? Không ghi tài khoản hoặc mật khẩu tại đây.',
            min_length=1, max_length=1000,
        )
        self.add_item(self.rating)
        self.add_item(self.comment)

    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = interaction.client.warranty_store
        reserved = False
        sent = False
        try:
            rating_text = self.rating.value.strip()
            if rating_text not in ('1', '2', '3', '4', '5'):
                raise WarrantyError('Số sao phải là một số từ 1 đến 5.')
            channel_id = get_feedback_channel_id()
            if not channel_id:
                raise WarrantyError('Shop chưa cài kênh feedback. Vui lòng báo admin.')
            channel = interaction.client.get_channel(channel_id) or await interaction.client.fetch_channel(channel_id)
            order = reserve_feedback(store, self.code, interaction.user.id,
                                     int(rating_text), self.comment.value, channel_id)
            reserved = True
            avatar = getattr(interaction.user, 'display_avatar', None)
            embed = build_feedback_embed(order, int(rating_text), self.comment.value,
                                         interaction.user.display_name, str(avatar.url) if avatar else None)
            message = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            sent = True
            with store.connection() as db:
                db.execute('UPDATE feedback SET message_id=? WHERE code=?', (message.id, self.code))
        except WarrantyError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        except Exception:
            log.exception('Feedback publish failed for %s', self.code)
            if reserved and not sent:
                with store.connection() as db:
                    db.execute('DELETE FROM feedback WHERE code=? AND message_id IS NULL', (self.code,))
            await interaction.followup.send(
                'Feedback đã đăng, nhưng lưu trạng thái gặp lỗi. Vui lòng báo admin.' if sent else
                'Chưa đăng được feedback. Vui lòng báo admin kiểm tra kênh và thử lại.', ephemeral=True)
            return
        await interaction.followup.send('✅ Cảm ơn bạn! Feedback đã được đăng lên kênh của shop.', ephemeral=True)


class FeedbackButton(discord.ui.DynamicItem[discord.ui.Button], template=r'feedback:(?P<code>[A-Za-z0-9_-]{1,64})'):
    def __init__(self, code):
        super().__init__(discord.ui.Button(label='Đánh giá', emoji='⭐', style=discord.ButtonStyle.secondary,
                                          custom_id=f'feedback:{code}'))
        self.code = code

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match['code'])

    async def callback(self, interaction):
        try:
            check_feedback(interaction.client.warranty_store, self.code, interaction.user.id)
            if not get_feedback_channel_id():
                raise WarrantyError('Shop chưa cài kênh feedback. Vui lòng báo admin.')
            await interaction.response.send_modal(FeedbackModal(self.code))
        except WarrantyError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
