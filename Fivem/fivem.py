import discord
from redbot.core import commands, app_commands
import requests

class FiveMPlayerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.server_ip = "127.0.0.1"  # Default IP
        self.server_port = 30120      # Default port

    @commands.command(name="setserver")
    async def set_server(self, ctx: commands.Context, ip: str, port: int):
        """Sets the FiveM server IP and port."""
        self.server_ip = ip
        self.server_port = port
        await ctx.send(f"Server IP and port set to {ip}:{port}")

    @app_commands.command()
    async def players(self, interaction: discord.Interaction):
        """Fetch and display the list of players from the FiveM server."""
        url = f"http://{self.server_ip}:{self.server_port}/players"  # Replace with your actual API endpoint
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception for HTTP errors
            data = response.json()
            if 'players' in data:
                players = "\n".join([f"{player['id']}: {player['name']}" for player in data['players']])
                await interaction.response.send_message(f"Current players:\n{players}", ephemeral=True)
            else:
                await interaction.response.send_message("No player data found.", ephemeral=True)
        except requests.RequestException as e:
            await interaction.response.send_message(f"Error fetching player list: {e}", ephemeral=True)

    @app_commands.command()
    @app_commands.describe(player_id="The ID of the player you want to look up")
    async def playerinfo(self, interaction: discord.Interaction, player_id: int):
        """Fetch and display detailed information about a player."""
        url = f"http://{self.server_ip}:{self.server_port}/player/{player_id}"  # Replace with your actual API endpoint
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception for HTTP errors
            data = response.json()
            if 'username' in data:
                player_info = (f"Username: {data['username']}\n"
                               f"Discord ID: {data['discord_id']}\n"
                               f"FiveM ID: {data['fivem_id']}\n"
                               f"Steam Name: {data['steam_name']}")
                await interaction.response.send_message(player_info, ephemeral=True)
            else:
                await interaction.response.send_message("No player data found for this ID.", ephemeral=True)
        except requests.RequestException as e:
            await interaction.response.send_message(f"Error fetching player info: {e}", ephemeral=True)
