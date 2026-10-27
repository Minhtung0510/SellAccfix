import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
import discord
from core.bot import Bot
from cogs.accounts import LOAI_CHOICES


class CommandSyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_removes_only_stale_account_command_after_global_sync(self):
        old = SimpleNamespace(name='add_account', type=discord.AppCommandType.chat_input,
                              options=[SimpleNamespace(name='loai', choices=[SimpleNamespace(name='2k', value='2k')])],
                              delete=AsyncMock())
        other = SimpleNamespace(name='menu', delete=AsyncMock())
        bot = SimpleNamespace(_global_commands_synced=True, _checked_command_guilds=set(),
                              tree=SimpleNamespace(fetch_commands=AsyncMock(return_value=[old, other])))
        guild = SimpleNamespace(id=123)
        await Bot._remove_stale_account_command(bot, guild)
        old.delete.assert_awaited_once()
        other.delete.assert_not_awaited()
        await Bot._remove_stale_account_command(bot, guild)
        bot.tree.fetch_commands.assert_awaited_once()

    async def test_leaves_current_guild_command(self):
        current = SimpleNamespace(name='add_account', type=discord.AppCommandType.chat_input,
                                  options=[SimpleNamespace(name='loai', choices=LOAI_CHOICES)], delete=AsyncMock())
        bot = SimpleNamespace(_global_commands_synced=True, _checked_command_guilds=set(),
                              tree=SimpleNamespace(fetch_commands=AsyncMock(return_value=[current])))
        await Bot._remove_stale_account_command(bot, SimpleNamespace(id=123))
        current.delete.assert_not_awaited()

    async def test_never_deletes_when_global_sync_failed(self):
        bot = SimpleNamespace(_global_commands_synced=False, _checked_command_guilds=set(),
                              tree=SimpleNamespace(fetch_commands=AsyncMock()))
        await Bot._remove_stale_account_command(bot, SimpleNamespace(id=123))
        bot.tree.fetch_commands.assert_not_awaited()
