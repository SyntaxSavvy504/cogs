import discord
from redbot.core import commands
import sqlite3
import uuid
import random
from datetime import datetime, timedelta
import asyncio

class Manager(commands.Cog):
    """Product management and delivery cog with SQLite integration and user data tracking"""

    def __init__(self, bot):
        self.bot = bot
        self.db_url = 'sqlitecloud://cxghu5vjik.sqlite.cloud:8860?apikey=SMuTVFyDkbis4918QwBKoWhCI7NluTal0LGPPLdaymU'
        self.setup_db()
        self.roles = {}  # Dictionary to store role permissions
        self.log_channels = {}  # Dictionary to store logging channels

    def setup_db(self):
        """Set up the SQLite database with the necessary tables."""
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock (
                product TEXT PRIMARY KEY,
                quantity INTEGER,
                price REAL,
                emoji TEXT
            )
        ''')
        cursor.execute('''
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
        conn.commit()
        conn.close()

    @commands.group(invoke_without_command=True)
    async def product(self, ctx):
        """Product management commands."""
        embed = discord.Embed(title="Product Commands", description="Manage products with the following commands:", color=discord.Color.blue())
        embed.add_field(name="Add Product", value="`!product add <name> <quantity> [emoji]`", inline=False)
        embed.add_field(name="Remove Product", value="`!product remove <name> <quantity>`", inline=False)
        embed.add_field(name="Stock Info", value="`!stock`", inline=False)
        embed.add_field(name="Delivery", value="`!delivery <user> <quantity> <price> <product> [text]`", inline=False)
        embed.add_field(name="Replace", value="`!replace <user> <uuid> [message]`", inline=False)
        embed.add_field(name="Schedule", value="`!schedule <user> <time> <message>`", inline=False)
        embed.add_field(name="View User Data", value="`!viewuserdata <user>`", inline=False)
        await ctx.send(embed=embed)

    @product.command(name='add')
    @commands.has_permissions(administrator=True)
    async def add_product(self, ctx, name: str, quantity: int, emoji: str = None):
        """Add a product to stock with an optional emoji."""
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO stock (product, quantity, price, emoji)
            VALUES (?, ?, 0, ?)
            ON CONFLICT(product) DO UPDATE SET quantity = quantity + excluded.quantity
        ''', (name, quantity, emoji))
        conn.commit()
        conn.close()

        embed = discord.Embed(title="Product Added", description=f"{name} has been added to stock.", color=discord.Color.green())
        embed.add_field(name="Product", value=f"{name} {emoji if emoji else ''}")
        embed.add_field(name="Quantity", value=quantity)
        await ctx.send(embed=embed)
        await self.log_stock_change(ctx, "Added", name, quantity)

    @product.command(name='remove')
    @commands.has_permissions(administrator=True)
    async def remove_product(self, ctx, name: str, quantity: int):
        """Remove a product from stock."""
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT quantity FROM stock WHERE product = ?', (name,))
        result = cursor.fetchone()
        if result and result[0] >= quantity:
            cursor.execute('''
                UPDATE stock SET quantity = quantity - ? WHERE product = ?
            ''', (quantity, name))
            cursor.execute('DELETE FROM stock WHERE quantity = 0 AND product = ?', (name,))
            conn.commit()
            conn.close()

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
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM stock')
        stocks = cursor.fetchall()
        conn.close()

        embed = discord.Embed(title="Current Stock", color=discord.Color.blue())
        for index, (product, quantity, _, emoji) in enumerate(stocks, start=1):
            embed.add_field(name=f"Item #{index} {emoji if emoji else ''}", value=f"**Product:** {product}\n**Quantity:** {quantity}", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name='delivery')
    async def delivery(self, ctx, user: discord.User, quantity: int, price: float, product: str, *, custom_message: str = None):
        """Send a delivery embed and track user purchase with an optional custom message."""
        uuid_str = f"{random.randint(1000, 9999)}"  # Generate a 4-digit UUID
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT quantity FROM stock WHERE product = ?', (product,))
        result = cursor.fetchone()
        if result and result[0] >= quantity:
            cursor.execute('''
                UPDATE stock SET quantity = quantity - ? WHERE product = ?
            ''', (quantity, product))
            cursor.execute('DELETE FROM stock WHERE quantity = 0 AND product = ?', (product,))
            cursor.execute('''
                INSERT INTO user_data (user_id, product, quantity, price, time, uuid)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user.id, product, quantity, price, datetime.utcnow().isoformat(), uuid_str))
            conn.commit()
            conn.close()

            # Send delivery embed to channel
            embed = discord.Embed(title="Product Delivery", description="Product has been delivered.", color=discord.Color.purple())
            embed.set_thumbnail(url=self.bot.user.avatar_url)
            embed.add_field(name="Product", value=f"**{product}**")
            embed.add_field(name="Quantity", value=f"**{quantity}**")
            embed.add_field(name="Price", value=f"**{price}**")
            embed.add_field(name="UUID", value=f"||{uuid_str}||")
            if custom_message:
                embed.add_field(name="Message", value=custom_message, inline=False)
            embed.set_footer(text="Vouch for product. No vouch, no warranty.")
            await ctx.send(embed=embed)

            # Send DM to user
            dm_embed = discord.Embed(title="Delivery Confirmation", description=f"You have received {quantity} of {product}.", color=discord.Color.green())
            dm_embed.set_thumbnail(url=self.bot.user.avatar_url)
            dm_embed.add_field(name="Product", value=f"**{product}**")
            dm_embed.add_field(name="Quantity", value=f"**{quantity}**")
            dm_embed.add_field(name="Price", value=f"**{price}**")
            dm_embed.add_field(name="UUID", value=f"||{uuid_str}||")
            if custom_message:
                dm_embed.add_field(name="Message", value=custom_message, inline=False)
            dm_embed.set_footer(text="Vouch for product. No vouch, no warranty.")
            await user.send(embed=dm_embed)

            await self.log_purchase(ctx, user, product, quantity, price, uuid_str)
        else:
            embed = discord.Embed(title="Error", description="Not enough stock or product not found.", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.command(name='replace')
    async def replace_product(self, ctx, user: discord.User, old_product_uuid: str, *, replacement_message: str):
        """Replace a suspended user's product using UUID with a new product."""
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM user_data WHERE user_id = ? AND uuid = ?', (user.id, old_product_uuid))
        old_product_data = cursor.fetchone()
        if old_product_data:
            old_product, quantity, price = old_product_data[1], old_product_data[2], old_product_data[3]

            cursor.execute('SELECT quantity FROM stock WHERE product = ?', (old_product,))
            result = cursor.fetchone()
            if result and result[0] >= quantity:
                cursor.execute('''
                    UPDATE stock SET quantity = quantity - ? WHERE product = ?
                ''', (quantity, old_product))
                cursor.execute('DELETE FROM stock WHERE quantity = 0 AND product = ?', (old_product,))
                conn.commit()
                conn.close()

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
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM user_data WHERE user_id = ?', (user.id,))
        purchases = cursor.fetchall()
        conn.close()

        if purchases:
            embed = discord.Embed(title=f"{user}'s Purchase History", color=discord.Color.blue())
            for purchase in purchases:
                embed.add_field(
                    name=f"{purchase[1]} (UUID: ||{purchase[5]}||)",
                    value=f"Quantity: **{purchase[2]}** | Price: **{purchase[3]}** | Time: {purchase[4]}",
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

async def setup(bot):
    await bot.add_cog(Manager(bot))
