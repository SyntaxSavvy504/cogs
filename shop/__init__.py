from .mycog import ProductCog

async def setup(bot):
    await bot.add_cog(ProductCog(bot))
