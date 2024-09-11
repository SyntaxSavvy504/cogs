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
        url = f"http://{self.server_ip}:{self.server_port}/players.json"
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception for HTTP errors
            data = response.json()
            
            if 'players' in data:
                if data['players']:
                    player_list = "\n".join([f"{player['id']}: {player['name']}" for player in data['players']])
                    player_count = len(data['players'])
                    await interaction.response.send_message(f"Current players ({player_count}):\n{player_list}", ephemeral=True)
                else:
                    await interaction.response.send_message("No players are currently online.", ephemeral=True)
            else:
                await interaction.response.send_message("The data received does not include player information.", ephemeral=True)
        except requests.RequestException as e:
            await interaction.response.send_message(f"Error fetching player list: {e}", ephemeral=True)
        except json.JSONDecodeError:
            await interaction.response.send_message("Error decoding the JSON response from the server.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An unexpected error occurred: {e}", ephemeral=True)

    @app_commands.command()
    async def serverstatus(self, interaction: discord.Interaction):
        """Check and display the server status."""
        url = f"http://{self.server_ip}:{self.server_port}/info.json"  # Adjust if necessary
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception for HTTP errors
            data = response.json()
            status = data.get('status', 'Unknown')
            players_online = data.get('players', 0)
            await interaction.response.send_message(f"Server Status: {status}\nPlayers Online: {players_online}", ephemeral=True)
        except requests.RequestException as e:
            await interaction.response.send_message(f"Error fetching server status: {e}", ephemeral=True)
        except json.JSONDecodeError:
            await interaction.response.send_message("Error decoding the JSON response from the server.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An unexpected error occurred: {e}", ephemeral=True)

    @app_commands.command()
    @app_commands.describe(player_id="The ID of the player you want to look up")
    async def playerinfo(self, interaction: discord.Interaction, player_id: int):
        """Fetch and display detailed information about a player."""
        url = f"http://{self.server_ip}:{self.server_port}/player/{player_id}"
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception for HTTP errors
            data = response.json()
            if 'username' in data:
                player_info = (f"Username: {data['username']}\n"
                               f"Discord ID: {data.get('discord_id', 'N/A')}\n"
                               f"FiveM ID: {data.get('fivem_id', 'N/A')}\n"
                               f"Steam Name: {data.get('steam_name', 'N/A')}")
                await interaction.response.send_message(player_info, ephemeral=True)
            else:
                await interaction.response.send_message("No player data found for this ID.", ephemeral=True)
        except requests.RequestException as e:
            await interaction.response.send_message(f"Error fetching player info: {e}", ephemeral=True)
        except json.JSONDecodeError:
            await interaction.response.send_message("Error decoding the JSON response from the server.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An unexpected error occurred: {e}", ephemeral=True)

    @app_commands.command()
    async def help(self, interaction: discord.Interaction):
        """Show help information for commands."""
        help_message = (
            "**FiveM Player Bot Help**\n\n"
            "`/setserver <ip> <port>` - Set the FiveM server IP and port.\n"
            "`/players` - Display the list of current players on the server.\n"
            "`/serverstatus` - Check and display the server status.\n"
            "`/playerinfo <player_id>` - Fetch and display detailed information about a specific player."
        )
        await interaction.response.send_message(help_message, ephemeral=True)
