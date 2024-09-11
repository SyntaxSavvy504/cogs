import discord
from redbot.core import commands
from pymongo import MongoClient
import uuid
from datetime import datetime
from pytz import timezone
import asyncio
import time

class Manager(commands.Cog):
    """Manage product delivery and stock."""

    def __init__(self, bot):
        self.bot = bot
        self.client = MongoClient("mongodb+srv://LK:x7dFo9kxMgIQM2ba@cluster0.fwh6iil.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        self.db = self.client['frenzy_store']

        # Ensure collections exist
        self.stock_collection = self.db['stock']
        self.purchase_history_collection = self.db['purchase_history']
        self.settings_collection = self.db['settings']

        # Default global settings
        self.settings_collection.update_one(
            {'_id': 'global'},
            {'$setOnInsert': {
                'log_channel_id': None,
                'restricted_roles': [],
                'grant_permissions': []
            }},
            upsert=True
        )

    def get_ist_time(self):
        """Return current time in IST."""
        ist = timezone('Asia/Kolkata')
        return datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

    def measure_latency(self, func, *args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        latency = time.time() - start_time
        return result, latency

    @staticmethod
    async def is_allowed(ctx):
        roles = ctx.cog.settings_collection.find_one({'_id': 'global'})['restricted_roles']
        if not roles:
            return True
        return any(role.id in roles for role in ctx.author.roles)

    @staticmethod
    async def has_grant_permissions(ctx):
        return any(role.id in ctx.cog.settings_collection.find_one({'_id': 'global'})['grant_permissions'] for role in ctx.author.roles)

    def generate_uuid(self):
        return str(uuid.uuid4())[:4].upper()

    @commands.command()
    async def deliver(self, ctx, member: discord.Member, product: str, quantity: int, price: float, *, custom_text: str):
        """Deliver a product to a member with a custom message and vouch text."""
        guild_stock, stock_latency = self.measure_latency(self.stock_collection.find_one, {'guild_id': str(ctx.guild.id)})

        if guild_stock and product in guild_stock.get('products', {}):
            product_info = guild_stock['products'][product]
            if product_info['quantity'] >= quantity:
                # Prompt for vouch text
                def check(msg):
                    return msg.author == ctx.author and msg.channel == ctx.channel

                await ctx.send("Please enter the vouch text:")
                try:
                    vouch_msg = await self.bot.wait_for('message', timeout=60.0, check=check)
                    vouch_text = vouch_msg.content
                except asyncio.TimeoutError:
                    await ctx.send("You took too long to respond. Delivery cancelled.")
                    return

                # Prepare the embed
                uuid_code = self.generate_uuid()
                purchase_date = self.get_ist_time()

                amount_inr = price * quantity
                usd_exchange_rate = 83.2  # Exchange rate from INR to USD
                amount_usd = amount_inr / usd_exchange_rate

                embed = discord.Embed(
                    title="__Frenzy Store__",
                    color=discord.Color.purple()
                )
                embed.set_author(name="Frenzy Store", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
                embed.add_field(name="__Here is your product__", value=f"> {product} {product_info.get('emoji', '')}", inline=False)
                embed.add_field(name="__Amount__", value=f"> ₹{amount_inr:.2f} (INR) / ${amount_usd:.2f} (USD)", inline=False)
                embed.add_field(name="__Purchase Date__", value=f"> {purchase_date}", inline=False)
                embed.add_field(name="\u200b", value="**- Follow our [TOS](https://discord.com/channels/911622571856891934/911629489325355049) & be a smart buyer!\n- [CLICK HERE](https://discord.com/channels/911622571856891934/1134197532868739195) to leave your __feedback__**", inline=False)
                embed.add_field(name="__Product info and credentials__", value=f"||```{custom_text}```||", inline=False)
                embed.add_field(name="__Vouch Format__", value=f"`{vouch_text}`", inline=False)
                embed.set_footer(text=f"Thanks for order. No vouch, no warranty")
                embed.set_image(url="https://media.discordapp.net/attachments/1271370383735394357/1271370426655703142/931f5b68a813ce9d437ec11b04eec649.jpg")
                embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)

                # Try to send the embed to the user's DM
                dm_channel = member.dm_channel or await member.create_dm()
                try:
                    await dm_channel.send(embed=embed)
                    await ctx.send(f"✅ **Product Delivered:**\n```\n1. {product}\n```\n📤 **Recipient:**\n```\n2. {member.mention}\n```\n📩 **Delivery Method:**\n```\n3. Direct Message\n```\n📅 **Delivery Time:**\n```\n4. {self.get_ist_time()}\n```")



                    # Deduct the quantity from server-specific stock
                    product_info['quantity'] -= quantity
                    if product_info['quantity'] <= 0:
                        del guild_stock['products'][product]
                    update_result, update_latency = self.measure_latency(self.stock_collection.update_one,
                        {'guild_id': str(ctx.guild.id)},
                        {'$set': {'products': guild_stock.get('products', {})}}
                    )

                    # Log the delivery
                    await self.log_event(ctx, f"🛒 **Delivered Product:**\n```1. Product: {quantity}x {product}\n```\n📩 **Recipient:**\n```2. {member.mention}\n```\n💰 **Amount:**\n```3. ₹{amount_inr:.2f} (INR) / ${amount_usd:.2f} (USD)\n```\n⏱️ **Stock Update Latency:**\n```4. {update_latency:.4f}s\n```\n🗄️ **MongoDB Find Latency:**\n```5. {stock_latency:.4f}s\n```")



                    # Record the purchase in history
                    purchase_record = {
                        "product": product,
                        "quantity": quantity,
                        "price": price,
                        "custom_text": custom_text,
                        "timestamp": purchase_date,
                        "sold_by": ctx.author.name
                    }
                    history_update_result, history_update_latency = self.measure_latency(self.purchase_history_collection.update_one,
                        {'guild_id': str(ctx.guild.id), 'user_id': str(member.id)},
                        {'$push': {'history': purchase_record}},
                        upsert=True
                    )

                    await self.log_event(ctx, f"Purchase record updated.\nMongoDB Database Updated: {history_update_latency:.4f}s")

                except discord.Forbidden as e:
                    await ctx.send(f"Failed to deliver the product `{product}` to {member.mention}. Reason: {str(e)}")
            else:
                await ctx.send(f"Insufficient stock for `{product}`.")
        else:
            await ctx.send(f"No stock available for `{product}`.")

    @commands.command()
    async def stock(self, ctx):
        """Display available stock."""
        guild_stock, stock_latency = self.measure_latency(self.stock_collection.find_one, {'guild_id': str(ctx.guild.id)})

        if not guild_stock or 'products' not in guild_stock:
            await ctx.send("No stock available.")
            return

        embed = discord.Embed(
            title="`📦 Available Stock`",
            color=discord.Color.green()
        )
        embed.set_author(name="Frenzy Store", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)

        for idx, (product, info) in enumerate(guild_stock['products'].items(), start=1):
            amount_inr = info['price']
            usd_exchange_rate = 83.2  # Exchange rate from INR to USD
            amount_usd = amount_inr / usd_exchange_rate
            embed.add_field(
                name=f"**{idx}.** `{product}` {info.get('emoji', '')}",
                value=(
                    f"**Quantity:** `{info['quantity']}`\n"
                    f"**Price:** `₹{amount_inr:.2f}` (INR) / `${amount_usd:.2f}` (USD)"
                ),
                inline=False
            )


        await ctx.send(embed=embed)
        await ctx.send(f"Successfully fetched data from the database:\n`Latency: {stock_latency:.4f}s`")

    @commands.command()
    @commands.check(is_allowed)
    async def addproduct(self, ctx, product: str, quantity: int, price: float, emoji: str):
        """Add a product to the stock."""
        guild_stock, stock_latency = self.measure_latency(self.stock_collection.find_one, {'guild_id': str(ctx.guild.id)}) or {'products': {}}

        if product in guild_stock['products']:
            guild_stock['products'][product]['quantity'] += quantity
            guild_stock['products'][product]['price'] = price
            guild_stock['products'][product]['emoji'] = emoji
        else:
            guild_stock['products'][product] = {"quantity": quantity, "price": price, "emoji": emoji}

        update_result, update_latency = self.measure_latency(self.stock_collection.update_one,
            {'guild_id': str(ctx.guild.id)},
            {'$set': {'products': guild_stock['products']}},
            upsert=True
        )

        embed = discord.Embed(
            title="Product Added",
            color=discord.Color.teal()
        )
        embed.set_author(name="Frenzy Store", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
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
        await ctx.send(f"MongoDB update latency: {update_latency:.4f}s")

        # Log the addition
        await self.log_event(ctx, f"Added {quantity}x {product} to the stock at ₹{price:.2f} (INR) / ${price / 83.2:.2f} (USD).\nStock update latency: {update_latency:.4f}s")

    @commands.command()
    @commands.check(is_allowed)
    async def removeproduct(self, ctx, product: str):
        """Remove a product from the stock."""
        guild_stock, stock_latency = self.measure_latency(self.stock_collection.find_one, {'guild_id': str(ctx.guild.id)})

        if not guild_stock or 'products' not in guild_stock or product not in guild_stock['products']:
            await ctx.send(f"{product} not found in stock.")
            return

        del guild_stock['products'][product]
        update_result, update_latency = self.measure_latency(self.stock_collection.update_one,
            {'guild_id': str(ctx.guild.id)},
            {'$set': {'products': guild_stock.get('products', {})}}
        )

        embed = discord.Embed(
            title="Product Removed",
            color=discord.Color.red()
        )
        embed.set_author(name="Frenzy Store", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
        embed.add_field(
            name="Product",
            value=f"> {product}",
            inline=False
        )
        await ctx.send(embed=embed)
        await ctx.send(f"MongoDB update latency: {update_latency:.4f}s")

        # Log the removal
        await self.log_event(ctx, f"Removed {product} from the stock.\nStock update latency: {update_latency:.4f}s")

    @commands.command()
    async def viewhistory(self, ctx, member: discord.Member = None):
        """View purchase history for a user."""
        if member is None:
            member = ctx.author

        purchase_history, history_latency = self.measure_latency(self.purchase_history_collection.find_one, {'guild_id': str(ctx.guild.id), 'user_id': str(member.id)})

        if not purchase_history or 'history' not in purchase_history:
            await ctx.send("No purchase history found for this user.")
            return

        embed = discord.Embed(
            title=f"```📜 Detailed Purchase History for {member.name}```",
            color=discord.Color.blue()
        )
        embed.set_author(name="Frenzy Store", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)

        for record in purchase_history['history']:
            embed.add_field(
                name=f"🛒 `{record['product']}` (x{record['quantity']})",
                value=(
                    f"1. **Price:** `₹{record['price']:.2f}` (INR)\n"
                    f"2. **Purchased On:** `{record['timestamp']}`\n"
                    f"3. **Sold By:** `{record['sold_by']}`\n"
                    f"4. **Custom Text:** `{record['custom_text']}`"
                ),
                inline=False
            )

        await ctx.send(embed=embed)
        await ctx.send(f"Successfully fetched data from the database! Latency: `{history_latency:.4f}s`")


    async def log_event(self, ctx, message):
        """Log the event to the log channel."""
        log_channel_id = self.settings_collection.find_one({'_id': 'global'}).get('log_channel_id')
        if not log_channel_id:
            return

        log_channel = self.bot.get_channel(log_channel_id)
        if log_channel:
            embed = discord.Embed(
                title="Event Log",
                description=message,
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text=f"Logged by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
            await log_channel.send(embed=embed)

    @commands.command()
    async def setlogchannel(self, ctx, channel: discord.TextChannel):
        """Set the channel for logging events."""
        self.settings_collection.update_one(
            {'_id': 'global'},
            {'$set': {'log_channel_id': channel.id}}
        )
        await ctx.send(f"Log channel set to {channel.mention}")

    @commands.command()
    @commands.check(is_allowed)
    async def setprice(self, ctx, product: str, price: float):
        """Set or update the price of a specific product."""
        guild_stock = self.stock_collection.find_one({'guild_id': str(ctx.guild.id)})

        if guild_stock and product in guild_stock.get('products', {}):
            guild_stock['products'][product]['price'] = price
            self.stock_collection.update_one(
                {'guild_id': str(ctx.guild.id)},
                {'$set': {'products': guild_stock['products']}}
            )
            await ctx.send(f"The price of `{product}` has been updated to ₹{price:.2f}.")
            await self.log_event(ctx, f"Price of `{product}` updated to ₹{price:.2f}.")
        else:
            await ctx.send(f"No product found with the name `{product}`.")


    @commands.command()
    async def restrictrole(self, ctx, role: discord.Role):
        """Restrict bot usage to a specific role."""
        self.settings_collection.update_one(
            {'_id': 'global'},
            {'$addToSet': {'restricted_roles': role.id}}
        )
        await ctx.send(f"Role {role.name} has been added to the restriction list.")

    @commands.command()
    async def grantpermissions(self, ctx, role: discord.Role):
        """Grant permissions to a specific role to use certain commands."""
        self.settings_collection.update_one(
            {'_id': 'global'},
            {'$addToSet': {'grant_permissions': role.id}}
        )
        await ctx.send(f"Role {role.name} has been granted special permissions.")

def setup(bot):
    bot.add_cog(Manager(bot))
