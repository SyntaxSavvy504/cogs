import asyncio
import sqlite3
import uuid
from typing import Optional, Literal
from discord import Embed, File, Member
from redbot.core import Config, checks, commands
from redbot.core.data_manager import cog_data_path
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

class Manager(commands.Cog):
    """
    Manage product delivery and stock.
    """

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 123456789012345678)  # Unique identifier
        self.config.register_global(log_channel=None, set_role=None)
        self.config.register_guild(stock=[], ignore_roles=[], log_channel=None)
        self.db = sqlite3.connect("sqlitecloud://cxghu5vjik.sqlite.cloud:8860?apikey=SMuTVFyDkbis4918QwBKoWhCI7NluTal0LGPPLdaymU")
        self.cursor = self.db.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS stock
                               (product TEXT, quantity INTEGER, price REAL, emoji TEXT)''')
        self.db.commit()

    @commands.command()
    async def deliver(self, ctx: commands.Context, quantity: int, price: float, product: str, *, text: str) -> None:
        """Deliver a product to a member via DM."""
        user = ctx.author
        delivery_id = str(uuid.uuid4())[:4]
        embed = Embed(title="Product Delivery", description=f"**Product**: {product}\n**Quantity**: {quantity}\n**Price**: ${price}\n**Details**: {text}",
                      color=0x00ff00)
        embed.set_footer(text=f"Vouch for product. No vouch, no warranty. ID: {delivery_id}")
        embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar.url)
        try:
            await user.send(embed=embed)
            await ctx.send(f"Product delivery has been sent to {user.mention}.")
        except Exception as e:
            await ctx.send(f"Failed to send DM to {user.mention}.")
            print(f"Error sending DM: {e}")

    @commands.command()
    async def stockinfo(self, ctx: commands.Context) -> None:
        """Show advanced stock info."""
        stock_list = self.cursor.execute("SELECT rowid, product, quantity, price, emoji FROM stock").fetchall()
        if not stock_list:
            await ctx.send("No stock available.")
            return
        embed = Embed(title="Stock Information", color=0x00ff00)
        for idx, (rowid, product, quantity, price, emoji) in enumerate(stock_list, 1):
            embed.add_field(name=f"#{idx}: {product} {emoji}", value=f"**Quantity**: {quantity}\n**Price**: ${price}", inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    @checks.has_permissions(manage_guild=True)
    async def addproduct(self, ctx: commands.Context, product: str, quantity: int, price: float, emoji: str) -> None:
        """Add a product to the stock."""
        self.cursor.execute("INSERT INTO stock (product, quantity, price, emoji) VALUES (?, ?, ?, ?)",
                            (product, quantity, price, emoji))
        self.db.commit()
        await ctx.send(f"Product `{product}` added to stock.")

    @commands.command()
    @checks.has_permissions(manage_guild=True)
    async def removeproduct(self, ctx: commands.Context, product: str) -> None:
        """Remove a product from the stock."""
        self.cursor.execute("DELETE FROM stock WHERE product = ?", (product,))
        self.db.commit()
        await ctx.send(f"Product `{product}` removed from stock.")

    @commands.command()
    @checks.has_permissions(manage_guild=True)
    async def setrole(self, ctx: commands.Context, role: Optional[commands.RoleConverter]) -> None:
        """Set a role that can use the delivery commands."""
        if role:
            await self.config.guild(ctx.guild).set_role.set(role.id)
            await ctx.send(f"Only members with the role {role.mention} can use the delivery commands.")
        else:
            await self.config.guild(ctx.guild).set_role.clear()
            await ctx.send("Delivery commands can be used by everyone.")

    @commands.command()
    @checks.has_permissions(manage_guild=True)
    async def setlogchannel(self, ctx: commands.Context, channel: Optional[commands.TextChannelConverter]) -> None:
        """Set a channel for logging events."""
        if channel:
            await self.config.log_channel.set(channel.id)
            await ctx.send(f"Log channel set to {channel.mention}.")
        else:
            await self.config.log_channel.clear()
            await ctx.send("Log channel cleared.")

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context):
        log_channel_id = await self.config.log_channel()
        if log_channel_id:
            log_channel = self.bot.get_channel(log_channel_id)
            if log_channel:
                embed = Embed(title="Command Executed", description=f"**Command**: {ctx.command}\n**User**: {ctx.author}\n**Channel**: {ctx.channel}\n**Message**: {ctx.message.content}",
                              color=0x00ff00)
                await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: commands.Message):
        """Check for role restrictions for delivery commands."""
        if message.author.bot:
            return
        set_role_id = await self.config.guild(message.guild).set_role()
        if set_role_id:
            set_role = message.guild.get_role(set_role_id)
            if set_role not in message.author.roles:
                return
        if message.content.startswith("!deliver") or message.content.startswith("!stockinfo"):
            if message.channel.permissions_for(message.guild.me).send_messages:
                await message.channel.send("Command restricted to specific roles.")

    async def cog_unload(self):
        self.db.close()
