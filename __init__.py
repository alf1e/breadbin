import sqlite3

import discord
from discord import app_commands
from discord.ext import commands

import breadcord
from breadcord.module import ModuleCog


class ModMailView(discord.ui.View):
    def __init__(self, cursor, message: discord.Message, bot: breadcord.Bot) -> None:
        super().__init__(timeout=300)

        self.cursor = cursor
        self.message = message
        self.config = bot.settings.breadbin
        self.bot = bot

    @discord.ui.button(label="Open ModMail", style=discord.ButtonStyle.primary)
    async def open_modmail(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Opened ModMail")

        # create channel in category
        category = self.bot.get_channel(self.config.modmail_category.value)
        guild = self.bot.get_guild(self.config.modmail_guild_id.value)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.get_role(self.config.modmail_role_id.value): discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        channel = await guild.create_text_channel(
            name=f"modmail-{self.message.author.name}",
            category=category,
            overwrites=overwrites
        )
        response = discord.Embed(
            title=f"ModMail | {self.message.author.name}",
            description=f"**Reason:** {self.message.content}",
            colour=discord.Colour.blurple()
        )

        await channel.send(embed=response)
        self.cursor.execute(
            "INSERT INTO modmail (reason, channel, user_id) VALUES (?, ?, ?)",
            (self.message.content, channel.id, self.message.author.id)
        )

    @discord.ui.button(label="Cancel ModMail", style=discord.ButtonStyle.danger)
    async def cancel_modmail(self, interaction: discord.Interaction, button: discord.ui.Button):
        return await interaction.response.send_message("Cancelled ModMail")


class BreadBin(breadcord.module.ModuleCog):
    def __init__(self, name: str | None = None) -> None:
        super().__init__(name)

        self.module_settings = self.bot.settings.breadbin
        self.connection = sqlite3.connect(self.module.storage_path / "modmail.db")
        self.cursor = self.connection.cursor()
        self.cursor.execute(
            "CREATE TABLE IF NOT EXISTS modmail ("
            "   id INTEGER PRIMARY KEY NOT NULL UNIQUE,"
            "   reason INTEGER NOT NULL,"
            "   channel INTEGER NOT NULL,"
            "   user_id INTEGER NOT NULL"
            ")"
        )

    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="ModMail | DM me to open a ticket!"))

    @ModuleCog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not message.guild:
            if channel := self.cursor.execute("SELECT channel FROM modmail WHERE user_id = ?",
                                              (message.author.id,)).fetchone():
                await self.bot.get_channel(channel[0]).send(f"**{message.author.name}** > {message.content}")
                self.connection.commit()
            else:
                await message.channel.send(view=ModMailView(self.cursor, message, self.bot))
                self.connection.commit()

        else:
            for modmail in self.cursor.execute("SELECT channel, user_id FROM modmail").fetchall():
                if message.content == "!close":
                    return
                if modmail[0] == message.channel.id:
                    await self.bot.get_user(modmail[1]).send(f"**STAFF** > {message.content}")
            self.connection.commit()

    @commands.command()
    async def close(self, ctx: commands.Context):
        if not await self.bot.is_owner(ctx.author):
            raise breadcord.errors.NotAdministratorError

        for i in ctx.author.roles:
            if i.id == self.module_settings.modmail_role_id.value:
                break
        else:
            return

        if user := self.cursor.execute("SELECT user_id FROM modmail WHERE channel = ?", (ctx.channel.id,)).fetchone():
            await ctx.send("ModMail closed")
            await ctx.channel.delete(reason="ModMail closed")
            self.cursor.execute("DELETE FROM modmail WHERE channel = ?", (ctx.channel.id,))
            await self.bot.get_user(user[0]).send("Your ModMail has been closed")

            self.connection.commit()
        else:
            await ctx.send("You don't have an open ModMail")


async def setup(bot: breadcord.Bot):
    await bot.add_cog(BreadBin("breadbin"))
