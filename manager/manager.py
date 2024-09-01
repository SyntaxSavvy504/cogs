import discord
from redbot.core import commands, app_commands, Config
import uuid
import json
import os
from datetime import datetime
from pytz import timezone
import asyncio

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

        # Create settings.json in the specified directory if it doesn't exist
        settings_path = "/home/container/.local/share/Red-DiscordBot/data/pterodactyl/cogs/Manager/settings.json"
        if not os.path.exists(settings_path):
            os.makedirs(os.path.dirname(settings_path), exist_ok=True)
            with open(settings_path, "w") as f:
                json.dump(default_global, f)

    def get_ist_time(self):
        """Return current time in IST."""
        ist = timezone('Asia/Kolkata')
        return datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

    async def is_allowed(self, interaction: discord.Interaction) -> bool:
        roles = await self.config.restricted_roles()
        if not roles:
            return True
        return any(role.id in roles for role in interaction.user.roles)

    async def has_grant_permissions(self, interaction: discord.Interaction) -> bool:
        return any(role.id in await self.config.grant_permissions() for role in interaction.user.roles)

    def generate_uuid(self):
        return str(uuid.uuid4())[:4].upper()

    async def check_is_allowed(self, interaction: discord.Interaction) -> bool:
        return await self.is_allowed(interaction)

    async def check_has_grant_permissions(self, interaction: discord.Interaction) -> bool:
        return await self.has_grant_permissions(interaction)

    @app_commands.command(name="deliver")
    @app_commands.describe(member="The member to deliver the product to", product="The product being delivered", quantity="The quantity of the product", price="The price per product", custom_text="Custom message for the product")
    @app_commands.check(check_is_allowed)
    async def deliver(self, interaction: discord.Interaction, member: discord.Member, product: str, quantity: int, price: float, *, custom_text: str):
        """Deliver a product to a member with a custom message and vouch text."""
        guild_stock = await self.config.guild(interaction.guild).stock()

        if product in guild_stock and guild_stock[product]['quantity'] >= quantity:
            # Prompt for vouch text
            def check(msg):
                return msg.author == interaction.user and msg.channel == interaction.channel

            await interaction.response.send_message("Please enter the vouch text:")
            try:
                vouch_msg = await self.bot.wait_for('message', timeout=60.0, check=check)
                vouch_text = vouch_msg.content
            except asyncio.TimeoutError:
                await interaction.response.send_message("You took too long to respond. Delivery cancelled.")
                return

            # Prepare the embed
            uuid_code = self.generate_uuid()
            purchase_date = self.get_ist_time()

            amount_inr = price * quantity
            usd_exchange_rate = 83.2  # Exchange rate from INR to USD
            amount_usd = amount_inr / usd_exchange_rate

            embed = discord.Embed(
                title="__Frenzy Store__",
                color=discord.Color.purple()
            )
            embed.set_author(name="Frenzy Store", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
            embed.add_field(name="Here is your product", value=f"> {product} {guild_stock[product].get('emoji', '')}", inline=False)
            embed.add_field(name="Amount", value=f"> ₹{amount_inr:.2f} (INR) / ${amount_usd:.2f} (USD)", inline=False)
            embed.add_field(name="Purchase Date", value=f"> {purchase_date}", inline=False)
            embed.add_field(name="\u200b", value="**- follow our [TOS](https://discord.com/channels/911622571856891934/911629489325355049) & be a smart buyer!\n- [CLICK HERE](https://discord.com/channels/911622571856891934/1134197532868739195) to leave your __feedback__**", inline=False)
            embed.add_field(name="Product info and credentials", value=f"||```{custom_text}```||", inline=False)
            embed.add_field(name="__Vouch Format__", value=f"```{vouch_text}```", inline=False)
            embed.set_footer(text=f"__Thanks for order. No vouch, no warranty__")
            embed.set_image(url="https://media.discordapp.net/attachments/1271370383735394357/1271370426655703142/931f5b68a813ce9d437ec11b04eec649.jpg")

            # Try to send the embed to the user's DM
            dm_channel = member.dm_channel or await member.create_dm()
            try:
                await dm_channel.send(embed=embed)
                await interaction.response.send_message(f"Product `{product}` delivered to {member.mention} via DM at {self.get_ist_time()}")

                # Deduct the quantity from server-specific stock
                guild_stock[product]['quantity'] -= quantity
                if guild_stock[product]['quantity'] <= 0:
                    del guild_stock[product]
                await self.config.guild(interaction.guild).stock.set(guild_stock)

                # Log the delivery
                await self.log_event(interaction, f"Delivered {quantity}x {product} to {member.mention} at ₹{amount_inr:.2f} (INR) / ${amount_usd:.2f} (USD)")

                # Record the purchase in history
                purchase_history = await self.config.guild(interaction.guild).purchase_history()
                purchase_record = {
                    "product": product,
                    "quantity": quantity,
                    "price": price,
                    "custom_text": custom_text,
                    "timestamp": purchase_date,
                    "sold_by": interaction.user.name
                }
                if str(member.id) not in purchase_history:
                    purchase_history[str(member.id)] = []
                purchase_history[str(member.id)].append(purchase_record)
                await self.config.guild(interaction.guild).purchase_history.set(purchase_history)

            except discord.Forbidden as e:
                await interaction.response.send_message(f"Failed to deliver the product `{product}` to {member.mention}. Reason: {str(e)}")
        else:
            await interaction.response.send_message(f"Insufficient stock for `{product}`.")

    @app_commands.command(name="stock")
    async def stock(self, interaction: discord.Interaction):
        """Display available stock."""
        guild_stock = await self.config.guild(interaction.guild).stock()
        if not guild_stock:
            await interaction.response.send_message("No stock available.")
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
                name=f"{idx}. {product} {info.get('emoji', '')}",
                value=f"> **Quantity:** {info['quantity']}\n> **Price:** ₹{amount_inr:.2f} (INR) / ${amount_usd:.2f} (USD)",
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="addproduct")
    @app_commands.describe(product="The product to add", quantity="The quantity of the product", price="The price of the product", emoji="The emoji representing the product")
    @app_commands.check(check_is_allowed)
    async def addproduct(self, interaction: discord.Interaction, product: str, quantity: int, price: float, emoji: str):
        """Add a product to the stock."""
        guild_stock = await self.config.guild(interaction.guild).stock()
        if product in guild_stock:
            guild_stock[product]['quantity'] += quantity
            guild_stock[product]['price'] = price
            guild_stock[product]['emoji'] = emoji
        else:
            guild_stock[product] = {"quantity": quantity, "price": price, "emoji": emoji}
        await self.config.guild(interaction.guild).stock.set(guild_stock)
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
        await interaction.response.send_message(embed=embed)

        # Log the addition
        await self.log_event(interaction, f"Added {quantity}x {product} to the stock at ₹{price:.2f} (INR) / ${price / 83.2:.2f} (USD)")

    @app_commands.command(name="removeproduct")
    @app_commands.describe(product="The product to remove")
    @app_commands.check(check_is_allowed)
    async def removeproduct(self, interaction: discord.Interaction, product: str):
        """Remove a product from the stock."""
        guild_stock = await self.config.guild(interaction.guild).stock()
        if product not in guild_stock:
            await interaction.response.send_message(f"{product} not found in stock.")
            return

        del guild_stock[product]
        await self.config.guild(interaction.guild).stock.set(guild_stock)

        embed = discord.Embed(
            title="Product Removed",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Product",
            value=f"> {product}",
            inline=False
        )
        await interaction.response.send_message(embed=embed)

        # Log the removal
        await self.log_event(interaction, f"Removed {product} from the stock")

    @app_commands.command(name="viewhistory")
    @app_commands.describe(member="The member whose purchase history you want to view")
    async def viewhistory(self, interaction: discord.Interaction, member: discord.Member = None):
        """View purchase history for a user."""
        if member is None:
            member = interaction.user

        purchase_history = await self.config.guild(interaction.guild).purchase_history()
        history = purchase_history.get(str(member.id), [])

        if not history:
            await interaction.response.send_message("No purchase history found for this user.")
            return

        embed = discord.Embed(
            title=f"Purchase History for {member.name}",
            color=discord.Color.blue()
        )
        for record in history:
            embed.add_field(
                name=f"{record['product']} (x{record['quantity']})",
                value=f"> **Price:** ₹{record['price']:.2f} (INR)\n> **Purchased on:** {record['timestamp']}\n> **Sold by:** {record['sold_by']}\n> **Custom Text:** {record['custom_text']}",
                inline=False
            )
        await interaction.response.send_message(embed=embed)

    async def log_event(self, interaction: discord.Interaction, message: str):
        """Log the event to the log channel."""
        log_channel_id = await self.config.log_channel_id()
        if not log_channel_id:
            return

        log_channel = self.bot.get_channel(log_channel_id)
        if log_channel:
            embed = discord.Embed(
                title="Event Log",
                description=message,
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text=f"Logged by {interaction.user.name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
            await log_channel.send(embed=embed)

    @app_commands.command(name="setlogchannel")
    @app_commands.describe(channel="The channel to set for logging events")
    async def setlogchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set the channel for logging events."""
        await self.config.log_channel_id.set(channel.id)
        await interaction.response.send_message(f"Log channel set to {channel.mention}")

    @app_commands.command(name="restrictrole")
    @app_commands.describe(role="The role to restrict bot usage")
    async def restrictrole(self, interaction: discord.Interaction, role: discord.Role):
        """Restrict bot usage to a specific role."""
        restricted_roles = await self.config.restricted_roles()
        if role.id not in restricted_roles:
            restricted_roles.append(role.id)
            await self.config.restricted_roles.set(restricted_roles)
            await interaction.response.send_message(f"Role {role.name} has been added to the restriction list.")
        else:
            await interaction.response.send_message(f"Role {role.name} is already restricted.")

    @app_commands.command(name="grantpermissions")
    @app_commands.describe(role="The role to grant special permissions")
    async def grantpermissions(self, interaction: discord.Interaction, role: discord.Role):
        """Grant permissions to a specific role to use certain commands."""
        grant_permissions = await self.config.grant_permissions()
        if role.id not in grant_permissions:
            grant_permissions.append(role.id)
            await self.config.grant_permissions.set(grant_permissions)
            await interaction.response.send_message(f"Role {role.name} has been granted special permissions.")
        else:
            await interaction.response.send_message(f"Role {role.name} already has special permissions.")

def setup(bot):
    bot.add_cog(Manager(bot))
