from .imagelogger import ImageLogger

async def setup(bot):
    bot.add_cog(ImageLogger(bot))

