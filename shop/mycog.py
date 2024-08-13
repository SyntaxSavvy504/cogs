from redbot.core import commands
import discord
from datetime import datetime
import asyncio

class ProductCog(commands.Cog):
    """Product management and delivery cog with user data tracking"""

    def __init__(self, bot):
        self.bot = bot
        self.stock = {}
        self.user_data = {}  # Dictionary to store user purchase data

    @commands.group(invoke_without_command=True)
    async def product(self, ctx):
        """Product management commands."""
        embed = discord.Embed(title="Product Commands", description="Manage products with the following commands:", color=discord.Color.blue())
        embed.add_field(name="Add Product", value="`!product add <name> <quantity>`", inline=False)
        embed.add_field(name="Remove Product", value="`!product remove <name> <quantity>`", inline=False)
        await ctx.send(embed=embed)

    @product.command(name='add')
    @commands.has_permissions(administrator=True)
    async def add_product(self, ctx, name: str, quantity: int):
        """Add a product to stock."""
        if name in self.stock:
            self.stock[name] += quantity
        else:
            self.stock[name] = quantity
        
        embed = discord.Embed(title="Product Added", description=f"{name} has been added to stock.", color=discord.Color.green())
        embed.add_field(name="Product", value=name)
        embed.add_field(name="Quantity", value=quantity)
        await ctx.send(embed=embed)

    @product.command(name='remove')
    @commands.has_permissions(administrator=True)
    async def remove_product(self, ctx, name: str, quantity: int):
        """Remove a product from stock."""
        if name in self.stock and self.stock[name] >= quantity:
            self.stock[name] -= quantity
            if self.stock[name] == 0:
                del self.stock[name]
            
            embed = discord.Embed(title="Product Removed", description=f"{name} has been removed from stock.", color=discord.Color.red())
            embed.add_field(name="Product", value=name)
            embed.add_field(name="Quantity", value=quantity)
            await ctx.send(embed=embed)
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
        for product, quantity in self.stock.items():
            embed.add_field(name=product, value=f"Quantity: {quantity}", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name='delivery')
    async def delivery(self, ctx, user: discord.User, quantity: int, price: float, product: str):
        """Send a delivery embed and track user purchase."""
        if product in self.stock and self.stock[product] >= quantity:
            self.stock[product] -= quantity
            if self.stock[product] == 0:
                del self.stock[product]

            # Record user purchase data
            now = datetime.utcnow()
            if user.id not in self.user_data:
                self.user_data[user.id] = []
            self.user_data[user.id].append({
                'product': product,
                'quantity': quantity,
                'price': price,
                'time': now
            })

            # Send delivery embed
            embed = discord.Embed(title="Product Delivery", description="Product has been delivered.", color=discord.Color.purple())
            embed.add_field(name="Product", value=product)
            embed.add_field(name="Quantity", value=quantity)
            embed.add_field(name="Price", value=price)
            await ctx.send(embed=embed)

            # Send DM to user
            dm_embed = discord.Embed(title="Delivery Confirmation", description=f"You have received {quantity} of {product}.", color=discord.Color.green())
            dm_embed.add_field(name="Product", value=product)
            dm_embed.add_field(name="Quantity", value=quantity)
            dm_embed.add_field(name="Price", value=price)
            await user.send(embed=dm_embed)
        else:
            embed = discord.Embed(title="Error", description="Not enough stock or product not found.", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.command(name='replace')
    async def replace_product(self, ctx, old_product: str, new_product: str, quantity: int):
        """Replace one product with another."""
        if old_product in self.stock and self.stock[old_product] >= quantity:
            self.stock[old_product] -= quantity
            if self.stock[old_product] == 0:
                del self.stock[old_product]

            if new_product in self.stock:
                self.stock[new_product] += quantity
            else:
                self.stock[new_product] = quantity

            embed = discord.Embed(title="Product Replaced", description="Product has been replaced.", color=discord.Color.orange())
            embed.add_field(name="Old Product", value=old_product)
            embed.add_field(name="New Product", value=new_product)
            embed.add_field(name="Quantity", value=quantity)
            await ctx.send(embed=embed)
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
                embed.add_field(name=data['time'].strftime("%Y-%m-%d %H:%M:%S"), value=f"Product: {data['product']}\nQuantity: {data['quantity']}\nPrice: {data['price']}", inline=False)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="No Data", description=f"No purchase data found for {user}.", color=discord.Color.red())
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ProductCog(bot))
