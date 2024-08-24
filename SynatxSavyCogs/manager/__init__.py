from .manager import Manager

async def setup(bot):
    await bot.add_cog(Manager(bot))
