import discord
from discord.ext import commands
from datetime import datetime
import asyncio
import uuid
import sqlite3

class ProductCog(commands.Cog):
    """Product management and delivery cog with user data tracking"""

    def __init__(self, bot):
        self.bot = bot
        self.stock = {}
        self.user_data = {}  # Dictionary to store user purchase data
        self.log_channel_id = YOUR_LOG_CHANNEL_ID  # Replace with your log channel ID
        self.allowed_role = None

        # Setup SQLite database
        self.conn = sqlite3.connect('database.db')
        self.cursor = self.conn.cursor()
        self.setup_database()
        self.load_data()

    def setup_database(self):
        """Set up the database schema."""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock (
                product TEXT PRIMARY KEY,
                quantity INTEGER,
                price REAL
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_data (
                user_id INTEGER,
                product TEXT,
                quantity INTEGER,
                price REAL,
                time TEXT,
                delivery_id TEXT,
                PRIMARY KEY (user_id, delivery_id)
            )
        ''')
        self.conn.commit()

    def load_data(self):
        """Load data from the database into memory."""
        self.cursor.execute("SELECT * FROM stock")
        for row in self.cursor.fetchall():
            self.stock[row[0]] = {'quantity': row[1], 'price': row[2]}

    async def log(self, message):
        """Send a log message to the log channel."""
        channel = self.bot.get_channel(self.log_channel_id)
        if channel:
            await channel.send(message)

    @commands.group(invoke_without_command=True)
    async def product(self, ctx):
        """Product management commands."""
        embed = discord.Embed(title="Product Commands", description="Manage products with the following commands:", color=discord.Color.blue())
        embed.add_field(name="Add Product", value="`!product add <name> <quantity> <price> [emoji]`", inline=False)
        embed.add_field(name="Remove Product", value="`!product remove <name> <quantity> [emoji]`", inline=False)
        embed.add_field(name="Replace Product", value="`!product replace <old_name> <new_name> <quantity>`", inline=False)
        await ctx.send(embed=embed)

    @product.command(name='add')
    @commands.has_permissions(administrator=True)
    async def add_product(self, ctx, name: str, quantity: int, price: float, emoji: str = ''):
        """Add a product to stock."""
        if name in self.stock:
            self.stock[name]['quantity'] += quantity
        else:
            self.stock[name] = {'quantity': quantity, 'price': price}
        
        self.cursor.execute("INSERT OR REPLACE INTO stock (product, quantity, price) VALUES (?, ?, ?)", (name, self.stock[name]['quantity'], price))
        self.conn.commit()

        embed = discord.Embed(title="Product Added", description=f"{name} has been added to stock.", color=discord.Color.green())
        embed.add_field(name="Product", value=f"{name} {emoji}")
        embed.add_field(name="Quantity", value=quantity)
        embed.add_field(name="Price", value=price)
        await ctx.send(embed=embed)
        await self.log(f"Product added: {name}, Quantity: {quantity}, Price: {price}")

    @product.command(name='remove')
    @commands.has_permissions(administrator=True)
    async def remove_product(self, ctx, name: str, quantity: int, emoji: str = ''):
        """Remove a product from stock."""
        if name in self.stock and self.stock[name]['quantity'] >= quantity:
            self.stock[name]['quantity'] -= quantity
            if self.stock[name]['quantity'] == 0:
                del self.stock[name]

            self.cursor.execute("DELETE FROM stock WHERE product = ? AND quantity = 0", (name,))
            self.conn.commit()

            embed = discord.Embed(title="Product Removed", description=f"{name} has been removed from stock.", color=discord.Color.red())
            embed.add_field(name="Product", value=f"{name} {emoji}")
            embed.add_field(name="Quantity", value=quantity)
            await ctx.send(embed=embed)
            await self.log(f"Product removed: {name}, Quantity: {quantity}")
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
        for index, (product, details) in enumerate(self.stock.items(), 1):
            embed.add_field(name=f"{index}. {product}", value=f"Quantity: {details['quantity']}\nPrice: {details['price']}", inline=False)
        await ctx.send(embed=embed)
        await self.log(f"Stock info requested by {ctx.author}")

    @commands.command(name='delivery')
    async def delivery(self, ctx, user: discord.User, quantity: int, price: float, product: str, *, text: str):
        """Send a delivery embed and track user purchase."""
        if product in self.stock and self.stock[product]['quantity'] >= quantity:
            self.stock[product]['quantity'] -= quantity
            if self.stock[product]['quantity'] == 0:
                del self.stock[product]

            # Generate UUID
            delivery_id = str(uuid.uuid4())[:4]

            # Record user purchase data
            now = datetime.utcnow()
            if user.id not in self.user_data:
                self.user_data[user.id] = []
            self.user_data[user.id].append({
                'product': product,
                'quantity': quantity,
                'price': price,
                'time': now,
                'delivery_id': delivery_id
            })

            # Update database
            self.cursor.execute("INSERT INTO user_data (user_id, product, quantity, price, time, delivery_id) VALUES (?, ?, ?, ?, ?, ?)", 
                                (user.id, product, quantity, price, now.isoformat(), delivery_id))
            self.conn.commit()

            # Send delivery embed
            embed = discord.Embed(title="Product Delivery", description="Product has been delivered.", color=discord.Color.purple())
            embed.add_field(name="Product", value=product)
            embed.add_field(name="Quantity", value=quantity)
            embed.add_field(name="Price", value=price)
            embed.add_field(name="Delivery ID", value=delivery_id)
            embed.set_footer(text="Vouch for product | No vouch, no warranty")
            await ctx.send(embed=embed)
            await self.log(f"Product delivered: {product}, Quantity: {quantity}, Price: {price}, Delivery ID: {delivery_id}")

            # Send DM to user
            dm_embed = discord.Embed(title="Delivery Confirmation", description=f"You have received {quantity} of {product}.", color=discord.Color.green())
            dm_embed.add_field(name="Product", value=product)
            dm_embed.add_field(name="Quantity", value=quantity)
            dm_embed.add_field(name="Price", value=price)
            dm_embed.add_field(name="Text", value=text)
            dm_embed.set_thumbnail(url=self.bot.user.avatar_url)  # Bot's avatar in the upper left corner
            dm_embed.set_footer(text="Vouch for product | No vouch, no warranty")
            await user.send(embed=dm_embed)
        else:
            embed = discord.Embed(title="Error", description="Not enough stock or product not found.", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.command(name='replace')
    async def replace_product(self, ctx, old_product: str, new_product: str, quantity: int):
        """Replace one product with another."""
        if old_product in self.stock and self.stock[old_product]['quantity'] >= quantity:
            self.stock[old_product]['quantity'] -= quantity
            if self.stock[old_product]['quantity'] == 0:
                del self.stock[old_product]

            if new_product in self.stock:
                self.stock[new_product]['quantity'] += quantity
            else:
                self.stock[new_product] = {'quantity': quantity, 'price': self.stock[old_product]['price']}

            self.cursor.execute("INSERT OR REPLACE INTO stock (product, quantity, price) VALUES (?, ?, ?)", (new_product, self.stock[new_product]['quantity'], self.stock[new_product]['price']))
            self.conn.commit()

            embed = discord.Embed(title="Product Replaced", description="Product has been replaced.", color=discord.Color.orange())
            embed.add_field(name="Old Product", value=old_product)
            embed.add_field(name="New Product", value=new_product)
            embed.add_field(name="Quantity", value=quantity)
            await ctx.send(embed=embed)
            await self.log(f"Product replaced: {old_product} with {new_product}, Quantity: {quantity}")
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
                await self.log(f"Scheduled message sent to {user} at {scheduled_time}.")
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
                embed.add_field(name=data['time'].strftime("%Y-%m-%d %H:%M:%S"), value=f"Product: {data['product']}\nQuantity: {data['quantity']}\nPrice: {data['price']}\nDelivery ID: {data['delivery_id']}", inline=False)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="No Data", description=f"No purchase data found for {user}.", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.command(name='setrole')
    @commands.has_permissions(administrator=True)
    async def set_role(self, ctx, role: discord.Role):
        """Set the role that can use product commands."""
        self.allowed_role = role.id
        await ctx.send(f"Role {role.name} can now use product commands.")

    @commands.Cog.listener()
    async def on_command(self, ctx):
        """Check role permission for commands."""
        if self.allowed_role and ctx.command.name != 'stock':
            if not any(role.id == self.allowed_role for role in ctx.author.roles):
                await ctx.send("You do not have permission to use this command.")
                raise commands.CommandNotFound

async def setup(bot):
    await bot.add_cog(ProductCog(bot))
