import discord
from redbot.core import commands, Config
import uuid
import json
import os

class Shop(commands.Cog):
    """Manage product delivery and stock."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        default_global = {
            "stock": {},
            "log_channel_id": None,
            "restricted_roles": [],
            "allowed_channels": [],
            "purchase_history": {}
        }
        self.config.register_global(**default_global)
        self.ensure_settings()

    def ensure_settings(self):
        if not os.path.exists('settings.json'):
            try:
                with open('settings.json', 'w') as f:
                    json.dump(self.config.default_global, f, indent=4)
            except IOError as e:
                print(f"Failed to create settings.json: {e}")

    @staticmethod
    async def is_allowed(ctx):
        roles = await ctx.cog.config.restricted_roles()
        if not roles:
            return True
        return any(role.id in roles for role in ctx.author.roles)

    @staticmethod
    async def is_channel_allowed(ctx):
        allowed_channels = await ctx.cog.config.allowed_channels()
        return not allowed_channels or ctx.channel.id in allowed_channels

    def generate_uuid(self):
        return str(uuid.uuid4())[:4].upper()

    @commands.command()
    async def deliver(self, ctx, member: discord.Member, product: str, quantity: int, price: float, *, custom_text: str):
        """Deliver a product to a member with a custom message."""
        if not await self.is_channel_allowed(ctx):
            await ctx.send("You can't use this command in this channel.")
            return

        uuid_code = self.generate_uuid()
        embed = discord.Embed(
            title="Frenzy Store",
            color=discord.Color.purple()
        )
        embed.set_author(name="Frenzy Store", icon_url=self.bot.user.avatar_url)
        embed.add_field(name="Here your product", value=f"{product}", inline=False)
        embed.add_field(name="Quantity", value=quantity, inline=True)
        embed.add_field(name="Price", value=f"${price:.2f}", inline=True)
        embed.add_field(name="UUID", value=uuid_code, inline=False)
        embed.set_footer(text=f"Vouch format: +rep @UtsaV {quantity}x {product} {price:.2f} INR legit")
        embed.add_field(name="Custom Message", value=f"||```{custom_text}```||", inline=False)
        embed.set_image(url="https://media.discordapp.net/attachments/1271370383735394357/1271370426655703142/931f5b68a813ce9d437ec11b04eec649.jpg")

        try:
            await member.send(embed=embed)
            await ctx.send(f"Product delivered to {member.mention} via DM.")
            
            # Log the delivery
            await self.log_event(ctx, f"Delivered {quantity}x {product} to {member.mention} at ${price:.2f}")
            
            # Record purchase history
            history = await self.config.purchase_history()
            if member.id not in history:
                history[member.id] = []
            history[member.id].append({
                "product": product,
                "quantity": quantity,
                "price": price,
                "date": str(ctx.message.created_at),
                "custom_message": custom_text
            })
            await self.config.purchase_history.set(history)
            
        except discord.Forbidden:
            await ctx.send(f"Failed to deliver the product to {member.mention}. They may have DMs disabled.")

    @commands.command()
    async def stock(self, ctx):
        """Display available stock."""
        if not await self.is_channel_allowed(ctx):
            await ctx.send("You can't use this command in this channel.")
            return

        stock = await self.config.stock()
        if not stock:
            await ctx.send("No stock available.")
            return

        embed = discord.Embed(
            title="Available Stock",
            color=discord.Color.purple()
        )

        for idx, (product, info) in enumerate(stock.items(), start=1):
            embed.add_field(
                name=f"{idx}. {product}",
                value=f"Quantity: {info['quantity']}\nPrice: ${info['price']:.2f}",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command()
    @commands.check(is_allowed)
    async def addproduct(self, ctx, product: str, quantity: int, price: float, emoji: str):
        """Add a product to the stock."""
        if not await self.is_channel_allowed(ctx):
            await ctx.send("You can't use this command in this channel.")
            return

        stock = await self.config.stock()
        stock[product] = {"quantity": quantity, "price": price, "emoji": emoji}
        await self.config.stock.set(stock)
        await ctx.send(f"Added {quantity}x {product} ({emoji}) at ${price:.2f} each to the stock.")
        
        # Log the addition
        await self.log_event(ctx, f"Added {quantity}x {product} ({emoji}) to the stock at ${price:.2f}")

    @commands.command()
    @commands.check(is_allowed)
    async def removeproduct(self, ctx, product: str):
        """Remove a product from the stock."""
        if not await self.is_channel_allowed(ctx):
            await ctx.send("You can't use this command in this channel.")
            return

        stock = await self.config.stock()
        if product not in stock:
            await ctx.send(f"{product} not found in stock.")
            return

        del stock[product]
        await self.config.stock.set(stock)
        await ctx.send(f"Removed {product} from the stock.")
        
        # Log the removal
        await self.log_event(ctx, f"Removed {product} from the stock.")

    @commands.command()
    @commands.check(is_allowed)
    async def setallowedchannels(self, ctx, *channel_ids: int):
        """Set channels where commands can be used."""
        await self.config.allowed_channels.set(list(channel_ids))
        await ctx.send(f"Allowed channels set to: {', '.join(str(x) for x in channel_ids)}")

    @commands.command()
    @commands.check(is_allowed)
    async def setlogchannel(self, ctx, channel: discord.TextChannel):
        """Set the log channel."""
        await self.config.log_channel_id.set(channel.id)
        await ctx.send(f"Log channel set to {channel.mention}.")

    @commands.command()
    @commands.check(is_allowed)
    async def setrole(self, ctx, role: discord.Role):
        """Restrict command usage to a specific role."""
        restricted_roles = await self.config.restricted_roles()
        restricted_roles.append(role.id)
        await self.config.restricted_roles.set(restricted_roles)
        await ctx.send(f"Role {role.name} added to the restricted roles list.")

    @commands.command()
    async def viewhistory(self, ctx):
        """View purchase history for the user."""
        if not await self.is_channel_allowed(ctx):
            await ctx.send("You can't use this command in this channel.")
            return

        if not await self.is_allowed(ctx):
            await ctx.send("You do not have permission to view history.")
            return

        history = await self.config.purchase_history()
        user_history = history.get(ctx.author.id, [])

        if not user_history:
            await ctx.send("No purchase history found.")
            return

        embed = discord.Embed(
            title="Purchase History",
            color=discord.Color.purple()
        )

        for entry in user_history:
            embed.add_field(
                name=f"Product: {entry['product']}",
                value=f"Quantity: {entry['quantity']}\nPrice: ${entry['price']:.2f}\nDate: {entry['date']}\nCustom Message: ||```{entry['custom_message']}```||",
                inline=False
            )

        await ctx.send(embed=embed)

    async def log_event(self, ctx, message):
        """Log an event to the configured log channel."""
        log_channel_id = await self.config.log_channel_id()
        if not log_channel_id:
            return

        log_channel = self.bot.get_channel(log_channel_id)
        if log_channel:
            embed = discord.Embed(
                title="Shop Event",
                description=message,
                color=discord.Color.red()
            )
            embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)
            embed.add_field(name="Channel", value=ctx.channel.mention)
            embed.add_field(name="Time", value=ctx.message.created_at.strftime("%Y-%m-%d %H:%M:%S"))
            try:
                await log_channel.send(embed=embed)
            except discord.Forbidden:
                print("Bot does not have permission to send messages in the log channel.")
