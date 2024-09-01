// import discord
// from redbot.core import commands, Config
// import uuid
// import json
// import os
// from datetime import datetime
// from pytz import timezone
// import asyncio

// class Manager(commands.Cog):
//     """Manage product delivery and stock."""

//     def __init__(self, bot):
//         self.bot = bot
//         self.config = Config.get_conf(self, identifier=1234567890)
//         default_global = {
//             "stock": {},
//             "log_channel_id": None,
//             "restricted_roles": [],
//             "grant_permissions": [],
//             "purchase_history": {}
//         }
//         self.config.register_global(**default_global)
//         default_server = {
//             "stock": {},
//             "purchase_history": {}
//         }
//         self.config.register_guild(**default_server)

//         # Create settings.json in the specified directory if it doesn't exist
//         settings_path = "/home/container/.local/share/Red-DiscordBot/data/pterodactyl/cogs/Manager/settings.json"
//         if not os.path.exists(settings_path):
//             os.makedirs(os.path.dirname(settings_path), exist_ok=True)
//             with open(settings_path, "w") as f:
//                 json.dump(default_global, f)

//     def get_ist_time(self):
//         """Return current time in IST."""
//         ist = timezone('Asia/Kolkata')
//         return datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

//     async def is_allowed(ctx):
//         roles = await ctx.cog.config.restricted_roles()
//         if not roles:
//             return True
//         return any(role.id in roles for role in ctx.author.roles)

//     async def has_grant_permissions(ctx):
//         return any(role.id in await ctx.cog.config.grant_permissions() for role in ctx.author.roles)

//     def generate_uuid(self):
//         return str(uuid.uuid4())[:4].upper()

//     @commands.command()
//     async def deliver(self, ctx, member: discord.Member, product: str, quantity: int, price: float, *, custom_text: str):
//         """Deliver a product to a member with a custom message and vouch text."""
//         guild_stock = await self.config.guild(ctx.guild).stock()

//         if product in guild_stock and guild_stock[product]['quantity'] >= quantity:
//             # Prompt for vouch text
//             def check(msg):
//                 return msg.author == ctx.author and msg.channel == ctx.channel

//             await ctx.send("Please enter the vouch text:")
//             try:
//                 vouch_msg = await self.bot.wait_for('message', timeout=60.0, check=check)
//                 vouch_text = vouch_msg.content
//             except asyncio.TimeoutError:
//                 await ctx.send("You took too long to respond. Delivery cancelled.")
//                 return

//             # Prepare the embed
//             uuid_code = self.generate_uuid()
//             purchase_date = self.get_ist_time()

//             amount_inr = price * quantity
//             usd_exchange_rate = 83.2  # Exchange rate from INR to USD
//             amount_usd = amount_inr / usd_exchange_rate

//             embed = discord.Embed(
//                 title="__Frenzy Store__",
//                 color=discord.Color.purple()
//             )
//             embed.set_author(name="Frenzy Store", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
//             embed.add_field(name="Here is your product", value=f"> {product} {guild_stock[product].get('emoji', '')}", inline=False)
//             embed.add_field(name="Amount", value=f"> ₹{amount_inr:.2f} (INR) / ${amount_usd:.2f} (USD)", inline=False)
//             embed.add_field(name="Purchase Date", value=f"> {purchase_date}", inline=False)
//             embed.add_field(name="\u200b", value="**- follow our [TOS](https://discord.com/channels/911622571856891934/911629489325355049) & be a smart buyer!\n- [CLICK HERE](https://discord.com/channels/911622571856891934/1134197532868739195) to leave your __feedback__**", inline=False)
//             embed.add_field(name="Product info and credentials", value=f"||```{custom_text}```||", inline=False)
//             embed.add_field(name="__Vouch Format__", value=f"```{vouch_text}```", inline=False)
//             embed.set_footer(text=f"__Thanks for order. No vouch, no warranty__")
//             embed.set_image(url="https://media.discordapp.net/attachments/1271370383735394357/1271370426655703142/931f5b68a813ce9d437ec11b04eec649.jpg")

//             # Try to send the embed to the user's DM
//             dm_channel = member.dm_channel or await member.create_dm()
//             try:
//                 await dm_channel.send(embed=embed)
//                 await ctx.send(f"Product `{product}` delivered to {member.mention} via DM at {self.get_ist_time()}")

//                 # Deduct the quantity from server-specific stock
//                 guild_stock[product]['quantity'] -= quantity
//                 if guild_stock[product]['quantity'] <= 0:
//                     del guild_stock[product]
//                 await self.config.guild(ctx.guild).stock.set(guild_stock)

//                 # Log the delivery
//                 await self.log_event(ctx, f"Delivered {quantity}x {product} to {member.mention} at ₹{amount_inr:.2f} (INR) / ${amount_usd:.2f} (USD)")

//                 # Record the purchase in history
//                 purchase_history = await self.config.guild(ctx.guild).purchase_history()
//                 purchase_record = {
//                     "product": product,
//                     "quantity": quantity,
//                     "price": price,
//                     "custom_text": custom_text,
//                     "timestamp": purchase_date,
//                     "sold_by": ctx.author.name
//                 }
//                 if str(member.id) not in purchase_history:
//                     purchase_history[str(member.id)] = []
//                 purchase_history[str(member.id)].append(purchase_record)
//                 await self.config.guild(ctx.guild).purchase_history.set(purchase_history)

//             except discord.Forbidden as e:
//                 await ctx.send(f"Failed to deliver the product `{product}` to {member.mention}. Reason: {str(e)}")
//         else:
//             await ctx.send(f"Insufficient stock for `{product}`.")

//     # Other commands like stock, addproduct, removeproduct, etc.

