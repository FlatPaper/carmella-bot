import random

import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import os
from datetime import datetime
import asyncio
import config

description = '''Bot personalized for carmellaco. Also a side project for fun.'''

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
bot = commands.Bot(command_prefix=config.COMMAND_PREFIX, intents=intents)

filtered_image_list = []
banner_task = None


def load_images():
    """
    void function to store a list of images (str) and shuffle it randomly
    """
    global filtered_image_list
    filtered_image_list = [os.path.join(config.FILTERED_FANART_SAVE_DIR, f)
                           for f in os.listdir(config.FILTERED_FANART_SAVE_DIR)
                           if os.path.isfile(os.path.join(config.FILTERED_FANART_SAVE_DIR, f))]
    random.shuffle(filtered_image_list)


async def change_banner(discord_logging):
    """
    function to change discord banner from `filtered_image_list`
    runs iteratively through the list and updates banner using discord.py API
    :return:
    """
    global filtered_image_list

    guild = bot.get_guild(config.SERVER_ID)
    log_channel = bot.get_channel(config.LOG_CHANNEL_ID)
    current_time_unix = int(datetime.now().timestamp())  # unix time for discord logging
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # normal format time for console logging

    # load images from folder if global image list is empty
    if not filtered_image_list:
        print(f'Image list is empty at {current_time}.')
        discord_logging and await log_channel.send(f'Image list is empty at <t:{current_time_unix}:F>.')
        load_images()
        print(f'Refilled image list at {current_time} with {len(filtered_image_list)} images.')
        discord_logging and await log_channel.send(
            f'Refilled image list at <t:{current_time_unix}:F> with {len(filtered_image_list)} '
            f'images.')

    # pop top of the stack from the list, so we don't get it again
    image_path = filtered_image_list.pop()

    with open(image_path, 'rb') as img:
        banner = img.read()

    # set discord banner while checking exceptions
    if guild:
        try:
            await guild.edit(banner=banner)
            print(f'Changed banner to `{image_path}` at time {current_time}.')
            discord_logging and await log_channel.send(
                f'Changed banner to `{image_path}` at time <t:{current_time_unix}:F>.')
        except discord.Forbidden as e:
            print(f'Failed to change banner at time {current_time} due to insufficient permissions: {e}')
            discord_logging and await log_channel.send(
                f'Failed to change banner at time <t:{current_time_unix}:F> due to insufficient '
                f'permissions: {e}')
        except discord.HTTPException as e:
            print(f'Failed to change banner at time {current_time} due to an HTTPException: {e}')
            discord_logging and await log_channel.send(
                f'Failed to change banner at time <t:{current_time_unix}:F> due to an '
                f'HTTPException: {e}')
        except Exception as e:
            print(f'Failed to change banner at time {current_time}: {e}')
            discord_logging and await log_channel.send(
                f'Failed to change banner at time <t:{current_time_unix}:F>: {e}')


async def change_banner_task(interval, discord_logging):
    """
    function responsible for repeatedly changing the server banner at an interval
    :param discord_logging:
    :param ctx:
    :param interval: int
        number of minutes to wait before changing server banner (recommended is 5)
    :return:
    """
    while True:
        await change_banner(discord_logging)
        await asyncio.sleep(interval * 60)


@bot.tree.command(name='change_banner_periodically', description="Change server banner periodically from fan art.")
@app_commands.describe(minutes="Interval in minutes to change banner",
                       logging="Determine if we should log changes in discord channel")
async def change_banner_periodically(interaction: discord.Interaction, minutes: int = 5, logging: bool = False):
    """
    Slash command to change server banner periodically.
    :param interaction:
    :param minutes: Integer value which is the interval in minutes to change the banner.
    :param logging: Bool value to determine if we should turn on discord logging or not
    :return:
    """
    if interaction.user.id != config.FLATPAPER_DISCORD_ID:
        print(f'Unauthorized usage of change_banner_periodically by {interaction.user.id}.')
        await interaction.response.send_message(
            f'Unauthorized usage of change_banner_periodically by {interaction.user.display_name}.')
        return

    global banner_task

    if banner_task and not banner_task.done():
        banner_task.cancel()
        await interaction.response.send_message("Stopped the previous banner change task.")

    banner_task = bot.loop.create_task(change_banner_task(minutes, logging))
    await interaction.response.send_message(f"Started changing banner every {minutes} minutes.")


@bot.tree.command(name='get_banner_queue_size', description='Fetches server banner queue size.')
async def get_banner_queue_size(interaction: discord.Interaction):
    queue_size = len(filtered_image_list)
    await interaction.response.send_message(f"There are {queue_size} fan-art images in the queue before it gets "
                                            f"refilled.")


@bot.tree.command(name='dl_img_from_ch_before_date',
                  description="Download images from a channel starting from a specific date")
@app_commands.describe(channel="Channel to download images from", date="Date in YYYY-MM-DD")
async def download_images_from_channel_after_date(interaction: discord.Interaction, channel: discord.TextChannel,
                                                  date: str):
    if interaction.user.id != config.FLATPAPER_DISCORD_ID:
        await interaction.followup.send("Only FlatPaper should be able to run this.")
        return

    await interaction.response.defer()  # indicate that bot is processing slash command

    # attempt to read date parameter as a string and convert it
    try:
        start_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        await interaction.followup.send("Invalid date format. Please use YYYY-MM-DD.")
        return

    await interaction.followup.send(f'Downloading images from {channel.mention} starting from {date}...')

    # process message history, add links to image_urls for files with specific extensions
    # limit is because default is 100, so it won't read entire message history
    image_urls = []
    async for message in channel.history(limit=635, after=start_date, oldest_first=True):
        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in ['png', 'jpg', 'jpeg', 'gif']):
                image_urls.append(attachment.url)

    # check if there are any images to download, otherwise make directory if it doesn't exist
    if not image_urls:
        await interaction.followup.send("No images found.")
        return
    if not os.path.exists(config.FANART_SAVE_DIR):
        os.makedirs(config.FANART_SAVE_DIR)

    async with aiohttp.ClientSession() as session:
        for i, url in enumerate(image_urls):
            print(f'Downloading {url}')
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        file_name = url.split('/')[-1].split('?')[0]  # split to get file name
                        file_path = os.path.join(config.FANART_SAVE_DIR, file_name)
                        with open(file_path, 'wb') as f:
                            f.write(await response.read())
                    else:
                        print(f'Failed to download {url}, status code: {response.status}')
            except Exception as e:
                print(f'Failed to download {url}, exception: {e}')

            await asyncio.sleep(1)

    await interaction.followup.send(f'Downloaded {len(image_urls)} images.')
    print(f'Downloaded {len(image_urls)} images.')


@bot.tree.command(name='ping', description='Bot Latency')
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f'Pong! Latency of bot is {round(bot.latency * 1000)} ms.')


@bot.command(description='Sync slash commands (flatpaper only)')
async def sync_slash_commands(ctx: discord.ext.commands.Context):
    if ctx.author.id == config.FLATPAPER_DISCORD_ID:
        s = await bot.tree.sync()
        print(f'Synced {len(s)} commands.')
        await ctx.send("Updated slash commands.")
        return
    await ctx.send("Unauthorized command.")


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')


bot.run(config.TOKEN)
