# main.py

import asyncio
import discord
from discord.ext import tasks, commands
from custom_bot import Bot
import config
from keep_alive import keep_alive

# Initialize Discord client with all intents
intents = discord.Intents.all()
bot = Bot(psn_api_token=config.Secrets.PSN_API, intents=intents, command_prefix="/")

@bot.hybrid_command(name='ping', description='Test if bot is responding!')
async def ping(ctx: commands.Context):
    await ctx.send(f'{round(bot.latency * 1000)}ms')

# Define custom statuses
activities = [
    "🔗 dsc.gg/spo-ps",
]

# Function to update bot's custom activity
@tasks.loop(seconds=15)
async def update_activity():
    for activity in activities:
        await bot.change_presence(status=discord.Status.do_not_disturb, activity=discord.Game(name=activity))
        await asyncio.sleep(1)  # Sleep for 1 second between activity updates to prevent rate limiting

@bot.event
async def on_ready():
    print("Bot is now working!")
    update_activity.start()

async def main():
    try:
        # Load the psn_cog extension
        await bot.load_extension("psn_cog")
        await bot.start(config.Secrets.BOT_TOKEN)
    except Exception as e:
        print(f"Error starting the bot: {e}")

if __name__ == "__main__":
    keep_alive()  # Keep the bot alive with the keep_alive function
    asyncio.run(main())
