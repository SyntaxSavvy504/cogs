from .image_logger import ImageLogger

async def setup(bot):
    cog = ImageLogger(bot)
    await bot.add_cog(cog)
