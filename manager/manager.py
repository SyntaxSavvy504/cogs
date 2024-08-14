import discord
from redbot.core import commands, Config
import uuid
from datetime import datetime
from pytz import timezone

class ShopManager(commands.Cog):
    """Manage product delivery, stock, and logging."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        default_global = {
            "stock": {},
            "log_channel_id": None,
            "purchase_history": {},
            "allowed_roles": [],
            "allowed_channels": [1273275915174023230],  # Default channel ID
            "admin_roles": []
        }
        self.config.register_global(**default_global)
        default_server = {
            "stock": {},
            "purchase_history": {}
        }
        self.config.register_guild(**default_server)

        # Ensure the cog folder and settings.json file are created
        cog_folder = "cogs/ShopManager"  # Adjust the path to your cog folder structure
        if not os.path.exists(cog_folder):
            os.makedirs(cog_folder)
        
        settings_path = os.path.join(cog_folder, "settings.json")
        if not os.path.exists(settings_path):
            with open(settings_path, "w") as f:
                json.dump(default_global, f)

    def get_ist_time(self):
        """Return current time in IST."""
        ist = timezone('Asia/Kolkata')
        return datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

    async def check_permissions(self, ctx):
        """Check if the user has the right permissions to use the commands."""
        allowed_roles = await self.config.global_get("allowed_roles")
        admin_roles = await self.config.global_get("admin_roles")
        if any(role.id in [r.id for r in ctx.author.roles] for role in ctx.guild.roles if role.id in allowed_roles) or any(role.id in [r.id for r in ctx.author.roles] for role in ctx.guild.roles if role.id in admin_roles):
            return True
        else:
            await ctx.send("You do not have the required role to use this command.")
            return False

    async def check_channel(self, ctx):
        """Ensure command is used in the allowed channel."""
        allowed_channels = await self.config.global_get("allowed_channels")
        if isinstance(allowed_channels, str):
            try:
                allowed_channels = json.loads(allowed_channels)
            except json.JSONDecodeError:
                await ctx.send("Configuration error: Allowed channels are not in the correct format.")
                return False
        if not isinstance(allowed_channels, list):
            await ctx.send("Configuration error: Allowed channels is not a list.")
            return False
        if ctx.channel.id not in allowed_channels:
            await ctx.send("Commands can only be used in the designated channel.")
            return False
        return True

    @commands.command()
    async def deliver(self, ctx, member: discord.Member, product: str, quantity: int, price: float, *, custom_text: str):
        """Deliver a product to a member with a custom message."""
        if not await self.check_channel(ctx) or not await self.check_permissions(ctx):
            return

        guild_stock = await self.config.guild(ctx.guild).stock()
        if product in guild_stock and guild_stock[product]['quantity'] >= quantity:
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
            uuid_code = str(uuid.uuid4()).upper()[:4]
            purchase_date = self.get_ist_time()

            embed = discord.Embed(
                title="__Frenzy Store__",
                color=discord.Color.purple()
            )
            embed.set_author(name="Frenzy Store", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
            embed.add_field(name="Here is your product", value=f"> {product}", inline=False)
            embed.add_field(name="Amount", value=f"> ₹{amount_inr:.2f} (INR) / ${amount_usd:.2f} (USD)", inline=False)
            embed.add_field(name="Purchase Date", value=f"> {purchase_date}", inline=False)
            embed.add_field(name="\u200b", value="**- follow our [TOS](https://discord.com/channels/911622571856891934/911629489325355049) & be a smart buyer!\n- [CLICK HERE](https://discord.com/channels/911622571856891934/1134197532868739195) to leave your __feedback__**", inline=False)
            embed.add_field(name="Product info and credentials", value=f"||```{custom_text}```||", inline=False)
            embed.set_footer(text=f"Vouch format: +rep {ctx.author.mention} {quantity}x {product} | No vouch, no warranty")
            embed.set_image(url="https://media.discordapp.net/attachments/1271370383735394357/1271370426655703142/931f5b68a813ce9d437ec11b04eec649.jpg")

            try:
                await member.send(embed=embed)
                await ctx.send(f"Product delivered to {member.mention} via DM.")
            except discord.Forbidden:
                await ctx.send(f"Failed to deliver the product to {member.mention}. They may have DMs disabled.")
            
            # Log the delivery
            await self.log_event(ctx, f"Delivered {quantity}x {product} to {member.mention} at ₹{amount_inr:.2f} (INR) / ${amount_usd:.2f} (USD)", log_type="delivery")

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

        else:
            await ctx.send(f"Insufficient stock for {product}.")

    @commands.command()
    async def stock(self, ctx):
        """Display available stock."""
        if not await self.check_channel(ctx) or not await self.check_permissions(ctx):
            return

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
    async def addproduct(self, ctx, product: str, quantity: int, price: float, emoji: str):
        """Add a product to the stock."""
        if not await self.check_channel(ctx) or not await self.check_permissions(ctx):
            return

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
            value=f"> **{product}**",
            inline=False
        )
        embed.add_field(
            name="Quantity",
            value=f"> {quantity}",
            inline=False
        )
        embed.add_field(
            name="Price",
            value=f"> ₹{price:.2f} (INR)",
            inline=False
        )
        embed.add_field(
            name="Emoji",
            value=f"> {emoji}",
            inline=False
        )
        await ctx.send(embed=embed)
        # Log the addition
        await self.log_event(ctx, f"Added {quantity}x {product} to stock at ₹{price:.2f} (INR)", log_type="addition")

    @commands.command()
    async def removeproduct(self, ctx, product: str, quantity: int):
        """Remove a product from the stock."""
        if not await self.check_channel(ctx) or not await self.check_permissions(ctx):
            return

        guild_stock = await self.config.guild(ctx.guild).stock()
        if product in guild_stock:
            if guild_stock[product]['quantity'] >= quantity:
                guild_stock[product]['quantity'] -= quantity
                if guild_stock[product]['quantity'] <= 0:
                    del guild_stock[product]
                await self.config.guild(ctx.guild).stock.set(guild_stock)
                await ctx.send(f"Removed {quantity}x {product} from stock.")
                # Log the removal
                await self.log_event(ctx, f"Removed {quantity}x {product} from stock", log_type="removal")
            else:
                await ctx.send(f"Insufficient quantity of {product} to remove.")
        else:
            await ctx.send(f"{product} does not exist in stock.")

    @commands.command()
    async def setallowedchannels(self, ctx, *channel_ids: int):
        """Set the channels where commands can be used."""
        if not await self.check_permissions(ctx):
            return

        await self.config.global_set("allowed_channels", list(channel_ids))
        await ctx.send(f"Allowed channels updated: {', '.join(map(str, channel_ids))}")

    @commands.command()
    async def setlogchannel(self, ctx, channel_id: int):
        """Set the channel for logging events."""
        if not await self.check_permissions(ctx):
            return

        await self.config.global_set("log_channel_id", channel_id)
        await ctx.send(f"Log channel set to <#{channel_id}>")

    @commands.command()
    async def viewhistory(self, ctx):
        """View purchase history for the user."""
        if not await self.check_channel(ctx) or not await self.check_permissions(ctx):
            return

        purchase_history = await self.config.guild(ctx.guild).purchase_history()
        user_history = purchase_history.get(str(ctx.author.id), [])

        if not user_history:
            await ctx.send("You have no purchase history.")
            return

        embed = discord.Embed(
            title="Purchase History",
            color=discord.Color.orange()
        )

        for record in user_history:
            embed.add_field(
                name=f"Product: {record['product']}",
                value=f"**Quantity:** {record['quantity']}\n**Price:** ₹{record['price']:.2f} (INR)\n**Date:** {record['timestamp']}\n**Custom Message:** ||```{record['custom_text']}```||\n**Sold By:** {record['sold_by']}",
                inline=False
            )

        await ctx.send(embed=embed)

    async def log_event(self, ctx, message, log_type):
        """Log an event to the designated log channel."""
        log_channel_id = await self.config.global_get("log_channel_id")
        if log_channel_id is None:
            return
        
        log_channel = self.bot.get_channel(log_channel_id)
        if log_channel is None:
            return

        embed = discord.Embed(
            title=f"Stock Event: {log_type.capitalize()}",
            description=message,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Event Time: {self.get_ist_time()}")

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            print(f"Could not send message to log channel {log_channel_id}.")
