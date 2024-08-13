from redbot.core import commands
import discord

class ProductCog(commands.Cog):
    """Product management and delivery cog"""

    def __init__(self, bot):
        self.bot = bot
        self.stock = {}

    @commands.group(invoke_without_command=True)
    async def product(self, ctx):
        """Product management commands."""
        await ctx.send("Use `!product add <name> <quantity>` to add a product, or `!product remove <name> <quantity>` to remove a product.")

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
            await ctx.send("Not enough stock or product not found.")

    @commands.command(name='stock')
    async def stock_info(self, ctx):
        """Show current stock info."""
        if not self.stock:
            await ctx.send("No products in stock.")
            return

        embed = discord.Embed(title="Current Stock", color=discord.Color.blue())
        for product, quantity in self.stock.items():
            embed.add_field(name=product, value=f"Quantity: {quantity}", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name='delivery')
    async def delivery(self, ctx, quantity: int, price: float, product: str):
        """Send a delivery embed."""
        if product in self.stock and self.stock[product] >= quantity:
            self.stock[product] -= quantity
            if self.stock[product] == 0:
                del self.stock[product]

            embed = discord.Embed(title="Product Delivery", description="Product has been delivered.", color=discord.Color.purple())
            embed.add_field(name="Product", value=product)
            embed.add_field(name="Quantity", value=quantity)
            embed.add_field(name="Price", value=price)
            await ctx.send(embed=embed)
        else:
            await ctx.send("Not enough stock or product not found.")

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
            await ctx.send("Not enough stock or old product not found.")

async def setup(bot):
    await bot.add_cog(ProductCog(bot))
