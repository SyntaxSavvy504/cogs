from redbot.core import commands
import discord
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
import random
import json
import os

class ProductCog(commands.Cog):
    """Product management and delivery cog with persistent user data tracking."""

    def __init__(self, bot):
        self.bot = bot
        self.data_file = "product_data.json"
        self.load_data()

    def load_data(self):
        """Load data from a JSON file."""
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r') as f:
                data = json.load(f)
                self.stock = data.get("stock", {})
                self.user_data = data.get("user_data", {})
                self.roles = data.get("roles", {})
                self.log_channels = data.get("log_channels", {})
        else:
            self.stock = {}
            self.user_data = {}
            self.roles = {}
            self.log_channels = {}

    def save_data(self):
        """Save data to a JSON file."""
        data = {
            "stock": self.stock,
            "user_data": self.user_data,
            "roles": self.roles,
            "log_channels": self.log_channels
        }
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=4)

    @commands.hybrid_group(name="product", invoke_without_command=True)
    @app_commands.describe(
        ctx="The command context"
    )
    async def product(self, ctx: commands.Context):
        """Product management commands."""
        embed = discord.Embed(
            title="Product Commands",
            description="Manage products with the following commands:",
            color=discord.Color.blue()
        )
        embed.add_field(name="Add Product", value="`/product add <name> <quantity> [emoji]`", inline=False)
        embed.add_field(name="Remove Product", value="`/product remove <name> <quantity>`", inline=False)
        await ctx.send(embed=embed)

    @product.command(name='add')
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        name="The name of the product",
        quantity="The quantity of the product",
        emoji="Optional emoji to associate with the product"
    )
    async def add_product(self, ctx: commands.Context, name: str, quantity: int, emoji: str = None):
        """Add a product to stock with an optional emoji."""
        if name in self.stock:
            self.stock[name]['quantity'] += quantity
        else:
            self.stock[name] = {'quantity': quantity, 'emoji': emoji}

        self.save_data()

        embed = discord.Embed(title="Product Added", description=f"{name} has been added to stock.", color=discord.Color.green())
        embed.add_field(name="Product", value=f"{name} {emoji if emoji else ''}")
        embed.add_field(name="Quantity", value=quantity)
        await ctx.send(embed=embed)
        await self.log_stock_change(ctx, "Added", name, quantity)

    @product.command(name='remove')
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        name="The name of the product",
        quantity="The quantity of the product to remove"
    )
    async def remove_product(self, ctx: commands.Context, name: str, quantity: int):
        """Remove a product from stock."""
        if name in self.stock and self.stock[name]['quantity'] >= quantity:
            self.stock[name]['quantity'] -= quantity
            if self.stock[name]['quantity'] == 0:
                del self.stock[name]

            self.save_data()

            embed = discord.Embed(title="Product Removed", description=f"{name} has been removed from stock.", color=discord.Color.red())
            embed.add_field(name="Product", value=name)
            embed.add_field(name="Quantity", value=quantity)
            await ctx.send(embed=embed)
            await self.log_stock_change(ctx, "Removed", name, quantity)
        else:
            embed = discord.Embed(title="Error", description="Not enough stock or product not found.", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.hybrid_command(name='stock')
    @app_commands.describe(ctx="The command context")
    async def stock_info(self, ctx: commands.Context):
        """Show current stock info."""
        if not self.stock:
            embed = discord.Embed(title="Stock Info", description="No products in stock.", color=discord.Color.yellow())
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(title="Current Stock", color=discord.Color.blue())
        for product, info in self.stock.items():
            embed.add_field(name=f"{product} {info['emoji'] if info['emoji'] else ''}", value=f"Quantity: {info['quantity']}", inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='delivery')
    @app_commands.describe(
        ctx="The command context",
        user="The user to send the delivery to",
        quantity="The quantity of the product",
        price="The price of the product",
        product="The name of the product",
        custom_message="An optional custom message"
    )
    async def delivery(self, ctx: commands.Context, user: discord.User, quantity: int, price: float, product: str, *, custom_message: str = None):
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

            self.save_data()

            # Send delivery embed
            embed = discord.Embed(title="Product Delivery", description="Product has been delivered.", color=discord.Color.purple())
            embed.set_thumbnail(url=self.bot.user.avatar.url)
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
            dm_embed.set_thumbnail(url=self.bot.user.avatar.url)
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

    @commands.hybrid_command(name='replace')
    @app_commands.describe(
        ctx="The command context",
        user="The user whose product will be replaced",
        old_product_uuid="The UUID of the product to replace",
        replacement_message="The message explaining the replacement"
    )
    async def replace_product(self, ctx: commands.Context, user: discord.User, old_product_uuid: str, *, replacement_message: str):
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

                self.save_data()

                embed = discord.Embed(title="Product Replaced", description="User's product has been replaced.", color=discord.Color.orange())
                embed.add_field(name="Old Product", value=f"**{old_product}**")
                embed.add_field(name="Quantity", value=f"**{quantity}**")
                embed.add_field(name="Replacement Message", value=replacement_message)
                await ctx.send(embed=embed)

                # Send DM to user
                dm_embed = discord.Embed(title="Product Replacement", description=f"Your product '{old_product}' has been replaced.", color=discord.Color.orange())
                dm_embed.add_field(name="Replacement Message", value=replacement_message)
                await user.send(embed=dm_embed)
            else:
                embed = discord.Embed(title="Error", description="Not enough stock or product not found.", color=discord.Color.red())
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="Error", description="UUID not found.", color=discord.Color.red())
            await ctx.send(embed=embed)

    def get_product_data_by_uuid(self, user, uuid):
        """Retrieve product data by UUID for a specific user."""
        if user.id in self.user_data:
            for product_data in self.user_data[user.id]:
                if product_data['uuid'] == uuid:
                    return product_data
        return None

    async def log_stock_change(self, ctx, action, product, quantity):
        """Log stock changes to the log channel."""
        if ctx.guild.id in self.log_channels:
            log_channel = self.bot.get_channel(self.log_channels[ctx.guild.id])
            if log_channel:
                embed = discord.Embed(
                    title="Stock Change",
                    description=f"Product '{product}' has been {action}.",
                    color=discord.Color.dark_blue()
                )
                embed.add_field(name="Product", value=product)
                embed.add_field(name="Quantity", value=quantity)
                embed.add_field(name="Action", value=action)
                embed.set_footer(text=f"Performed by {ctx.author.name}")
                await log_channel.send(embed=embed)

    async def log_purchase(self, ctx, user, product, quantity, price, uuid):
        """Log purchases to the log channel."""
        if ctx.guild.id in self.log_channels:
            log_channel = self.bot.get_channel(self.log_channels[ctx.guild.id])
            if log_channel:
                embed = discord.Embed(
                    title="Product Purchase",
                    description=f"{user.name} purchased '{product}'.",
                    color=discord.Color.dark_green()
                )
                embed.add_field(name="User", value=user.mention)
                embed.add_field(name="Product", value=product)
                embed.add_field(name="Quantity", value=quantity)
                embed.add_field(name="Price", value=f"${price}")
                embed.add_field(name="UUID", value=uuid)
                await log_channel.send(embed=embed)
