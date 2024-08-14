import discord
from redbot.core import commands, Config
import uuid
import json
import os
from datetime import datetime
from pytz import timezone

class Manager(commands.Cog):
    """Manage product delivery and stock."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        default_global = {
            "stock": {},
            "log_channel_id": None,
            "restricted_roles": [],
            "grant_permissions": [],
            "purchase_history": {}
        }
        self.config.register_global(**default_global)
        default_server = {
            "stock": {},
            "purchase_history": {}
        }
        self.config.register_guild(**default_server)

        # Create settings.json if it doesn't exist
        if not os.path.exists("settings.json"):
            with open("settings.json", "w") as f:
                json.dump(default_global, f)

    def get_ist_time(self):
        """Return current time in IST."""
        ist = timezone('Asia/Kolkata')
        return datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

    async def is_allowed(ctx):
        roles = await ctx.cog.config.restricted_roles()
        if not roles:
            return True
        return any(role.id in roles for role in ctx.author.roles)

    async def has_grant_permissions(ctx):
        return any(role.id in await ctx.cog.config.grant_permissions() for role in ctx.author.roles)

    def generate_uuid(self):
        return str(uuid.uuid4())[:4].upper()

    @commands.command()
    async def deliver(self, ctx, member: discord.Member, product: str, quantity: int, price: float, *, custom_text: str):
        """Deliver a product to a member with a custom message."""
        stock = await self.config.stock()
        guild_stock = await self.config.guild(ctx.guild).stock()

        # Check server-specific stock first
        if product in guild_stock and guild_stock[product]['quantity'] >= quantity:
            # Deduct the quantity from server-specific stock
            guild_stock[product]['quantity'] -= quantity
            if guild_stock[product]['quantity'] <= 0:
                del guild_stock[product]
            await self.config.guild(ctx.guild).stock.set(guild_stock)

            # Calculate amount in INR and USD
            amount_inr = price * quantity
            usd_exchange_rate = 83.2  # Exchange rate from INR to USD
            amount_usd = amount_inr / usd_exchange_rate

            # Prepare the embed
            uuid_code = self.generate_uuid()
            purchase_date = self.get_ist_time()

            embed = discord.Embed(
                title="__Frenzy Store__",
                color=discord.Color.purple()
            )
            embed.set_author(name="Frenzy Store", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
            embed.add_field(name="Here is your product", value=f"> {product}", inline=False)
            embed.add_field(name="Amount", value=f"> ₹{amount_inr:.2f} (INR) / ${amount_usd:.2f} (USD)", inline=False)
            embed.add_field(name="Purchase Date", value=f"> {purchase_date}", inline=False)
            embed.add_field(name="\u200b", value="**- follow our [TOS](https://discord.com/channels/911622571856891934/911629489325355049) & be a smart buyer!\n- [CLICK HERE](https://discord.com/channels/911622571856891934/1134197532868739195)  to leave your __feedback__**", inline=False)
            embed.add_field(name="Product info and credentials", value=f"||```{custom_text}```||", inline=False)
            embed.set_footer(text=f"Vouch format: +rep {ctx.guild.owner} {quantity}x {product} | No vouch, no warranty")
            embed.set_image(url="https://media.discordapp.net/attachments/1271370383735394357/1271370426655703142/931f5b68a813ce9d437ec11b04eec649.jpg?ex=66bdaefa&is=66bc5d7a&hm=175b7664862e5f77e5736b51eb96857ee882a3ead7638bdf87cc4ea22b7181aa&=&format=webp&width=1114&height=670")

            try:
                await member.send(embed=embed)
                await ctx.send(f"Product delivered to {member.mention} via DM.")
            except discord.Forbidden:
                await ctx.send(f"Failed to deliver the product to {member.mention}. They may have DMs disabled.")
            
            # Log the delivery
            await self.log_event(ctx, f"Delivered {quantity}x {product} to {member.mention} at ₹{amount_inr:.2f} (INR) / ${amount_usd:.2f} (USD)")

            # Record the purchase in history
            purchase_history = await self.config.guild(ctx.guild).purchase_history()
            purchase_record = {
                "product": product,
                "quantity": quantity,
                "price": price,
                "custom_text": custom_text,
                "timestamp": purchase_date,
                "sold_by": ctx.author.name
            }
            if str(member.id) not in purchase_history:
                purchase_history[str(member.id)] = []
            purchase_history[str(member.id)].append(purchase_record)
            await self.config.guild(ctx.guild).purchase_history.set(purchase_history)

        else:
            await ctx.send(f"Insufficient stock for {product}.")

    @commands.command()
    async def stock(self, ctx):
        """Display available stock."""
        guild_stock = await self.config.guild(ctx.guild).stock()
        if not guild_stock:
            await ctx.send("No stock available.")
            return

        embed = discord.Embed(
            title="Available Stock",
            color=discord.Color.green()
        )

        for idx, (product, info) in enumerate(guild_stock.items(), start=1):
            amount_inr = info['price']
            usd_exchange_rate = 83.2  # Exchange rate from INR to USD
            amount_usd = amount_inr / usd_exchange_rate
            embed.add_field(
                name=f"{idx}. {product}",
                value=f"> **Quantity:** {info['quantity']}\n> **Price:** ₹{amount_inr:.2f} (INR) / ${amount_usd:.2f} (USD)",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command()
    @commands.check(is_allowed)
    async def addproduct(self, ctx, product: str, quantity: int, price: float, emoji: str):
        """Add a product to the stock."""
        guild_stock = await self.config.guild(ctx.guild).stock()
        if product in guild_stock:
            guild_stock[product]['quantity'] += quantity
            guild_stock[product]['price'] = price
            guild_stock[product]['emoji'] = emoji
        else:
            guild_stock[product] = {"quantity": quantity, "price": price, "emoji": emoji}
        await self.config.guild(ctx.guild).stock.set(guild_stock)
        embed = discord.Embed(
            title="Product Added",
            color=discord.Color.teal()
        )
        embed.add_field(
            name="Product",
            value=f"> {product} {emoji}",
            inline=False
        )
        embed.add_field(
            name="Quantity",
            value=f"> {quantity}",
            inline=False
        )
        embed.add_field(
            name="Price",
            value=f"> ₹{price:.2f} (INR) / ${price / 83.2:.2f} (USD)",
            inline=False
        )
        await ctx.send(embed=embed)

        # Log the addition
        await self.log_event(ctx, f"Added {quantity}x {product} to the stock at ₹{price:.2f} (INR) / ${price / 83.2:.2f} (USD)")

    @commands.command()
    @commands.check(is_allowed)
    async def removeproduct(self, ctx, product: str):
        """Remove a product from the stock."""
        guild_stock = await self.config.guild(ctx.guild).stock()
        if product not in guild_stock:
            await ctx.send(f"{product} not found in stock.")
            return

        del guild_stock[product]
        await self.config.guild(ctx.guild).stock.set(guild_stock)

        embed = discord.Embed(
            title="Product Removed",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Product",
            value=f"> {product}",
            inline=False
        )
        await ctx.send(embed=embed)

        # Log the removal
        await self.log_event(ctx, f"Removed {product} from the stock.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setlogchannel(self, ctx, channel: discord.TextChannel):
        """Set the log channel."""
        await self.config.log_channel_id.set(channel.id)
        embed = discord.Embed(
            title="Log Channel Set",
            description=f"The log channel has been set to {channel.mention}.",
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)

    async def log_event(self, ctx, message):
        log_channel_id = await self.config.log_channel_id()
        if not log_channel_id:
            return

        log_channel = self.bot.get_channel(log_channel_id)
        if log_channel:
            embed = discord.Embed(
                title="Activity Log",
                description=message,
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            await log_channel.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def addrestrictedrole(self, ctx, role: discord.Role):
        """Add a role to the restricted roles list."""
        restricted_roles = await self.config.restricted_roles()
        if role.id not in restricted_roles:
            restricted_roles.append(role.id)
            await self.config.restricted_roles.set(restricted_roles)
            await ctx.send(f"Role {role.name} added to restricted roles.")
        else:
            await ctx.send(f"Role {role.name} is already in the restricted roles list.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def removerestrictedrole(self, ctx, role: discord.Role):
        """Remove a role from the restricted roles list."""
        restricted_roles = await self.config.restricted_roles()
        if role.id in restricted_roles:
            restricted_roles.remove(role.id)
            await self.config.restricted_roles.set(restricted_roles)
            await ctx.send(f"Role {role.name} removed from restricted roles.")
        else:
            await ctx.send(f"Role {role.name} is not in the restricted roles list.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def grantpermission(self, ctx, role: discord.Role):
        """Grant permissions to a role."""
        grant_permissions = await self.config.grant_permissions()
        if role.id not in grant_permissions:
            grant_permissions.append(role.id)
            await self.config.grant_permissions.set(grant_permissions)
            await ctx.send(f"Permissions granted to role {role.name}.")
        else:
            await ctx.send(f"Role {role.name} already has permissions.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def revokepermission(self, ctx, role: discord.Role):
        """Revoke permissions from a role."""
        grant_permissions = await self.config.grant_permissions()
        if role.id in grant_permissions:
            grant_permissions.remove(role.id)
            await self.config.grant_permissions.set(grant_permissions)
            await ctx.send(f"Permissions revoked from role {role.name}.")
        else:
            await ctx.send(f"Role {role.name} does not have permissions.")

    @commands.command()
    async def purchasehistory(self, ctx, member: discord.Member = None):
        """Show purchase history for a member or yourself."""
        member = member or ctx.author
        purchase_history = await self.config.guild(ctx.guild).purchase_history()
        history = purchase_history.get(str(member.id), [])

        if not history:
            await ctx.send(f"No purchase history found for {member.mention}.")
            return

        embed = discord.Embed(
            title=f"Purchase History for {member.name}",
            color=discord.Color.purple()
        )

        for record in history:
            embed.add_field(
                name=f"Product: {record['product']}",
                value=f"**Quantity:** {record['quantity']}\n**Price:** ₹{record['price']:.2f} (INR)\n**Custom Text:** ||```{record['custom_text']}```||\n**Timestamp:** {record['timestamp']}\n**Sold by:** {record['sold_by']}",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def viewrestrictedroles(self, ctx):
        """View the list of restricted roles."""
        restricted_roles = await self.config.restricted_roles()
        if not restricted_roles:
            await ctx.send("No roles are currently restricted.")
            return

        restricted_roles_names = [ctx.guild.get_role(role_id).name for role_id in restricted_roles if ctx.guild.get_role(role_id)]
        if not restricted_roles_names:
            await ctx.send("No valid restricted roles found.")
            return

        embed = discord.Embed(
            title="Restricted Roles",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Roles",
            value="\n".join(restricted_roles_names),
            inline=False
        )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def viewgrantedroles(self, ctx):
        """View the list of roles with granted permissions."""
        grant_permissions = await self.config.grant_permissions()
        if not grant_permissions:
            await ctx.send("No roles currently have granted permissions.")
            return

        granted_roles_names = [ctx.guild.get_role(role_id).name for role_id in grant_permissions if ctx.guild.get_role(role_id)]
        if not granted_roles_names:
            await ctx.send("No valid roles with granted permissions found.")
            return

        embed = discord.Embed(
            title="Roles with Granted Permissions",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Roles",
            value="\n".join(granted_roles_names),
            inline=False
        )
        await ctx.send(embed=embed)
