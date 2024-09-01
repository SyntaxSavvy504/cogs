from .image_logger import ImageLogger

async def setup(bot):
    await bot.add_cog(ImageLogger(bot))
