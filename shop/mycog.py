from redbot.core import commands
import discord
from datetime import datetime
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
            embed.add_field(name="Product", value=product)
            embed.add_field(name="Quantity", value=quantity)
            embed.add_field(name="Price", value=price)
            embed.add_field(name="UUID", value=uuid)
            if custom_message:
                embed.add_field(name="Message", value=custom_message, inline=False)
            await ctx.send(embed=embed)

            # Send DM to user
            dm_embed = discord.Embed(title="Delivery Confirmation", description=f"You have received {quantity} of {product}.", color=discord.Color.green())
            dm_embed.add_field(name="Product", value=product)
            dm_embed.add_field(name="Quantity", value=quantity)
            dm_embed.add_field(name="Price", value=price)
            dm_embed.add_field(name="UUID", value=uuid)
            if custom_message:
                dm_embed.add_field(name="Message", value=custom_message, inline=False)
            await user.send(embed=dm_embed)

            await self.log_purchase(ctx, user, product, quantity, price, uuid)
        else:
            embed = discord.Embed(title="Error", description="Not enough stock or product not found.", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.command(name='replace')
    async def replace_product(self, ctx, user: discord.User, old_product_uuid: str, new_product: str, quantity: int):
        """Replace one product with another using UUID."""
        old_product = self.get_product_by_uuid(old_product_uuid)
        if old_product and old_product in self.stock and self.stock[old_product]['quantity'] >= quantity:
            self.stock[old_product]['quantity'] -= quantity
            if self.stock[old_product]['quantity'] == 0:
                del self.stock[old_product]

            if new_product in self.stock:
                self.stock[new_product]['quantity'] += quantity
            else:
                self.stock[new_product] = {'quantity': quantity, 'emoji': None}

            embed = discord.Embed(title="Product Replaced", description="Product has been replaced.", color=discord.Color.orange())
            embed.add_field(name="Old Product", value=old_product)
            embed.add_field(name="New Product", value=new_product)
            embed.add_field(name="Quantity", value=quantity)
            await ctx.send(embed=embed)

            # Send DM to user
            dm_embed = discord.Embed(title="Product Replacement", description=f"Your product has been replaced.", color=discord.Color.orange())
            dm_embed.add_field(name="Old Product", value=old_product)
            dm_embed.add_field(name="New Product", value=new_product)
            dm_embed.add_field(name="Quantity", value=quantity)
            await user.send(embed=dm_embed)

            await self.log_replacement(ctx, user, old_product, new_product, quantity)
        else:
            embed = discord.Embed(title="Error", description="Not enough stock or old product not found.", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.command(name='schedule')
    @commands.has_permissions(administrator=True)
    async def schedule_message(self, ctx, user: discord.User, time: str, *, message: str):
        """Schedule a DM to a user."""
        try:
            scheduled_time = datetime.strptime(time, "%Y-%m-%d %H:%M:%S")
            now = datetime.utcnow()
            delay = (scheduled_time - now).total_seconds()

            if delay > 0:
                await ctx.send(f"Message scheduled to be sent to {user} at {scheduled_time}.")
                await asyncio.sleep(delay)
                dm_embed = discord.Embed(title="Scheduled Message", description=message, color=discord.Color.gold())
                await user.send(embed=dm_embed)
            else:
                await ctx.send("The scheduled time must be in the future.")
        except ValueError:
            await ctx.send("Invalid time format. Use `YYYY-MM-DD HH:MM:SS`.")

    @commands.command(name='viewuserdata')
    async def view_user_data(self, ctx, user: discord.User):
        """View user purchase data."""
        if user.id in self.user_data:
            embed = discord.Embed(title=f"{user}'s Purchase History", color=discord.Color.blue())
            for data in self.user_data[user.id]:
                embed.add_field(name=data['time'].strftime("%Y-%m-%d %H:%M:%S"), value=f"Product: {data['product']}\nQuantity: {data['quantity']}\nPrice: {data['price']}\nUUID: {data['uuid']}", inline=False)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="No Data", description=f"No purchase data found for {user}.", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.command(name='setroles')
    @commands.has_permissions(administrator=True)
    async def set_roles(self, ctx, role: discord.Role):
        """Set a role to access product management commands."""
        self.roles[role.id] = True
        embed = discord.Embed(title="Role Set", description=f"Role {role.name} has been granted access to product management commands.", color=discord.Color.green())
        await ctx.send(embed=embed)

    @commands.command(name='setlog')
    @commands.has_permissions(administrator=True)
    async def set_log(self, ctx, log_type: str, channel: discord.TextChannel):
        """Set different channels for logging stock changes, purchases, and replacements."""
        if log_type in ["stock", "purchase", "replacement"]:
            self.log_channels[log_type] = channel.id
            embed = discord.Embed(title="Log Channel Set", description=f"Logging channel for {log_type} has been set to {channel.mention}.", color=discord.Color.green())
            await ctx.send(embed=embed)
        else:
            await ctx.send("Invalid log type. Use 'stock', 'purchase', or 'replacement'.")

    async def log_stock_change(self, ctx, action: str, product: str, quantity: int):
        """Log stock changes."""
        if 'stock' in self.log_channels:
            channel = self.bot.get_channel(self.log_channels['stock'])
            if channel:
                embed = discord.Embed(title="Stock Change", color=discord.Color.orange())
                embed.add_field(name="Action", value=action)
                embed.add_field(name="Product", value=product)
                embed.add_field(name="Quantity", value=quantity)
                embed.add_field(name="By", value=ctx.author)
                await channel.send(embed=embed)

    async def log_purchase(self, ctx, user: discord.User, product: str, quantity: int, price: float, uuid: str):
        """Log user purchases."""
        if 'purchase' in self.log_channels:
            channel = self.bot.get_channel(self.log_channels['purchase'])
            if channel:
                embed = discord.Embed(title="Purchase", color=discord.Color.green())
                embed.add_field(name="User", value=user)
                embed.add_field(name="Product", value=product)
                embed.add_field(name="Quantity", value=quantity)
                embed.add_field(name="Price", value=price)
                embed.add_field(name="UUID", value=uuid)
                embed.add_field(name="Date", value=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
                embed.add_field(name="By", value=ctx.author)
                await channel.send(embed=embed)

    async def log_replacement(self, ctx, user: discord.User, old_product: str, new_product: str, quantity: int):
        """Log product replacements."""
        if 'replacement' in self.log_channels:
            channel = self.bot.get_channel(self.log_channels['replacement'])
            if channel:
                embed = discord.Embed(title="Product Replacement", color=discord.Color.orange())
                embed.add_field(name="User", value=user)
                embed.add_field(name="Old Product", value=old_product)
                embed.add_field(name="New Product", value=new_product)
                embed.add_field(name="Quantity", value=quantity)
                embed.add_field(name="Date", value=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
                embed.add_field(name="By", value=ctx.author)
                await channel.send(embed=embed)

    def get_product_by_uuid(self, uuid: str):
        """Get product name by UUID (mock implementation)."""
        # You need to replace this with actual implementation
        # For now, this is just a placeholder that returns None
        return None

async def setup(bot):
    await bot.add_cog(ProductCog(bot))
