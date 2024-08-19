import discord
from redbot.core import commands, Config
import uuid
import json
import os
from datetime import datetime
from pytz import timezone

class Manager(commands.Cog):
    """Manage product delivery and stock."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        default_global = {
            "stock": {},
            "log_channel_id": None,
            "restricted_roles": [],
            "grant_permissions": [],
            "purchase_history": {}
        }
        self.config.register_global(**default_global)
        default_server = {
            "stock": {},
            "purchase_history": {}
        }
        self.config.register_guild(**default_server)

        # Create settings.json in the specified directory if it doesn't exist
        settings_path = "/home/container/.local/share/Red-DiscordBot/data/pterodactyl/cogs/Manager/settings.json"
        if not os.path.exists(settings_path):
            os.makedirs(os.path.dirname(settings_path), exist_ok=True)
            with open(settings_path, "w") as f:
                json.dump(default_global, f)

    def get_ist_time(self):
        """Return current time in IST."""
        ist = timezone('Asia/Kolkata')
        return datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

    async def is_allowed(ctx):
        roles = await ctx.cog.config.restricted_roles()
        if not roles:
            return True
        return any(role.id in roles for role in ctx.author.roles)

    async def has_grant_permissions(ctx):
        return any(role.id in await ctx.cog.config.grant_permissions() for role in ctx.author.roles)

    def generate_uuid(self):
        return str(uuid.uuid4())[:4].upper()

    def create_embed(self, title, description, fields=None, footer=None, image_url=None):
        """Helper method to create embeds."""
        embed = discord.Embed(title=title, description=description, color=discord.Color.purple())
        if fields:
            for name, value in fields.items():
                embed.add_field(name=name, value=value, inline=False)
        if footer:
            embed.set_footer(text=footer)
        if image_url:
            embed.set_image(url=image_url)
        return embed

    @commands.command()
    async def deliver(self, ctx, member: discord.Member, product: str, quantity: int, price: float, *, custom_text: str):
        """Deliver a product to a member with a custom message."""
        if quantity <= 0 or price <= 0:
            await ctx.send("Quantity and price must be greater than zero.")
            return
        
        stock = await self.config.stock()
        guild_stock = await self.config.guild(ctx.guild).stock()

        if product not in guild_stock or guild_stock[product]['quantity'] < quantity:
            await ctx.send(f"Insufficient stock for {product}.")
            return

        # Deduct the quantity from server-specific stock
        guild_stock[product]['quantity'] -= quantity
        if guild_stock[product]['quantity'] <= 0:
            del guild_stock[product]
        await self.config.guild(ctx.guild).stock.set(guild_stock)

        # Calculate amount in INR and USD
        amount_inr = price * quantity
        usd_exchange_rate = 83.2  # Exchange rate from INR to USD
        amount_usd = amount_inr / usd_exchange_rate

        # Prepare the embed
        uuid_code = self.generate_uuid()
        purchase_date = self.get_ist_time()

        fields = {
            "Here is your product": f"> {product}",
            "Amount": f"> ₹{amount_inr:.2f} (INR) / ${amount_usd:.2f} (USD)",
            "Purchase Date": f"> {purchase_date}",
            "Product info and credentials": f"||```{custom_text}```||"
        }
        footer = f"Vouch format: +rep {ctx.author.name} {quantity}x {product} | No vouch, no warranty"
        image_url = "https://media.discordapp.net/attachments/1271370383735394357/1271370426655703142/931f5b68a813ce9d437ec11b04eec649.jpg"

        embed = self.create_embed(
            title="__Frenzy Store__",
            description="Here is your product",
            fields=fields,
            footer=footer,
            image_url=image_url
        )

        try:
            await member.send(embed=embed)
            await ctx.send(f"Product delivered to {member.mention} via DM.")
        except discord.Forbidden:
            await ctx.send(f"Failed to deliver the product to {member.mention}. They may have DMs disabled.")
        
        # Log the delivery
        await self.log_event(ctx, f"Delivered {quantity}x {product} to {member.mention} at ₹{amount_inr:.2f} (INR) / ${amount_usd:.2f} (USD)")

        # Record the purchase in history
        purchase_history = await self.config.guild(ctx.guild).purchase_history()
        purchase_record = {
            "product": product,
            "quantity": quantity,
            "price": price,
            "custom_text": custom_text,
            "timestamp": purchase_date,
            "sold_by": ctx.author.name
        }
        if str(member.id) not in purchase_history:
            purchase_history[str(member.id)] = []
        purchase_history[str(member.id)].append(purchase_record)
        await self.config.guild(ctx.guild).purchase_history.set(purchase_history)

    @commands.command()
    async def stock(self, ctx):
        """Display available stock."""
        guild_stock = await self.config.guild(ctx.guild).stock()
        if not guild_stock:
            await ctx.send("No stock available.")
            return

        embed = discord.Embed(
            title="Available Stock",
            color=discord.Color.green()
        )

        for idx, (product, info) in enumerate(guild_stock.items(), start=1):
            amount_inr = info['price']
            usd_exchange_rate = 83.2  # Exchange rate from INR to USD
            amount_usd = amount_inr / usd_exchange_rate
            embed.add_field(
                name=f"{idx}. {product}",
                value=f"> **Quantity:** {info['quantity']}\n> **Price:** ₹{amount_inr:.2f} (INR) / ${amount_usd:.2f} (USD)",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command()
    @commands.check(is_allowed)
    async def addproduct(self, ctx, product: str, quantity: int, price: float, emoji: str):
        """Add a product to the stock."""
        if quantity <= 0 or price <= 0:
            await ctx.send("Quantity and price must be greater than zero.")
            return

        guild_stock = await self.config.guild(ctx.guild).stock()
        if product in guild_stock:
            guild_stock[product]['quantity'] += quantity
            guild_stock[product]['price'] = price
            guild_stock[product]['emoji'] = emoji
        else:
            guild_stock[product] = {"quantity": quantity, "price": price, "emoji": emoji}
        await self.config.guild(ctx.guild).stock.set(guild_stock)
        
        fields = {
            "Product": f"> {product} {emoji}",
            "Quantity": f"> {quantity}",
            "Price": f"> ₹{price:.2f} (INR) / ${price / 83.2:.2f} (USD)"
        }
        embed = self.create_embed(
            title="Product Added",
            description="The product has been added to the stock.",
            fields=fields
        )
        await ctx.send(embed=embed)

        # Log the addition
        await self.log_event(ctx, f"Added {quantity}x {product} to the stock at ₹{price:.2f} (INR) / ${price / 83.2:.2f} (USD)")

    @commands.command()
    @commands.check(is_allowed)
    async def removeproduct(self, ctx, product: str):
        """Remove a product from the stock."""
        guild_stock = await self.config.guild(ctx.guild).stock()
        if product not in guild_stock:
            await ctx.send(f"{product} not found in stock.")
            return

        del guild_stock[product]
        await self.config.guild(ctx.guild).stock.set(guild_stock)

        embed = discord.Embed(
            title="Product Removed",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Product",
            value=f"> {product}",
            inline=False
        )
        await ctx.send(embed=embed)

        # Log the removal
        await self.log_event(ctx, f"Removed {product} from the stock.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setlogchannel(self, ctx, channel: discord.TextChannel):
        """Set the log channel."""
        await self.config.log_channel_id.set(channel.id)
        embed = discord.Embed(
            title="Log Channel Set",
            description=f"The log channel has been set to {channel.mention}.",
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)

    async def log_event(self, ctx, message):
        log_channel_id = await self.config.log_channel_id()
        if not log_channel_id:
            return

        log_channel = self.bot.get_channel(log_channel_id)
        if not log_channel:
            return

        embed = discord.Embed(
            title="Event Log",
            description=message,
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"Logged by {ctx.author.name} at {self.get_ist_time()}")
        await log_channel.send(embed=embed)

    @commands.command()
    async def viewhistory(self, ctx, user_id: int = None):
        """View purchase history for a specified user or yourself."""
        user_id = str(user_id) if user_id else str(ctx.author.id)
        purchase_history = await self.config.guild(ctx.guild).purchase_history()
        user_history = purchase_history.get(user_id, [])

        if not user_history:
            await ctx.send("No data found.")
            return

        embed = discord.Embed(
            title="Purchase History",
            color=discord.Color.gold()
        )

        for record in user_history:
            amount_inr = record['price']
            usd_exchange_rate = 83.2
            amount_usd = amount_inr / usd_exchange_rate
            embed.add_field(
                name=f"Product: {record['product']}",
                value=f"> **Quantity:** {record['quantity']}\n> **Price:** ₹{amount_inr:.2f} (INR) / ${amount_usd:.2f} (USD)\n> **Date:** {record['timestamp']}\n> **Custom Text:** ||```{record['custom_text']}```||\n> **Sold By:** {record['sold_by']}",
                inline=False
            )

        await ctx.send(embed=embed)
