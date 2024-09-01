import discord
from redbot.core import commands, Config
from datetime import datetime

class ImageLogger(commands.Cog):
    """Log deleted images and links."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567891)
        default_global = {
            "log_channel_id": None
        }
        self.config.register_global(**default_global)

    async def on_message_delete(self, message):
        """Log deleted images or links."""
        log_channel_id = await self.config.log_channel_id()
        if not log_channel_id:
            return

        log_channel = self.bot.get_channel(log_channel_id)
        if log_channel:
            embed = discord.Embed(color=discord.Color.purple())
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

            if message.attachments:
                for attachment in message.attachments:
                    embed.title = "Image Deleted"
                    embed.description = (f"**Sent by:** {message.author}\n"
                                         f"**Deleted by:** {self.bot.user}\n"
                                         f"**Message Content:** {message.content}\n"
                                         f"**Timestamp:** {timestamp}")
                    embed.set_image(url=attachment.url)
                    embed.set_footer(text=f"Deleted in #{message.channel.name}", 
                                     icon_url=self.bot.user.avatar.url)
                    
                    # Warning for nudity
                    if "nudity" in message.content.lower():  # Simple check for nudity
                        embed.add_field(
                            name="⚠️ Warning",
                            value="This image may contain nudity.",
                            inline=False
                        )

                    await log_channel.send(embed=embed)

            elif message.content:
                if "http" in message.content:  # Check for links
                    embed.title = "Link Deleted"
                    embed.description = (f"**Sent by:** {message.author}\n"
                                         f"**Deleted by:** {self.bot.user}\n"
                                         f"**Message Content:** {message.content}\n"
                                         f"**Timestamp:** {timestamp}")
                    embed.set_footer(text=f"Deleted in #{message.channel.name}", 
                                     icon_url=self.bot.user.avatar.url)

                    # Warning for nudity
                    if "nudity" in message.content.lower():  # Simple check for nudity
                        embed.add_field(
                            name="⚠️ Warning",
                            value="This link may contain nudity.",
                            inline=False
                        )

                    await log_channel.send(embed=embed)

    @commands.command()
    async def setloggerchannel(self, ctx, channel: discord.TextChannel):
        """Set the channel for logging deleted images and links."""
        await self.config.log_channel_id.set(channel.id)
        await ctx.send(f"Log channel set to {channel.mention}")