//     @commands.command()
//     async def stock(self, ctx):
//         """Display available stock."""
//         guild_stock = await self.config.guild(ctx.guild).stock()
//         if not guild_stock:
//             await ctx.send("No stock available.")
//             return

//         embed = discord.Embed(
//             title="Available Stock",
//             color=discord.Color.green()
//         )

//         for idx, (product, info) in enumerate(guild_stock.items(), start=1):
//             amount_inr = info['price']
//             usd_exchange_rate = 83.2  # Exchange rate from INR to USD
//             amount_usd = amount_inr / usd_exchange_rate
//             embed.add_field(
//                 name=f"{idx}. {product} {info.get('emoji', '')}",
//                 value=f"> **Quantity:** {info['quantity']}\n> **Price:** ₹{amount_inr:.2f} (INR) / ${amount_usd:.2f} (USD)",
//                 inline=False
//             )

//         await ctx.send(embed=embed)

//     @commands.command()
//     @commands.check(is_allowed)
//     async def addproduct(self, ctx, product: str, quantity: int, price: float, emoji: str):
//         """Add a product to the stock."""
//         guild_stock = await self.config.guild(ctx.guild).stock()
//         if product in guild_stock:
//             guild_stock[product]['quantity'] += quantity
//             guild_stock[product]['price'] = price
//             guild_stock[product]['emoji'] = emoji
//         else:
//             guild_stock[product] = {"quantity": quantity, "price": price, "emoji": emoji}
//         await self.config.guild(ctx.guild).stock.set(guild_stock)
//         embed = discord.Embed(
//             title="Product Added",
//             color=discord.Color.teal()
//         )
//         embed.add_field(
//             name="Product",
//             value=f"> {product} {emoji}",
//             inline=False
//         )
//         embed.add_field(
//             name="Quantity",
//             value=f"> {quantity}",
//             inline=False
//         )
//         embed.add_field(
//             name="Price",
//             value=f"> ₹{price:.2f} (INR) / ${price / 83.2:.2f} (USD)",
//             inline=False
//         )
//         await ctx.send(embed=embed)

//         # Log the addition
//         await self.log_event(ctx, f"Added {quantity}x {product} to the stock at ₹{price:.2f} (INR) / ${price / 83.2:.2f} (USD)")

//     @commands.command()
//     @commands.check(is_allowed)
//     async def removeproduct(self, ctx, product: str):
//         """Remove a product from the stock."""
//         guild_stock = await self.config.guild(ctx.guild).stock()
//         if product not in guild_stock:
//             await ctx.send(f"{product} not found in stock.")
//             return

//         del guild_stock[product]
//         await self.config.guild(ctx.guild).stock.set(guild_stock)

//         embed = discord.Embed(
//             title="Product Removed",
//             color=discord.Color.red()
//         )
//         embed.add_field(
//             name="Product",
//             value=f"> {product}",
//             inline=False
//         )
//         await ctx.send(embed=embed)

//         # Log the removal
//         await self.log_event(ctx, f"Removed {product} from the stock")

//     @commands.command()
//     async def viewhistory(self, ctx, member: discord.Member = None):
//         """View purchase history for a user."""
//         if member is None:
//             member = ctx.author

//         purchase_history = await self.config.guild(ctx.guild).purchase_history()
//         history = purchase_history.get(str(member.id), [])

//         if not history:
//             await ctx.send("No purchase history found for this user.")
//             return

//         embed = discord.Embed(
//             title=f"Purchase History for {member.name}",
//             color=discord.Color.blue()
//         )
//         for record in history:
//             embed.add_field(
//                 name=f"{record['product']} (x{record['quantity']})",
//                 value=f"> **Price:** ₹{record['price']:.2f} (INR)\n> **Purchased on:** {record['timestamp']}\n> **Sold by:** {record['sold_by']}\n> **Custom Text:** {record['custom_text']}",
//                 inline=False
//             )
//         await ctx.send(embed=embed)

//     async def log_event(self, ctx, message):
//         """Log the event to the log channel."""
//         log_channel_id = await self.config.log_channel_id()
//         if not log_channel_id:
//             return

//         log_channel = self.bot.get_channel(log_channel_id)
//         if log_channel:
//             embed = discord.Embed(
//                 title="Event Log",
//                 description=message,
//                 color=discord.Color.orange(),
//                 timestamp=datetime.utcnow()
//             )
//             embed.set_footer(text=f"Logged by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
//             await log_channel.send(embed=embed)

//     @commands.command()
//     async def setlogchannel(self, ctx, channel: discord.TextChannel):
//         """Set the channel for logging events."""
//         await self.config.log_channel_id.set(channel.id)
//         await ctx.send(f"Log channel set to {channel.mention}")

//     @commands.command()
//     async def restrictrole(self, ctx, role: discord.Role):
//         """Restrict bot usage to a specific role."""
//         restricted_roles = await self.config.restricted_roles()
//         if role.id not in restricted_roles:
//             restricted_roles.append(role.id)
//             await self.config.restricted_roles.set(restricted_roles)
//             await ctx.send(f"Role {role.name} has been added to the restriction list.")
//         else:
//             await ctx.send(f"Role {role.name} is already restricted.")

//     @commands.command()
//     async def grantpermissions(self, ctx, role: discord.Role):
//         """Grant permissions to a specific role to use certain commands."""
//         grant_permissions = await self.config.grant_permissions()
//         if role.id not in grant_permissions:
//             grant_permissions.append(role.id)
//             await self.config.grant_permissions.set(grant_permissions)
//             await ctx.send(f"Role {role.name} has been granted special permissions.")
//         else:
//             await ctx.send(f"Role {role.name} already has special permissions.")

// def setup(bot):
//     bot.add_cog(Manager(bot))


// not updated version