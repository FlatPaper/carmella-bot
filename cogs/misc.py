import discord
from discord.ext import commands
from discord import app_commands


class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Cog Loaded: {self.__class__.__name__}')

    @app_commands.command(name='ping', description='Bot Latency')
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f'Pong! Latency of bot is {round(self.bot.latency * 1000)} ms.')


async def setup(bot):
    await bot.add_cog(Misc(bot))