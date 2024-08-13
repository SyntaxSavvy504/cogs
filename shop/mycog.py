import discord
from redbot.core import commands
import sqlite3
import random
from datetime import datetime

class ProductCog(commands.Cog):
    """Product management and delivery cog with SQLite integration and user data tracking"""

    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect('database.db')
        self.cursor = self.conn.cursor()
        self.setup_db()
        self.roles = {}  # Dictionary to store role permissions
        self.log_channels = {}  # Dictionary to store logging channels

    def setup_db(self):
        """Set up the SQLite database with the necessary tables."""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock (
                product TEXT PRIMARY KEY,
                quantity INTEGER,
                price REAL,
                emoji TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_data (
                user_id INTEGER,
                product TEXT,
                quantity INTEGER,
                price REAL,
                time TEXT,
                uuid TEXT,
                PRIMARY KEY (user_id, uuid)
            )
        ''')
        self.conn.commit()

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
        if self.product_exists(name):
            self.cursor.execute('UPDATE stock SET quantity = quantity + ? WHERE product = ?', (quantity, name))
        else:
            self.cursor.execute('INSERT INTO stock (product, quantity, price, emoji) VALUES (?, ?, ?, ?)', (name, quantity, 0, emoji))

        self.conn.commit()
        embed = discord.Embed(title="Product Added", description=f"{name} has been added to stock.", color=discord.Color.green())
        embed.add_field(name="Product", value=f"{name} {emoji if emoji else ''}")
        embed.add_field(name="Quantity", value=quantity)
        await ctx.send(embed=embed)
        await self.log_stock_change(ctx, "Added", name, quantity)

    @product.command(name='remove')
    @commands.has_permissions(administrator=True)
    async def remove_product(self, ctx, name: str, quantity: int):
        """Remove a product from stock."""
        if self.product_exists(name):
            self.cursor.execute('SELECT quantity FROM stock WHERE product = ?', (name,))
            current_quantity = self.cursor.fetchone()[0]
            if current_quantity >= quantity:
                new_quantity = current_quantity - quantity
                if new_quantity > 0:
                    self.cursor.execute('UPDATE stock SET quantity = ? WHERE product = ?', (new_quantity, name))
                else:
                    self.cursor.execute('DELETE FROM stock WHERE product = ?', (name,))
                self.conn.commit()
                embed = discord.Embed(title="Product Removed", description=f"{name} has been removed from stock.", color=discord.Color.red())
                embed.add_field(name="Product", value=name)
                embed.add_field(name="Quantity", value=quantity)
                await ctx.send(embed=embed)
                await self.log_stock_change(ctx, "Removed", name, quantity)
            else:
                embed = discord.Embed(title="Error", description="Not enough stock or product not found.", color=discord.Color.red())
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="Error", description="Product not found.", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.command(name='stock')
    async def stock_info(self, ctx):
        """Show current stock info."""
        self.cursor.execute('SELECT * FROM stock')
        products = self.cursor.fetchall()
        
        if not products:
            embed = discord.Embed(title="Stock Info", description="No products in stock.", color=discord.Color.yellow())
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(title="Current Stock", color=discord.Color.blue())
        for product, quantity, price, emoji in products:
            embed.add_field(name=f"{product} {emoji if emoji else ''}", value=f"Quantity: {quantity} | Price: {price}", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name='delivery')
    async def delivery(self, ctx, user: discord.User, quantity: int, price: float, product: str, *, custom_message: str = None):
        """Send a delivery embed and track user purchase with an optional custom message."""
        uuid = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=4))  # Generate a 4-digit alphanumeric UUID

        if self.product_exists(product):
            self.cursor.execute('SELECT quantity FROM stock WHERE product = ?', (product,))
            current_quantity = self.cursor.fetchone()[0]
            if current_quantity >= quantity:
                self.cursor.execute('UPDATE stock SET quantity = quantity - ? WHERE product = ?', (quantity, product))
                self.conn.commit()

                # Record user purchase data
                now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                self.cursor.execute('INSERT INTO user_data (user_id, product, quantity, price, time, uuid) VALUES (?, ?, ?, ?, ?, ?)', 
                                    (user.id, product, quantity, price, now, uuid))
                self.conn.commit()

                # Send delivery embed
                embed = discord.Embed(title="Product Delivery", description="Product has been delivered.", color=discord.Color.purple())
                embed.set_thumbnail(url=self.bot.user.avatar_url)
                embed.add_field(name="Product", value=f"**{product}**")
                embed.add_field(name="Quantity", value=f"**{quantity}**")
                embed.add_field(name="Price", value=f"**{price}**")
                embed.add_field(name="UUID", value=f"||{uuid}||")
                if custom_message:
                    embed.add_field(name="Custom Message", value=custom_message)
                await user.send(embed=embed)
                await ctx.send(f"Delivery sent to {user.mention}.")
            else:
                embed = discord.Embed(title="Error", description="Not enough stock or product not found.", color=discord.Color.red())
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="Error", description="Product not found.", color=discord.Color.red())
            await ctx.send(embed=embed)

    def product_exists(self, name: str) -> bool:
        """Check if a product exists in the stock."""
        self.cursor.execute('SELECT COUNT(*) FROM stock WHERE product = ?', (name,))
        return self.cursor.fetchone()[0] > 0

    async def log_stock_change(self, ctx, action: str, product: str, quantity: int):
        """Log stock changes to a specific channel."""
        if self.log_channels:
            log_channel = self.bot.get_channel(self.log_channels.get('stock'))
            if log_channel:
                embed = discord.Embed(title="Stock Change", description=f"{action} action performed.", color=discord.Color.orange())
                embed.add_field(name="Product", value=product)
                embed.add_field(name="Quantity", value=quantity)
                embed.add_field(name="User", value=ctx.author)
                embed.set_footer(text=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
                await log_channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ProductCog(bot))
