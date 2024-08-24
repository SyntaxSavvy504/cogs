from .imagelogger import ImageLogger

def setup(bot):
    bot.add_cog(ImageLogger(bot))
