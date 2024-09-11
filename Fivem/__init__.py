from .fivem import FiveMPlayerCog

async def setup(bot):
    await bot.add_cog(FiveMPlayerCog(bot))
