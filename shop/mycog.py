from redbot.core import commands
import discord
from datetime import datetime
import sqlite3
import random
import os

class ProductCog(commands.Cog):
    """Product management and delivery cog with persistent user data tracking."""

    def __init__(self, bot):
        self.bot = bot
        self.db_file = "product_data.db"  # Local file, not used for SQLiteCloud
        self.connection_string = "sqlitecloud://cxghu5vjik.sqlite.cloud:8860?apikey=SMuTVFyDkbis4918QwBKoWhCI7NluTal0LGPPLdaymU"
        self.conn = self.create_connection()
        self.cursor = self.conn.cursor()
        self.create_tables()
        self.load_data()

    def create_connection(self):
        """Create a database connection to SQLiteCloud."""
        try:
            conn = sqlite3.connect(self.db_file)  # Placeholder connection
            return conn
        except Exception as e:
            print(f"Error connecting to the database: {e}")
            raise

    def create_tables(self):
        """Create tables if they do not exist."""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock (
                name TEXT PRIMARY KEY,
                quantity INTEGER,
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
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS log_channels (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER
            )
        ''')
        self.conn.commit()

    def load_data(self):
        """Load data from the SQLite database."""
        self.cursor.execute("SELECT * FROM stock")
        self.stock = {row[0]: {'quantity': row[1], 'emoji': row[2]} for row in self.cursor.fetchall()}

        self.cursor.execute("SELECT * FROM user_data")
        self.user_data = {}
        for row in self.cursor.fetchall():
            user_id = row[0]
            if user_id not in self.user_data:
                self.user_data[user_id] = []
            self.user_data[user_id].append({
                'product': row[1],
                'quantity': row[2],
                'price': row[3],
                'time': datetime.fromisoformat(row[4]),
                'uuid': row[5]
            })

        self.cursor.execute("SELECT * FROM log_channels")
        self.log_channels = {row[0]: row[1] for row in self.cursor.fetchall()}

    def save_data(self):
        """Save data to the SQLite database."""
        self.cursor.execute("DELETE FROM stock")
        for product, info in self.stock.items():
            self.cursor.execute("INSERT INTO stock (name, quantity, emoji) VALUES (?, ?, ?)",
                                (product, info['quantity'], info['emoji']))

        self.cursor.execute("DELETE FROM user_data")
        for user_id, purchases in self.user_data.items():
            for purchase in purchases:
                self.cursor.execute("INSERT INTO user_data (user_id, product, quantity, price, time, uuid) VALUES (?, ?, ?, ?, ?, ?)",
                                    (user_id, purchase['product'], purchase['quantity'], purchase['price'], purchase['time'].isoformat(), purchase['uuid']))

        self.cursor.execute("DELETE FROM log_channels")
        for guild_id, channel_id in self.log_channels.items():
            self.cursor.execute("INSERT INTO log_channels (guild_id, channel_id) VALUES (?, ?)",
                                (guild_id, channel_id))

        self.conn.commit()

    @commands.group(name="product", invoke_without_command=True)
    async def product(self, ctx: commands.Context):
        """Product management commands."""
        embed = discord.Embed(
            title="Product Commands",
            description="Manage products with the following commands:",
            color=discord.Color.blue()
        )
        embed.add_field(name="Add Product", value="`!product add <name> <quantity> [emoji]`", inline=False)
        embed.add_field(name="Remove Product", value="`!product remove <name> <quantity>`", inline=False)
        await ctx.send(embed=embed)

    @product.command(name='add')
    @commands.has_permissions(administrator=True)
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

    @commands.command(name='stock')
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

    @commands.command(name='delivery')
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

            await self.log_delivery(ctx, user, product, quantity, price, uuid)
        else:
            embed = discord.Embed(title="Error", description="Not enough stock or product not found.", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.command(name='viewuserdata')
    async def view_user_data(self, ctx: commands.Context, user: discord.User):
        """View a user's purchase data."""
        if user.id in self.user_data:
            embed = discord.Embed(title=f"{user.name}'s Purchase Data", color=discord.Color.orange())
            for purchase in self.user_data[user.id]:
                embed.add_field(name=f"Product: {purchase['product']} (UUID: ||{purchase['uuid']}||)",
                                value=f"Quantity: {purchase['quantity']} | Price: {purchase['price']} | Time: {purchase['time'].strftime('%Y-%m-%d %H:%M:%S')}",
                                inline=False)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="Error", description="No purchase data found for this user.", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.command(name='setlog')
    @commands.has_permissions(administrator=True)
    async def set_log_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set a channel for logging stock changes and user purchases."""
        self.log_channels[ctx.guild.id] = channel.id
        self.save_data()
        await ctx.send(f"Log channel set to {channel.mention}")

    @commands.command(name='manageconnection')
    @commands.is_owner()
    async def manage_connection(self, ctx: commands.Context, command: str):
        """Manually manage the SQLiteCloud connection."""
        if command == 'reconnect':
            try:
                self.conn = self.create_connection()
                self.cursor = self.conn.cursor()
                await ctx.send("Reconnected to SQLiteCloud successfully.")
            except Exception as e:
                await ctx.send(f"Error reconnecting: {e}")
        else:
            await ctx.send("Unknown command. Use 'reconnect' to reconnect to SQLiteCloud.")

    async def log_stock_change(self, ctx: commands.Context, action: str, product: str, quantity: int):
        """Log stock changes to the specified channel."""
        channel_id = self.log_channels.get(ctx.guild.id)
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                embed = discord.Embed(title="Stock Change", description=f"{action} in stock", color=discord.Color.blue())
                embed.add_field(name="Product", value=product)
                embed.add_field(name="Quantity", value=quantity)
                await channel.send(embed=embed)

    async def log_delivery(self, ctx: commands.Context, user: discord.User, product: str, quantity: int, price: float, uuid: str):
        """Log delivery information to the specified channel."""
        channel_id = self.log_channels.get(ctx.guild.id)
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                embed = discord.Embed(title="Delivery Log", description="Product delivery recorded", color=discord.Color.purple())
                embed.add_field(name="User", value=user.mention)
                embed.add_field(name="Product", value=product)
                embed.add_field(name="Quantity", value=quantity)
                embed.add_field(name="Price", value=price)
                embed.add_field(name="UUID", value=f"||{uuid}||")
                await channel.send(embed=embed)

def setup(bot):
    bot.add_cog(ProductCog(bot))
