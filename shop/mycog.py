from redbot.core import commands
import discord
from datetime import datetime, timedelta
import asyncio
import random

class ProductCog(commands.Cog):
    """Product management and delivery cog with user data tracking"""

    def __init__(self, bot):
        self.bot = bot
        self.stock = {}
        self.user_data = {}  # Dictionary to store user purchase data
        self.roles = {}  # Dictionary to store role permissions
        self.log_channels = {}  # Dictionary to store logging channels

    @commands.group(invoke_without_command=True)
    async def product(self, ctx):
        """Product management commands."""
        embed = discord.Embed(title="Product Commands", description="Manage products with the following commands:", color=discord.Color.blue())
        embed.add_field(name="Add Product", value="`!product add <name> <quantity> [emoji]`", inline=False)
        embed.add_field(name="Remove Product", value="`!product remove <name> <quantity>`", inline=False)
        await ctx.send(embed=embed)

    @product.command(name='add')
    @commands.has_permissions(administrator=True)
    async def add_product(self, ctx, name: str, quantity: int, emoji: str = None):
        """Add a product to stock with an optional emoji."""
        if name in self.stock:
            self.stock[name]['quantity'] += quantity
        else:
            self.stock[name] = {'quantity': quantity, 'emoji': emoji}

        embed = discord.Embed(title="Product Added", description=f"{name} has been added to stock.", color=discord.Color.green())
        embed.add_field(name="Product", value=f"{name} {emoji if emoji else ''}")
        embed.add_field(name="Quantity", value=quantity)
        await ctx.send(embed=embed)
        await self.log_stock_change(ctx, "Added", name, quantity)

    @product.command(name='remove')
    @commands.has_permissions(administrator=True)
    async def remove_product(self, ctx, name: str, quantity: int):
        """Remove a product from stock."""
        if name in self.stock and self.stock[name]['quantity'] >= quantity:
            self.stock[name]['quantity'] -= quantity
            if self.stock[name]['quantity'] == 0:
                del self.stock[name]

            embed = discord.Embed(title="Product Removed", description=f"{name} has been removed from stock.", color=discord.Color.red())
            embed.add_field(name="Product", value=name)
            embed.add_field(name="Quantity", value=quantity)
            await ctx.send(embed=embed)
            await self.log_stock_change(ctx, "Removed", name, quantity)
        else:
            embed = discord.Embed(title="Error", description="Not enough stock or product not found.", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.command(name='stock')
    async def stock_info(self, ctx):
        """Show current stock info."""
        if not self.stock:
            embed = discord.Embed(title="Stock Info", description="No products in stock.", color=discord.Color.yellow())
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(title="Current Stock", color=discord.Color.blue())
        for product, info in self.stock.items():
            embed.add_field(name=f"{product} {info['emoji'] if info['emoji'] else ''}", value=f"Quantity: {info['quantity']}", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name='delivery')
    async def delivery(self, ctx, user: discord.User, quantity: int, price: float, product: str, *, custom_message: str = None):
        """Send a delivery embed and track user purchase with an optional custom message."""
        uuid = f"{random.randint(1000, 9999)}"  # Generate a 4-digit UUID
        if product in self.stock and self.stock[product]['quantity'] >= quantity:
            self.stock[product]['quantity'] -= quantity
            if self.stock[product]['quantity'] == 0:
                del self.stock[product]

            # Record user purchase data
            now = datetime.utcnow()
            if user.id not in self.user_data:
                self.user_data[user.id] = []
            self.user_data[user.id].append({
                'product': product,
                'quantity': quantity,
                'price': price,
                'time': now,
                'uuid': uuid
            })

            # Send delivery embed
            embed = discord.Embed(title="Product Delivery", description="Product has been delivered.", color=discord.Color.purple())
            embed.set_thumbnail(url=self.bot.user.avatar_url)
            embed.add_field(name="Product", value=f"**{product}**")
            embed.add_field(name="Quantity", value=f"**{quantity}**")
            embed.add_field(name="Price", value=f"**{price}**")
            embed.add_field(name="UUID", value=f"||{uuid}||")
            if custom_message:
                embed.add_field(name="Message", value=custom_message, inline=False)
            embed.set_footer(text="NO VOUCH = NO WARRANTY")
            await ctx.send(embed=embed)

            # Send DM to user
            dm_embed = discord.Embed(title="Delivery Confirmation", description=f"You have received {quantity} of {product}.", color=discord.Color.green())
            dm_embed.set_thumbnail(url=self.bot.user.avatar_url)
            dm_embed.add_field(name="Product", value=f"**{product}**")
            dm_embed.add_field(name="Quantity", value=f"**{quantity}**")
            dm_embed.add_field(name="Price", value=f"**{price}**")
            dm_embed.add_field(name="UUID", value=f"||{uuid}||")
            if custom_message:
                dm_embed.add_field(name="Message", value=custom_message, inline=False)
            dm_embed.set_footer(text="NO VOUCH = NO WARRANTY")
            await user.send(embed=dm_embed)

            await self.log_purchase(ctx, user, product, quantity, price, uuid)
        else:
            embed = discord.Embed(title="Error", description="Not enough stock or product not found.", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.command(name='replace')
    async def replace_product(self, ctx, user: discord.User, old_product_uuid: str, *, replacement_message: str):
        """Replace a suspended user's product using UUID with a new product."""
        old_product_data = self.get_product_data_by_uuid(user, old_product_uuid)
        if old_product_data:
            old_product = old_product_data['product']
            quantity = old_product_data['quantity']
            price = old_product_data['price']

            if old_product in self.stock and self.stock[old_product]['quantity'] >= quantity:
                self.stock[old_product]['quantity'] -= quantity
                if self.stock[old_product]['quantity'] == 0:
                    del self.stock[old_product]

                embed = discord.Embed(title="Product Replaced", description="User's product has been replaced.", color=discord.Color.orange())
                embed.add_field(name="Old Product", value=f"**{old_product}**")
                embed.add_field(name="Quantity", value=f"**{quantity}**")
                embed.add_field(name="Replacement Message", value=replacement_message)
                await ctx.send(embed=embed)

                # Send DM to user
                dm_embed = discord.Embed(title="Product Replacement", description=f"Your product has been replaced due to an account issue.", color=discord.Color.orange())
                dm_embed.add_field(name="Old Product", value=f"**{old_product}**")
                dm_embed.add_field(name="Quantity", value=f"**{quantity}**")
                dm_embed.add_field(name="Replacement Message", value=replacement_message)
                await user.send(embed=dm_embed)

                await self.log_replacement(ctx, user, old_product, quantity, replacement_message)
            else:
                embed = discord.Embed(title="Error", description="Not enough stock or old product not found.", color=discord.Color.red())
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="Error", description="No matching purchase found for the provided UUID.", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.command(name='schedule')
    @commands.has_permissions(administrator=True)
    async def schedule_message(self, ctx, user: discord.User, time: str, *, message: str):
        """Schedule a DM to a user."""
        try:
            # Parse time in minutes
            minutes = int(time.rstrip('min'))
            scheduled_time = datetime.utcnow() + timedelta(minutes=minutes)

            await ctx.send(f"Message scheduled to be sent to {user} in {minutes} minute(s) at {scheduled_time}.")
            await asyncio.sleep(minutes * 60)
            dm_embed = discord.Embed(title="Scheduled Message", description=message, color=discord.Color.gold())
            dm_embed.set_thumbnail(url=self.bot.user.avatar_url)
            await user.send(embed=dm_embed)
        except ValueError:
            await ctx.send("Invalid time format. Use `Xmin` where X is the number of minutes.")

    @commands.command(name='viewuserdata')
    async def view_user_data(self, ctx, user: discord.User):
        """View user purchase data."""
        if user.id in self.user_data:
            embed = discord.Embed(title=f"{user}'s Purchase History", color=discord.Color.blue())
            for purchase in self.user_data[user.id]:
                embed.add_field(
                    name=f"{purchase['product']} (UUID: ||{purchase['uuid']}||)",
                    value=f"Quantity: **{purchase['quantity']}** | Price: **{purchase['price']}** | Time: {purchase['time'].strftime('%Y-%m-%d %H:%M:%S UTC')}",
                    inline=False
                )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="No Data", description="No purchase data found for this user.", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.command(name='setroles')
    @commands.has_permissions(administrator=True)
    async def set_roles(self, ctx, *roles: discord.Role):
        """Set roles that have access to product commands."""
        self.roles = {role.id: role.name for role in roles}
        role_names = ", ".join(self.roles.values())
        embed = discord.Embed(title="Roles Updated", description=f"The following roles have access to product commands: {role_names}", color=discord.Color.green())
        await ctx.send(embed=embed)

    @commands.command(name='setlog')
    @commands.has_permissions(administrator=True)
    async def set_log_channel(self, ctx, channel: discord.TextChannel):
        """Set the log channel for stock changes and user purchases."""
        self.log_channels[ctx.guild.id] = channel.id
        embed = discord.Embed(title="Log Channel Set", description=f"Logs will be sent to {channel.mention}.", color=discord.Color.green())
        await ctx.send(embed=embed)

    async def log_stock_change(self, ctx, action: str, product: str, quantity: int):
        """Log stock changes."""
        if ctx.guild.id in self.log_channels:
            log_channel = self.bot.get_channel(self.log_channels[ctx.guild.id])
            embed = discord.Embed(title="Stock Change Log", color=discord.Color.orange())
            embed.add_field(name="Action", value=action)
            embed.add_field(name="Product", value=product)
            embed.add_field(name="Quantity", value=quantity)
            await log_channel.send(embed=embed)

    async def log_purchase(self, ctx, user: discord.User, product: str, quantity: int, price: float, uuid: str):
        """Log user purchases."""
        if ctx.guild.id in self.log_channels:
            log_channel = self.bot.get_channel(self.log_channels[ctx.guild.id])
            embed = discord.Embed(title="Purchase Log", color=discord.Color.orange())
            embed.add_field(name="User", value=str(user))
            embed.add_field(name="Product", value=product)
            embed.add_field(name="Quantity", value=quantity)
            embed.add_field(name="Price", value=price)
            embed.add_field(name="UUID", value=f"||{uuid}||")
            await log_channel.send(embed=embed)

    async def log_replacement(self, ctx, user: discord.User, old_product: str, quantity: int, replacement_message: str):
        """Log product replacements."""
        if ctx.guild.id in self.log_channels:
            log_channel = self.bot.get_channel(self.log_channels[ctx.guild.id])
            embed = discord.Embed(title="Replacement Log", color=discord.Color.orange())
            embed.add_field(name="User", value=str(user))
            embed.add_field(name="Old Product", value=old_product)
            embed.add_field(name="Quantity", value=quantity)
            embed.add_field(name="Replacement Message", value=replacement_message)
            await log_channel.send(embed=embed)

    def get_product_data_by_uuid(self, user: discord.User, uuid: str):
        """Get product data by UUID from user purchase history."""
        if user.id in self.user_data:
            for purchase in self.user_data[user.id]:
                if purchase['uuid'] == uuid:
                    return purchase
        return None

async def setup(bot):
    await bot.add_cog(ProductCog(bot))
