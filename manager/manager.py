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
            "stock": {},
            "log_channel_id": None,
            "restricted_roles": [],
            "purchase_history": {}
        }
        self.config.register_global(**default_global)

        # Create settings.json if it doesn't exist
        if not os.path.exists("settings.json"):
            with open("settings.json", "w") as f:
                json.dump(default_global, f)

    async def is_allowed(ctx):
        roles = await ctx.cog.config.restricted_roles()
        if not roles:
            return True
        return any(role.id in roles for role in ctx.author.roles)

    def generate_uuid(self):
        return str(uuid.uuid4())[:4].upper()

    @commands.command()
    async def deliver(self, ctx, member: discord.Member, product: str, quantity: int, price: float, *, custom_text: str):
        """Deliver a product to a member with a custom message."""
        uuid_code = self.generate_uuid()
        embed = discord.Embed(
            title="Frenzy Store",
            color=discord.Color.blue()
        )
        embed.set_author(name="Frenzy Store", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
        embed.add_field(name="Here is your product", value=product, inline=False)
        embed.add_field(name="\u200b", value="**- follow our [TOS](https://discord.com/channels/911622571856891934/911629489325355049) & be a smart buyer!\n- [CLICK HERE](https://discord.com/channels/911622571856891934/1134197532868739195)  to leave your __feedback__**", inline=False)
        embed.add_field(name="Custom Message", value=f"||{custom_text}||", inline=False)
        embed.set_footer(text=f"Vouch format: {member.mention} purchased {quantity}x {product} | No vouch, no warranty")

        try:
            await member.send(embed=embed)
            await ctx.send(f"Product delivered to {member.mention} via DM.")
        except discord.Forbidden:
            await ctx.send(f"Failed to deliver the product to {member.mention}. They may have DMs disabled.")
        
        # Log the delivery
        await self.log_event(ctx, f"Delivered {quantity}x {product} to {member.mention} at ${price:.2f}")

        # Record the purchase in history
        purchase_history = await self.config.purchase_history()
        purchase_record = {
            "product": product,
            "quantity": quantity,
            "price": price,
            "custom_text": custom_text,
            "timestamp": str(datetime.utcnow()),
            "sold_by": ctx.author.name
        }
        if str(member.id) not in purchase_history:
            purchase_history[str(member.id)] = []
        purchase_history[str(member.id)].append(purchase_record)
        await self.config.purchase_history.set(purchase_history)

    @commands.command()
    async def stock(self, ctx):
        """Display available stock."""
        stock = await self.config.stock()
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
                value=f"Quantity: {info['quantity']}\nPrice: ${info['price']:.2f}",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command()
    @commands.check(is_allowed)
    async def addproduct(self, ctx, product: str, quantity: int, price: float, emoji: str):
        """Add a product to the stock."""
        stock = await self.config.stock()
        stock[product] = {"quantity": quantity, "price": price, "emoji": emoji}
        await self.config.stock.set(stock)
        await ctx.send(f"Added {quantity}x {product} {emoji} at ${price:.2f} each to the stock.")

        # Log the addition
        await self.log_event(ctx, f"Added {quantity}x {product} to the stock at ${price:.2f}")

    @commands.command()
    @commands.check(is_allowed)
    async def removeproduct(self, ctx, product: str):
        """Remove a product from the stock."""
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
    async def setlogchannel(self, ctx, channel: discord.TextChannel):
        """Set the log channel."""
        await self.config.log_channel_id.set(channel.id)
        await ctx.send(f"Log channel set to {channel.mention}.")

    @commands.command()
    async def setrole(self, ctx, role: discord.Role):
        """Restrict command usage to a specific role."""
        restricted_roles = await self.config.restricted_roles()
        restricted_roles.append(role.id)
        await self.config.restricted_roles.set(restricted_roles)
        await ctx.send(f"Role {role.name} added to the restricted roles list.")

    @commands.command()
    @commands.check(is_allowed)
    async def view(self, ctx, member: discord.Member):
        """View a member's purchase history."""
        purchase_history = await self.config.purchase_history()
        if str(member.id) not in purchase_history:
            await ctx.send(f"No purchase history found for {member.mention}.")
            return

        history = purchase_history[str(member.id)]
        embed = discord.Embed(
            title=f"{member.name}'s Purchase History",
            color=discord.Color.purple()
        )

        for record in history:
            embed.add_field(
                name=f"{record['timestamp']}",
                value=f"Product: {record['product']}\nQuantity: {record['quantity']}\nPrice: ${record['price']:.2f}\nMessage: {record['custom_text']}\nSold by: {record['sold_by']}",
                inline=False
            )

        await ctx.send(embed=embed)

    async def log_event(self, ctx, message):
        log_channel_id = await self.config.log_channel_id()
        if log_channel_id:
            log_channel = self.bot.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(
                    title="Log Event",
                    description=message,
                    color=discord.Color.orange(),
                    timestamp=datetime.utcnow()
                )
                embed.set_footer(text=f"Logged by {ctx.author.name}")
                await log_channel.send(embed=embed)
