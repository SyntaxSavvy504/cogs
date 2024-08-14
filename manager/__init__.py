from .manager import Manager

def setup(bot):
    bot.add_cog(Manager(bot))
