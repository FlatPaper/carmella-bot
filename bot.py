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
bot = commands.Bot(command_prefix='c?', intents=intents)


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
