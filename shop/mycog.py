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
        self.db_file = "product_data.db"
        self.conn = sqlite3.connect(self.db_file)
        self.cursor = self.conn.cursor()
        self.create_tables()
        self.load_data()

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

            await self.log_purchase(ctx, user, product, quantity, price, uuid)
        else:
            embed = discord.Embed(title="Error", description="Not enough stock or product not found.", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.command(name='replace')
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
                
                new_product = self.get_replacement_product()
                new_quantity = quantity
                new_price = price

                if new_product in self.stock:
                    self.stock[new_product]['quantity'] += new_quantity
                else:
                    self.stock[new_product] = {'quantity': new_quantity, 'emoji': ''}

                # Update user data
                now = datetime.utcnow()
                self.user_data[user.id] = [item for item in self.user_data[user.id] if item['uuid'] != old_product_uuid]
                self.user_data[user.id].append({
                    'product': new_product,
                    'quantity': new_quantity,
                    'price': new_price,
                    'time': now,
                    'uuid': old_product_uuid
                })

                self.save_data()

                # Send replacement embed
                embed = discord.Embed(title="Product Replacement", description="Your product has been replaced.", color=discord.Color.orange())
                embed.set_thumbnail(url=self.bot.user.avatar.url)
                embed.add_field(name="Old Product", value=f"**{old_product}**")
                embed.add_field(name="New Product", value=f"**{new_product}**")
                embed.add_field(name="Quantity", value=f"**{new_quantity}**")
                embed.add_field(name="Price", value=f"**{new_price}**")
                embed.add_field(name="Message", value=replacement_message, inline=False)
                embed.set_footer(text="NO VOUCH = NO WARRANTY")
                await ctx.send(embed=embed)

                # Notify user
                dm_embed = discord.Embed(title="Replacement Confirmation", description=f"Your product has been replaced with {new_product}.", color=discord.Color.green())
                dm_embed.set_thumbnail(url=self.bot.user.avatar.url)
                dm_embed.add_field(name="Old Product", value=f"**{old_product}**")
                dm_embed.add_field(name="New Product", value=f"**{new_product}**")
                dm_embed.add_field(name="Quantity", value=f"**{new_quantity}**")
                dm_embed.add_field(name="Price", value=f"**{new_price}**")
                dm_embed.add_field(name="Message", value=replacement_message, inline=False)
                dm_embed.set_footer(text="NO VOUCH = NO WARRANTY")
                await user.send(embed=dm_embed)

                await self.log_purchase(ctx, user, new_product, new_quantity, new_price, old_product_uuid)
            else:
                embed = discord.Embed(title="Error", description="Not enough stock of the old product or product not found.", color=discord.Color.red())
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="Error", description="Old product UUID not found.", color=discord.Color.red())
            await ctx.send(embed=embed)

    def get_product_data_by_uuid(self, user, uuid):
        """Retrieve product data by UUID for a specific user."""
        if user.id in self.user_data:
            for item in self.user_data[user.id]:
                if item['uuid'] == uuid:
                    return item
        return None

    def get_replacement_product(self):
        """Simulate fetching a replacement product."""
        # Implement your logic for selecting a replacement product
        # For simplicity, returning a static product name
        return "Replacement Product"

    async def log_stock_change(self, ctx, action, product, quantity):
        """Log stock changes to the specified channel."""
        if ctx.guild.id in self.log_channels:
            channel = self.bot.get_channel(self.log_channels[ctx.guild.id])
            if channel:
                embed = discord.Embed(title="Stock Change", description=f"Product stock updated.", color=discord.Color.blue())
                embed.add_field(name="Action", value=action)
                embed.add_field(name="Product", value=product)
                embed.add_field(name="Quantity", value=quantity)
                await channel.send(embed=embed)

    async def log_purchase(self, ctx, user, product, quantity, price, uuid):
        """Log user purchases to the specified channel."""
        if ctx.guild.id in self.log_channels:
            channel = self.bot.get_channel(self.log_channels[ctx.guild.id])
            if channel:
                embed = discord.Embed(title="Purchase Log", description=f"User purchase recorded.", color=discord.Color.green())
                embed.add_field(name="User", value=user.mention)
                embed.add_field(name="Product", value=product)
                embed.add_field(name="Quantity", value=quantity)
                embed.add_field(name="Price", value=price)
                embed.add_field(name="UUID", value=f"||{uuid}||")
                await channel.send(embed=embed)

    @commands.command(name='setlog')
    @commands.has_permissions(administrator=True)
    async def set_log_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the channel for logging stock changes and user purchases."""
        self.log_channels[ctx.guild.id] = channel.id
        self.save_data()
        await ctx.send(f"Log channel set to {channel.mention}")

    @commands.command(name='viewuserdata')
    async def view_user_data(self, ctx: commands.Context, user: discord.User):
        """View user purchase data."""
        if user.id in self.user_data:
            embed = discord.Embed(title=f"{user.name}'s Purchase Data", color=discord.Color.blue())
            for purchase in self.user_data[user.id]:
                embed.add_field(name=f"Product: {purchase['product']} - UUID: ||{purchase['uuid']}||", value=f"Quantity: {purchase['quantity']}, Price: {purchase['price']}, Time: {purchase['time']}", inline=False)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="No Data", description="No purchase data found for this user.", color=discord.Color.red())
            await ctx.send(embed=embed)

    def cog_unload(self):
        """Close the database connection when the cog is unloaded."""
        self.conn.close()
