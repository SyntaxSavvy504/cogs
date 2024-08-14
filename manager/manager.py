import discord
from redbot.core import commands, Config
import uuid

class Manager(commands.Cog):
    """Manage product delivery and stock."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        default_global = {
            "stock": {},
            "log_channel_id": None,
            "restricted_roles": []
        }
        self.config.register_global(**default_global)

    async def is_allowed(ctx):
        roles = await ctx.cog.config.restricted_roles()
        if not roles:
            return True
        return any(role.id in roles for role in ctx.author.roles)

    def generate_uuid(self):
        return str(uuid.uuid4())[:4].upper()

    @commands.command()
    async def deliver(self, ctx, member: discord.Member, product: str, quantity: int, price: float):
        """Deliver a product to a member."""
        uuid_code = self.generate_uuid()
        embed = discord.Embed(
            title="Product Delivery",
            color=discord.Color.blue()
        )
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)
        embed.add_field(name="Product", value=product, inline=False)
        embed.add_field(name="Quantity", value=quantity, inline=True)
        embed.add_field(name="Price", value=f"${price:.2f}", inline=True)
        embed.add_field(name="UUID", value=uuid_code, inline=False)
        embed.set_footer(text=f"Vouch format: {member.mention} purchased {quantity}x {product} | No vouch, no warranty")

        try:
            await member.send(embed=embed)
            await ctx.send(f"Product delivered to {member.mention} via DM.")
        except discord.Forbidden:
            await ctx.send(f"Failed to deliver the product to {member.mention}. They may have DMs disabled.")
        
        # Log the delivery
        await self.log_event(ctx, f"Delivered {quantity}x {product} to {member.mention} at ${price:.2f}")

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
    async def addproduct(self, ctx, product: str, quantity: int, price: float):
        """Add a product to the stock."""
        stock = await self.config.stock()
        stock[product] = {"quantity": quantity, "price": price}
        await self.config.stock.set(stock)
        await ctx.send(f"Added {quantity}x {product} at ${price:.2f} each to the stock.")

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

    async def log_event(self, ctx, message):
        log_channel_id = await self.config.log_channel_id()
        if log_channel_id:
            log_channel = self.bot.get_channel(log_channel_id)
            if log_channel:
                await log_channel.send(message)