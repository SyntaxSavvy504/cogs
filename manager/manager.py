import discord
from discord import app_commands
from redbot.core import commands
from pymongo import MongoClient
import uuid
from datetime import datetime
from pytz import timezone
import asyncio
import time

class FrenzyStore(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_client = MongoClient('mongodb://localhost:27017/')
        self.db = self.db_client['frenzy_store']
        self.stock_collection = self.db['stock']
    
    # Helper functions
    def measure_latency(self, func, *args, **kwargs):
        """Measures the latency of a MongoDB operation."""
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        latency = end_time - start_time
        return result, latency

    def get_ist_time(self):
        """Get current time in IST."""
        ist = timezone('Asia/Kolkata')
        return datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

    def generate_uuid(self):
        """Generate a unique UUID for transactions."""
        return str(uuid.uuid4())

    async def log_event(self, interaction, log_message):
        """Log events in the guild's system channel."""
        if interaction.guild.system_channel:
            await interaction.guild.system_channel.send(log_message)

    # Commands
    @app_commands.command(name="deliver", description="Deliver a product to a member with a custom message and vouch text.")
    async def deliver(self, interaction: discord.Interaction, member: discord.Member, product: str, quantity: int, price: float, custom_text: str):
        """Deliver a product to a member with a custom message and vouch text."""
        guild_stock, stock_latency = self.measure_latency(self.stock_collection.find_one, {'guild_id': str(interaction.guild.id)})

        if guild_stock and product in guild_stock.get('products', {}):
            product_info = guild_stock['products'][product]
            if product_info['quantity'] >= quantity:
                def check(msg):
                    return msg.author == interaction.user and msg.channel == interaction.channel

                await interaction.response.send_message("Please enter the vouch text:", ephemeral=True)
                try:
                    vouch_msg = await self.bot.wait_for('message', timeout=60.0, check=check)
                    vouch_text = vouch_msg.content
                except asyncio.TimeoutError:
                    await interaction.followup.send("You took too long to respond. Delivery cancelled.", ephemeral=True)
                    return

                # Prepare the embed
                uuid_code = self.generate_uuid()
                purchase_date = self.get_ist_time()

                amount_inr = price * quantity
                usd_exchange_rate = 83.2
                amount_usd = amount_inr / usd_exchange_rate

                embed = discord.Embed(
                    title="__Frenzy Store__",
                    color=discord.Color.purple()
                )
                embed.set_author(name="Frenzy Store", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
                embed.add_field(name="Here is your product", value=f"> {product} {product_info.get('emoji', '')}", inline=False)
                embed.add_field(name="Amount", value=f"> ₹{amount_inr:.2f} (INR) / ${amount_usd:.2f} (USD)", inline=False)
                embed.add_field(name="Purchase Date", value=f"> {purchase_date}", inline=False)
                embed.add_field(name="\u200b", value="**- Follow our [TOS](https://discord.com/channels/911622571856891934/911629489325355049) & be a smart buyer!\n- [CLICK HERE](https://discord.com/channels/911622571856891934/1134197532868739195) to leave your __feedback__**", inline=False)
                embed.add_field(name="Product info and credentials", value=f"||```{custom_text}```||", inline=False)
                embed.add_field(name="__Vouch Format__", value=f"```{vouch_text}```", inline=False)
                embed.set_footer(text=f"Thanks for order. No vouch, no warranty")
                embed.set_image(url="https://media.discordapp.net/attachments/1271370383735394357/1271370426655703142/931f5b68a813ce9d437ec11b04eec649.jpg")
                embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)

                # Try to send the embed to the user's DM
                dm_channel = member.dm_channel or await member.create_dm()
                try:
                    await dm_channel.send(embed=embed)
                    await interaction.followup.send(f"Product `{product}` delivered to {member.mention} via DM at {self.get_ist_time()}", ephemeral=True)

                    product_info['quantity'] -= quantity
                    if product_info['quantity'] <= 0:
                        del guild_stock['products'][product]
                    update_result, update_latency = self.measure_latency(self.stock_collection.update_one,
                        {'guild_id': str(interaction.guild.id)},
                        {'$set': {'products': guild_stock.get('products', {})}}
                    )

                    # Log the delivery
                    await self.log_event(interaction, f"Delivered {quantity}x {product} to {member.mention} at ₹{amount_inr:.2f} (INR) / ${amount_usd:.2f} (USD).\nStock update latency: {update_latency:.4f}s\nMongoDB find latency: {stock_latency:.4f}s")

                except discord.Forbidden as e:
                    await interaction.followup.send(f"Failed to deliver the product `{product}` to {member.mention}. Reason: {str(e)}", ephemeral=True)
            else:
                await interaction.followup.send(f"Insufficient stock for `{product}`.", ephemeral=True)
        else:
            await interaction.followup.send(f"No stock available for `{product}`.", ephemeral=True)

    @app_commands.command(name="stock", description="Check the current stock in the store.")
    async def stock(self, interaction: discord.Interaction):
        """Check the current stock."""
        guild_stock, stock_latency = self.measure_latency(self.stock_collection.find_one, {'guild_id': str(interaction.guild.id)})

        if guild_stock and 'products' in guild_stock and guild_stock['products']:
            stock_list = [f"**{p}:** {d['quantity']} {d.get('emoji', '')}" for p, d in guild_stock['products'].items()]
            stock_message = "\n".join(stock_list)
            await interaction.response.send_message(f"**Current Stock:**\n{stock_message}\n\nLatency: {stock_latency:.4f}s", ephemeral=True)
        else:
            await interaction.response.send_message("No stock available.", ephemeral=True)

    @app_commands.command(name="addproduct", description="Add a product to the store.")
    async def add_product(self, interaction: discord.Interaction, product: str, quantity: int, emoji: str = None):
        """Add a product to the store."""
        guild_stock, stock_latency = self.measure_latency(self.stock_collection.find_one, {'guild_id': str(interaction.guild.id)})

        if not guild_stock:
            guild_stock = {'guild_id': str(interaction.guild.id), 'products': {}}
        
        guild_stock['products'][product] = {'quantity': quantity, 'emoji': emoji}

        update_result, update_latency = self.measure_latency(self.stock_collection.update_one,
            {'guild_id': str(interaction.guild.id)},
            {'$set': {'products': guild_stock['products']}},
            upsert=True
        )

        await interaction.response.send_message(f"Added {quantity}x {product} to the store with emoji {emoji}. Latency: {update_latency:.4f}s", ephemeral=True)

    @app_commands.command(name="removeproduct", description="Remove a product from the store.")
    async def remove_product(self, interaction: discord.Interaction, product: str):
        """Remove a product from the store."""
        guild_stock, stock_latency = self.measure_latency(self.stock_collection.find_one, {'guild_id': str(interaction.guild.id)})

        if guild_stock and product in guild_stock.get('products', {}):
            del guild_stock['products'][product]

            update_result, update_latency = self.measure_latency(self.stock_collection.update_one,
                {'guild_id': str(interaction.guild.id)},
                {'$set': {'products': guild_stock['products']}}
            )

            await interaction.response.send_message(f"Removed `{product}` from the store. Latency: {update_latency:.4f}s", ephemeral=True)
        else:
            await interaction.response.send_message(f"No stock available for `{product}`.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(FrenzyStore(bot))
