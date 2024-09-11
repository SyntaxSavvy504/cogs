import discord
from redbot.core import commands, app_commands
import subprocess
import json

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
        """Fetch and display the list of players from the FiveM server using curl."""
        url = f"http://{self.server_ip}:{self.server_port}/players.json"
        data = self.fetch_data_with_curl(url)
        if data:
            if 'players' in data:
                player_list = "\n".join([f"{player['id']}: {player['name']}" for player in data['players']])
                player_count = len(data['players'])
                await interaction.response.send_message(f"Current players ({player_count}):\n{player_list}", ephemeral=True)
            else:
                await interaction.response.send_message("No player data found.", ephemeral=True)
        else:
            await interaction.response.send_message("Error fetching player list.", ephemeral=True)

    def fetch_data_with_curl(self, url):
        """Fetch data from a URL using curl and return the response as a JSON object."""
        try:
            result = subprocess.run(['curl', '-s', url], capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            return data
        except subprocess.CalledProcessError as e:
            print(f"Error executing curl command: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON response: {e}")
            return None

