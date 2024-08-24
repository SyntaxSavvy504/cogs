import discord
from discord.ext import commands
from redbot.core import Config
from datetime import datetime

class ImageLogger(commands.Cog):
    """Logs deleted images in a specified channel."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=9876543210)
        default_guild = {
            "image_log_channel_id": None
        }
        self.config.register_guild(**default_guild)

    async def log_image_deletion(self, message):
        """Logs deleted images in the specified log channel."""
        image_log_channel_id = await self.config.guild(message.guild).image_log_channel_id()
        if image_log_channel_id:
            image_log_channel = self.bot.get_channel(image_log_channel_id)
            if image_log_channel and message.attachments:
                for attachment in message.attachments:
                    if attachment.url.lower().endswith(('png', 'jpg', 'jpeg', 'gif', 'webp')):
                        embed = discord.Embed(
                            title="Deleted Image",
                            description=(
                                f"**User:** {message.author.mention} ({message.author})\n"
                                f"**Channel:** {message.channel.mention} (ID: {message.channel.id})\n"
                                f"**Message ID:** {message.id}\n"
                                f"**Date & Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            ),
                            color=discord.Color.purple(),  # Set embed color to purple
                            timestamp=datetime.now()
                        )
                        embed.set_footer(text=f"User ID: {message.author.id}")
                        embed.set_image(url=attachment.url)

                        # Assuming the image might have some tags or additional information
                        embed.add_field(
                            name="Attachment Info",
                            value=(
                                f"**Filename:** {attachment.filename}\n"
                                f"**Size:** {attachment.size / 1000:.2f} KB\n"
                                f"**URL:** [Click here]({attachment.url})"
                            ),
                            inline=False
                        )

                        await image_log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Triggered when a message is deleted."""
        if message.guild and not message.author.bot:
            await self.log_image_deletion(message)

    @commands.command()
    async def setimagelogchannel(self, ctx, channel: discord.TextChannel):
        """Sets the channel where deleted images will be logged."""
        await self.config.guild(ctx.guild).image_log_channel_id.set(channel.id)
        embed = discord.Embed(
            title="Image Log Channel Set",
            description=f"Image log channel has been set to {channel.mention}.",
            color=discord.Color.purple()  # Set embed color to purple
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def imageloginfo(self, ctx):
        """Displays the current image log channel."""
        image_log_channel_id = await self.config.guild(ctx.guild).image_log_channel_id()
        if image_log_channel_id:
            channel = self.bot.get_channel(image_log_channel_id)
            embed = discord.Embed(
                title="Current Image Log Channel",
                description=f"The current image log channel is {channel.mention}.",
                color=discord.Color.purple()  # Set embed color to purple
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="No Image Log Channel Set",
                description="The image log channel has not been set. Use `setimagelogchannel` to set one.",
                color=discord.Color.purple()  # Set embed color to purple
            )
            await ctx.send(embed=embed)
