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
            "log_channel_id": None,
            "restricted_roles": [],
            "grant_permissions": [],
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

    @commands.command()
    async def deliver(self, ctx, member: discord.Member, product: str, quantity: int, price: float, *, custom_text: str):
        """Deliver a product to a member with a custom message."""
        guild_stock = await self.config.guild(ctx.guild).stock()

        if product in guild_stock and guild_stock[product]['quantity'] >= quantity:
            # Prepare the embed
            uuid_code = self.generate_uuid()
            purchase_date = self.get_ist_time()
            guild_owner = ctx.guild.owner.mention

            embed = discord.Embed(
                title="__Frenzy Store__",
                color=discord.Color.purple()
            )
            embed.set_author(name="Frenzy Store", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
            embed.add_field(name="Here is your product", value=f"> {product} {guild_stock[product].get('emoji', '')}", inline=False)
            embed.add_field(name="Amount", value=f"> ₹{price * quantity:.2f} (INR) / ${(price * quantity) / 83.2:.2f} (USD)", inline=False)
            embed.add_field(name="Purchase Date", value=f"> {purchase_date}", inline=False)
            embed.add_field(name="\u200b", value="**- follow our [TOS](https://discord.com/channels/911622571856891934/911629489325355049) & be a smart buyer!\n- [CLICK HERE](https://discord.com/channels/911622571856891934/1134197532868739195) to leave your __feedback__**", inline=False)
            embed.add_field(name="Product info and credentials", value=f"||```{custom_text}```||", inline=False)
            embed.add_field(name="Vouch Format", value=f"> +rep {guild_owner} {quantity}x {product} ₹{price * quantity:.2f} LEGIT", inline=False)
            embed.set_footer(text=f"Vouch format: +rep {ctx.author.name} {quantity}x {product} | No vouch, no warranty")
            embed.set_image(url="https://media.discordapp.net/attachments/1271370383735394357/1271370426655703142/931f5b68a813ce9d437ec11b04eec649.jpg")

            # Try to send the embed to the user's DM
            dm_channel = member.dm_channel or await member.create_dm()
            try:
                await dm_channel.send(embed=embed)
                await ctx.send(f"Product `{product}` delivered to {member.mention} via DM. {self.get_ist_time()}")

                # Deduct the quantity from server-specific stock
                guild_stock[product]['quantity'] -= quantity
                if guild_stock[product]['quantity'] <= 0:
                    del guild_stock[product]
                await self.config.guild(ctx.guild).stock.set(guild_stock)

                # Log the delivery
                await self.log_event(ctx, f"Delivered {quantity}x {product} to {member.mention} at ₹{price * quantity:.2f} (INR) / ${(price * quantity) / 83.2:.2f} (USD)")

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

            except discord.Forbidden as e:
                await ctx.send(f"Failed to deliver the product `{product}` to {member.mention}. Reason: {str(e)}")
        else:
            await ctx.send(f"Insufficient stock for `{product}`.")

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
                name=f"{idx}. {product} {info.get('emoji', '')}",
                value=f"> **Quantity:** {info['quantity']}\n> **Price:** ₹{amount_inr:.2f} (INR) / ${amount_usd:.2f} (USD)",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command()
    @commands.check(is_allowed)
    async def addproduct(self, ctx, product: str, quantity: int, price: float, emoji: str):
        """Add a product to the stock."""
        guild_stock = await self.config.guild(ctx.guild).stock()
        if product in guild_stock:
            guild_stock[product]['quantity'] += quantity
            guild_stock[product]['price'] = price
            guild_stock[product]['emoji'] = emoji
        else:
            guild_stock[product] = {"quantity": quantity, "price": price, "emoji": emoji}
        await self.config.guild(ctx.guild).stock.set(guild_stock)
        embed = discord.Embed(
            title="Product Added",
            color=discord.Color.teal()
        )
        embed.add_field(
            name="Product",
            value=f"> {product} {emoji}",
            inline=False
        )
        embed.add_field(
            name="Quantity",
            value=f"> {quantity}",
            inline=False
        )
        embed.add_field(
            name="Price",
            value=f"> ₹{price:.2f} (INR) / ${price / 83.2:.2f} (USD)",
            inline=False
        )
        await ctx.send(embed=embed)

        # Log the addition
        await self.log_event(ctx, f"Added {quantity}x {product} to the stock at ₹{price:.2f} (INR) / ${price / 83.2:.2f} (USD)")

    @commands.command()
    @commands.check(is_allowed)
    async def removeproduct(self, ctx, product: str, quantity: int):
        """Remove a specific quantity of a product from the stock."""
        guild_stock = await self.config.guild(ctx.guild).stock()
        if product in guild_stock:
            if guild_stock[product]['quantity'] >= quantity:
                guild_stock[product]['quantity'] -= quantity
                if guild_stock[product]['quantity'] <= 0:
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
                await self.log_event(ctx, f"Removed {quantity}x {product} from the stock.")
            else:
                await ctx.send(f"Cannot remove more {product} than available in stock.")
        else:
            await ctx.send(f"{product} not found in stock.")

    @commands.command()
    @commands.check(is_allowed)
    async def updateprice(self, ctx, product: str, price: float):
        """Update the price of an existing product."""
        guild_stock = await self.config.guild(ctx.guild).stock()
        if product in guild_stock:
            old_price = guild_stock[product]['price']
            guild_stock[product]['price'] = price
            await self.config.guild(ctx.guild).stock.set(guild_stock)
            await ctx.send(f"Price of `{product}` updated from ₹{old_price:.2f} to ₹{price:.2f} (INR).")
            # Log the price update
            await self.log_event(ctx, f"Updated price of {product} from ₹{old_price:.2f} to ₹{price:.2f} (INR).")
        else:
            await ctx.send(f"`{product}` not found in stock.")

    @commands.command()
    @commands.check(is_allowed)
    async def setallowedchannels(self, ctx, *channel_ids: int):
        """Set the allowed channels for bot commands."""
        if not channel_ids:
            await ctx.send("Please provide at least one channel ID.")
            return
        await self.config.guild(ctx.guild).allowed_channels.set(list(channel_ids))
        await ctx.send(f"Allowed channels updated: {', '.join([str(cid) for cid in channel_ids])}")

    @commands.command()
    @commands.check(is_allowed)
    async def setlogchannel(self, ctx, channel: discord.TextChannel):
        """Set the logging channel."""
        await self.config.log_channel_id.set(channel.id)
        await ctx.send(f"Log channel set to {channel.mention}")

    @commands.command()
    @commands.check(is_allowed)
    async def viewhistory(self, ctx, member: discord.Member = None):
        """View the purchase history of a member."""
        if member is None:
            member = ctx.author
        purchase_history = await self.config.guild(ctx.guild).purchase_history()

        if str(member.id) not in purchase_history:
            await ctx.send(f"No purchase history found for {member.mention}.")
            return

        history = purchase_history[str(member.id)]
        embed = discord.Embed(
            title=f"Purchase History of {member.name}",
            color=discord.Color.blue()
        )
        for record in history:
            product = record["product"]
            quantity = record["quantity"]
            price = record["price"]
            timestamp = record["timestamp"]
            custom_text = record["custom_text"]
            embed.add_field(
                name=f"{timestamp}",
                value=f"> **Product:** {product}\n> **Quantity:** {quantity}\n> **Price:** ₹{price:.2f} (INR) / ${price / 83.2:.2f} (USD)\n> **Custom Text:** • {custom_text}",
                inline=False
            )

        await ctx.send(embed=embed)

    async def log_event(self, ctx, message):
        """Log an event to the specified log channel."""
        log_channel_id = await self.config.log_channel_id()
        if log_channel_id:
            log_channel = self.bot.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(
                    description=message,
                    color=discord.Color.orange(),
                    timestamp=discord.utils.utcnow()
                )
                await log_channel.send(embed=embed)

def setup(bot):
    bot.add_cog(Manager(bot))
