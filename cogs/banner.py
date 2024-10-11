import random
import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
from datetime import datetime
import asyncio
import config


class Banner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.filtered_image_list = []
        self.banner_task = None

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Cog Loaded: {self.__class__.__name__}')

    def load_images(self):
        self.filtered_image_list = [
            os.path.join(config.FILTERED_FANART_SAVE_DIR, f)
            for f in os.listdir(config.FILTERED_FANART_SAVE_DIR)
            if os.path.isfile(os.path.join(config.FILTERED_FANART_SAVE_DIR, f))
        ]
        random.shuffle(self.filtered_image_list)

    async def change_banner(self, discord_logging):
        guild = self.bot.get_guild(config.SERVER_ID)
        log_channel = self.bot.get_channel(config.LOG_CHANNEL_ID)
        current_time_unix = int(datetime.now().timestamp())
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if not self.filtered_image_list:
            print(f'Image list is empty at {current_time}.')
            discord_logging and await log_channel.send(f'Image list is empty at <t:{current_time_unix}:F>.')
            self.load_images()
            print(f'Refilled image list at {current_time} with {len(self.filtered_image_list)} images.')
            discord_logging and await log_channel.send(
                f'Refilled image list at <t:{current_time_unix}:F> with {len(self.filtered_image_list)} '
                f'images.')

        image_path = self.filtered_image_list.pop()

        with open(image_path, 'rb') as img:
            banner = img.read()

        if guild:
            try:
                await guild.edit(banner=banner)
                print(f'Changed banner to `{image_path}` at time {current_time}.')
                discord_logging and await log_channel.send(
                    f'Changed banner to `{image_path}` at time <t:{current_time_unix}:F>.')
            except discord.Forbidden as e:
                print(
                    f'Failed to change banner `{image_path}` at time {current_time} due to insufficient permissions: {e}')
                discord_logging and await log_channel.send(
                    f'Failed to change banner `{image_path}` at time <t:{current_time_unix}:F> due to insufficient '
                    f'permissions: {e}')
            except discord.HTTPException as e:
                print(f'Failed to change banner `{image_path}` at time {current_time} due to an HTTPException: {e}')
                discord_logging and await log_channel.send(
                    f'Failed to change banner `{image_path}` at time <t:{current_time_unix}:F> due to an '
                    f'HTTPException: {e}')
            except Exception as e:
                print(f'Failed to change banner `{image_path}` at time {current_time}: {e}')
                discord_logging and await log_channel.send(
                    f'Failed to change banner `{image_path}` at time <t:{current_time_unix}:F>: {e}')

    async def change_banner_task(self, interval, discord_logging):
        while True:
            await self.change_banner(discord_logging)
            await asyncio.sleep(interval * 60)

    @app_commands.command(name='change_banner_periodically',
                          description="Change server banner periodically from fan art.")
    async def change_banner_periodically(self, interaction: discord.Interaction, minutes: int = 5,
                                         logging: bool = False):
        if interaction.user.id != config.FLATPAPER_DISCORD_ID:
            await interaction.response.send_message(
                f'Unauthorized usage of change_banner_periodically by {interaction.user.display_name}.')
            return

        if self.banner_task and not self.banner_task.done():
            self.banner_task.cancel()
            await interaction.response.send_message("Stopped the previous banner change task.")

        self.banner_task = self.bot.loop.create_task(self.change_banner_task(minutes, logging))
        await interaction.response.send_message(f"Started changing banner every {minutes} minutes.")


async def setup(bot):
    await bot.add_cog(Banner(bot))
