import discord
from discord.ext import commands
from ui.views import AccountView
from ui.warranty import (
    WarrantyButton,
    ApproveStockWarrantyButton,
    ApproveManualWarrantyButton,
    RejectWarrantyButton,
)
from ui.check_acc import CheckAccButton
from ui.feedback import FeedbackButton
from utils.warranty import WarrantyStore

class Bot(commands.Bot):
    def __init__(self, **kwargs):
        intents = kwargs.pop("intents", discord.Intents.default())
        super().__init__(command_prefix=kwargs.pop("command_prefix", ()), intents=intents, max_messages=None,
                         member_cache_flags=discord.MemberCacheFlags.none())
        self._global_commands_synced = False
        self._checked_command_guilds = set()
        self._cogs_to_load = [
            "cogs.admin",
            "cogs.accounts",
            "cogs.orders",
        ]

    async def setup_hook(self) -> None:
        self.warranty_store = WarrantyStore()
        self.warranty_store.recover_allocations()
        self.add_dynamic_items(
            WarrantyButton,
            CheckAccButton,
            FeedbackButton,
            ApproveStockWarrantyButton,
            ApproveManualWarrantyButton,
            RejectWarrantyButton,
        )
        # Persistent view cho Select menu
        self.add_view(AccountView())
        self.add_view(AccountView(current_game="steam"))
        for ext in self._cogs_to_load:
            await self.load_extension(ext)
        try:
            synced = await self.tree.sync()
            self._global_commands_synced = any(command.name == "add_account" for command in synced)
            print(f"Synced {len(synced)} slash command(s)")
            from cogs.accounts import LOAI_CHOICES
            print("/add_account: " + " | ".join(choice.value for choice in LOAI_CHOICES))
        except Exception as e:
            print(f"Slash sync error: {e}")

    async def _remove_stale_account_command(self, guild):
        # Global sync does not remove old guild-specific commands that shadow it.
        # Fetching via this tree only returns commands owned by this application.
        if not self._global_commands_synced or guild.id in self._checked_command_guilds:
            return
        from cogs.accounts import LOAI_CHOICES
        expected = [(choice.name, choice.value) for choice in LOAI_CHOICES]
        try:
            for command in await self.tree.fetch_commands(guild=guild):
                if command.name != "add_account" or command.type != discord.AppCommandType.chat_input:
                    continue
                option = next((option for option in command.options if option.name == "loai"), None)
                actual = [(choice.name, choice.value) for choice in option.choices] if option else []
                if actual != expected:
                    await command.delete()
                    print(f"Server {guild.id}: removed outdated guild /add_account; using synced global choices.")
            self._checked_command_guilds.add(guild.id)
        except discord.HTTPException as exc:
            print(f"Server {guild.id}: could not check legacy /add_account (HTTP {exc.status}).")

    async def _ensure_guild_emojis(self, guild):
        import os
        from utils.constants import VALORANT_LOGO_PATH, CS2_LOGO_PATH, STEAM_LOGO_PATH
        me = guild.me
        if not (me and me.guild_permissions.manage_emojis_and_stickers):
            return
        v_emoji = discord.utils.get(guild.emojis, name="dtff_valorant")
        if not v_emoji and os.path.exists(VALORANT_LOGO_PATH):
            try:
                with open(VALORANT_LOGO_PATH, "rb") as f:
                    await guild.create_custom_emoji(name="dtff_valorant", image=f.read())
            except Exception as e:
                print(f"Không thể tạo emoji dtff_valorant trên server {guild.name}: {e}")
        c_emoji = discord.utils.get(guild.emojis, name="dtff_cs2")
        if not c_emoji and os.path.exists(CS2_LOGO_PATH):
            try:
                with open(CS2_LOGO_PATH, "rb") as f:
                    await guild.create_custom_emoji(name="dtff_cs2", image=f.read())
            except Exception as e:
                print(f"Không thể tạo emoji dtff_cs2 trên server {guild.name}: {e}")
        s_emoji = discord.utils.get(guild.emojis, name="dtff_steam")
        if not s_emoji and os.path.exists(STEAM_LOGO_PATH):
            try:
                with open(STEAM_LOGO_PATH, "rb") as f:
                    await guild.create_custom_emoji(name="dtff_steam", image=f.read())
            except Exception as e:
                print(f"Không thể tạo emoji dtff_steam trên server {guild.name}: {e}")

    async def on_ready(self):
        print(f"Bot is online as {self.user} | application ID: {self.application_id}")
        for guild in self.guilds:
            await self._remove_stale_account_command(guild)
            await self._ensure_guild_emojis(guild)

    async def on_guild_join(self, guild):
        await self._remove_stale_account_command(guild)
        await self._ensure_guild_emojis(guild)
