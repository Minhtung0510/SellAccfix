import os
from pathlib import Path

from dotenv import load_dotenv


def run_bot(*, test_mode=False):
    import sys
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    base_dir = Path(__file__).resolve().parent
    env_path = base_dir / '.env'
    if not env_path.exists() and (base_dir.parent / '.env').exists():
        env_path = base_dir.parent / '.env'
    load_dotenv(env_path)
    # The launcher selects the mode, even if .env still contains an old value.
    os.environ['PAYMENT_TEST_MODE'] = 'true' if test_mode else 'false'

    token = os.getenv('DISCORD_TOKEN', '').strip()
    if not token:
        raise RuntimeError('DISCORD_TOKEN chưa được cấu hình trong .env')
    if not test_mode:
        required = ('BANK_CODE', 'ACCOUNT_NO', 'ACCOUNT_NAME', 'WEB2M_PASSWORD', 'WEB2M_TOKEN')
        missing = [key for key in required if not os.getenv(key, '').strip()]
        if missing:
            raise RuntimeError('Thiếu cấu hình thanh toán: ' + ', '.join(missing)
                               + '. Để chạy thử không cần ngân hàng, dùng: python test_bot.py')

    import discord
    from core.bot import Bot
    from Modules import pay

    pay.load_config()
    print('[TEST] Chỉ admin tạo đơn miễn thanh toán; acc vẫn trừ từ kho.' if test_mode
          else '[LIVE] Thanh toán thật. Chế độ test đã tắt.')
    intents = discord.Intents.none()
    intents.guilds = True
    bot = Bot(intents=intents)
    bot.run(token)


if __name__ == '__main__':
    run_bot()
