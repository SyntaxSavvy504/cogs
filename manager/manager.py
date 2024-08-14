import discord
from redbot.core import commands, Config
import uuid
import json
import os
from datetime import datetime

class Manager(commands.Cog):
    """Manage product delivery and stock."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        default_global = {
            "servers": {}  # Store data per server
        }
        self.config.register_global(**default_global)

        # Create settings.json if it doesn't exist
        if not os.path.exists("settings.json"):
            with open("settings.json", "w") as f:
                json.dump(default_global, f)

    async def is_allowed(self, ctx):
        roles = await self.config.servers(ctx.guild.id).restricted_roles()
        if not roles:
            return True
        return any(role.id in roles for role in ctx.author.roles)

    async def is_in_allowed_channel(self, ctx):
        allowed_channel_id = 1273275915174023230
        return ctx.channel.id == allowed_channel_id

    async def cog_check(self, ctx):
        """Check if the command is run in the allowed channel."""
        if not await self.is_in_allowed_channel(ctx):
            await ctx.send("Commands can only be run in the designated channel.")
            return False
        return True

    def generate_uuid(self):
        return str(uuid.uuid4())[:4].upper()

    async def get_server_data(self, server_id):
        """Get or initialize server-specific data."""
        data = await self.config.servers(server_id).all()
        if not data:
            await self.config.servers(server_id).set({
                "stock": {},
                "log_channel_id": None,
                "restricted_roles": [],
                "purchase_history": {}
            })
            data = await self.config.servers(server_id).all()
        return data

    async def log_event(self, ctx, message):
        server_data = await self.get_server_data(ctx.guild.id)
        log_channel_id = server_data["log_channel_id"]
        if log_channel_id:
            log_channel = self.bot.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(
                    title="Log Event",
                    description=f"> {message}",
                    color=discord.Color.orange(),
                    timestamp=datetime.utcnow()
                )
                embed.set_footer(text=f"Logged by {ctx.author.name}")
                await log_channel.send(embed=embed)

    @commands.command()
    async def deliver(self, ctx, member: discord.Member, product: str, quantity: int, price: float, *, custom_text: str):
        """Deliver a product to a member with a custom message."""
        server_data = await self.get_server_data(ctx.guild.id)
        stock = server_data["stock"]

        if product not in stock or stock[product]['quantity'] < quantity:
            await ctx.send(f"Insufficient stock for {product}.")
            return

        # Deduct the quantity from stock
        stock[product]['quantity'] -= quantity
        if stock[product]['quantity'] <= 0:
            del stock[product]
        await self.config.servers(ctx.guild.id).stock.set(stock)

        # Prepare the embed
        uuid_code = self.generate_uuid()
        purchase_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        embed = discord.Embed(
            title="__Frenzy Store__",
            color=discord.Color.blue()
        )
        embed.set_author(name="Frenzy Store", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
        embed.add_field(name="Here is your product", value=f"> {product}", inline=False)
        embed.add_field(name="Amount", value=f"> ${price * quantity:.2f}", inline=False)
        embed.add_field(name="Purchase Date", value=f"> {purchase_date}", inline=False)
        embed.add_field(name="\u200b", value="**- follow our [TOS](https://discord.com/channels/911622571856891934/911629489325355049) & be a smart buyer!\n- [CLICK HERE](https://discord.com/channels/911622571856891934/1134197532868739195) to leave your __feedback__**", inline=False)
        embed.add_field(name="Custom Message", value=f"||```{custom_text}```||", inline=False)
        embed.set_footer(text=f"Vouch format: +rep {member.mention} {quantity}x {product} | No vouch, no warranty")
        embed.set_image(url="https://media.discordapp.net/attachments/1271370383735394357/1271370426655703142/931f5b68a813ce9d437ec11b04eec649.jpg?ex=66bdaefa&is=66bc5d7a&hm=175b7664862e5f77e5736b51eb96857ee882a3ead7638bdf87cc4ea22b7181aa&=&format=webp&width=1114&height=670")

        try:
            await member.send(embed=embed)
            await ctx.send(f"Product delivered to {member.mention} via DM.")
            await self.log_event(ctx, f"Successfully delivered {quantity}x {product} to {member.mention} at ${price:.2f}.")
        except discord.Forbidden:
            await ctx.send(f"Failed to deliver the product to {member.mention}. They may have DMs disabled.")
            await self.log_event(ctx, f"Failed to deliver {quantity}x {product} to {member.mention}. DMs might be disabled.")

        # Record the purchase in history
        purchase_history = server_data["purchase_history"]
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
        await self.config.servers(ctx.guild.id).purchase_history.set(purchase_history)

    @commands.command()
    async def stock(self, ctx):
        """Display available stock."""
        server_data = await self.get_server_data(ctx.guild.id)
        stock = server_data["stock"]
        if not stock:
            await ctx.send("No stock available.")
            return

        embed = discord.Embed(
            title="Available Stock",
            color=discord.Color.green()
        )

        for idx, (product, info) in enumerate(stock.items(), start=1):
            embed.add_field(
                name=f"{idx}. {product}",
                value=f"> **Quantity:** {info['quantity']}\n> **Price:** ${info['price']:.2f}",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command()
    @commands.check(is_allowed)
    async def addproduct(self, ctx, product: str, quantity: int, price: float, emoji: str):
        """Add a product to the stock."""
        server_data = await self.get_server_data(ctx.guild.id)
        stock = server_data["stock"]
        if product in stock:
            stock[product]['quantity'] += quantity
            stock[product]['price'] = price
            stock[product]['emoji'] = emoji
        else:
            stock[product] = {"quantity": quantity, "price": price, "emoji": emoji}
        await self.config.servers(ctx.guild.id).stock.set(stock)
        embed = discord.Embed(
            title="Product Added",
            color=discord.Color.teal()
        )
        embed.add_field(
            name="Product",
            value=f"||```{product} {emoji}```||",
            inline=False
        )
        embed.add_field(
            name="Quantity",
            value=f"||```{quantity}```||",
            inline=False
        )
        embed.add_field(
            name="Price",
            value=f"||```${price:.2f}```||",
            inline=False
        )
        await ctx.send(embed=embed)

        # Log the addition
        await self.log_event(ctx, f"Added {quantity}x {product} to the stock at ${price:.2f}.")

    @commands.command()
    @commands.check(is_allowed)
    async def removeproduct(self, ctx, product: str):
        """Remove a product from the stock."""
        server_data = await self.get_server_data(ctx.guild.id)
        stock = server_data["stock"]
        if product not in stock:
            await ctx.send(f"{product} not found in stock.")
            return

        del stock[product]
        await self.config.servers(ctx.guild.id).stock.set(stock)

        embed = discord.Embed(
            title="Product Removed",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Product",
            value=f"||```{product}```||",
            inline=False
        )
        await ctx.send(embed=embed)

        # Log the removal
        await self.log_event(ctx, f"Removed {product} from the stock.")

    @commands.command()
    @commands.check(is_allowed)
    async def viewhistory(self, ctx):
        """View purchase history."""
        server_data = await self.get_server_data(ctx.guild.id)
        purchase_history = server_data["purchase_history"]
        user_history = purchase_history.get(str(ctx.author.id), [])

        if not user_history:
            await ctx.send("No purchase history found.")
            return

        embed = discord.Embed(
            title="Purchase History",
            color=discord.Color.purple()
        )
        for record in user_history:
            embed.add_field(
                name=f"Product: {record['product']}",
                value=f"> **Quantity:** {record['quantity']}\n> **Price:** ${record['price']:.2f}\n> **Timestamp:** {record['timestamp']}\n> **Custom Message:** ||```{record['custom_text']}```||",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setallowedchannels(self, ctx, *channel_ids: int):
        """Set allowed channels for commands."""
        await self.config.servers(ctx.guild.id).allowed_channels.set(list(channel_ids))
        await ctx.send(f"Allowed channels updated to: {', '.join(map(str, channel_ids))}")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setlogchannel(self, ctx, channel_id: int):
        """Set the log channel."""
        await self.config.servers(ctx.guild.id).log_channel_id.set(channel_id)
        await ctx.send(f"Log channel set to <#{channel_id}>")

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{self.__class__.__name__} cog loaded.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        # Log message event
        if message.guild:
            await self.log_event(message, f"Message received in {message.channel.name}: {message.content}")
