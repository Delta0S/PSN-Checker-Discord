import base64
import discord
from discord import app_commands
from discord.ext import commands
from psnawp_api.core.psnawp_exceptions import PSNAWPForbidden, PSNAWPNotFound, PSNAWPServerError
import config
from psnawp_api.models.trophies.trophy_summary import TrophySummary
from custom_bot import Bot
import logging
from datetime import datetime
import asyncio
from tenacity import retry, wait_fixed, stop_after_attempt, retry_if_exception_type
from requests.exceptions import ConnectionError

# Configure logging
logging.basicConfig(level=logging.INFO)

def format_trophies(trophy_infos: TrophySummary):
    trophy_amounts = {
        config.TROPHY_TEXTS[3]: trophy_infos.earned_trophies.bronze,
        config.TROPHY_TEXTS[2]: trophy_infos.earned_trophies.silver,
        config.TROPHY_TEXTS[1]: trophy_infos.earned_trophies.gold,
        config.TROPHY_TEXTS[0]: trophy_infos.earned_trophies.platinum
    }

    trophy_fields = [
        ("Level", f"<:LevelPlatinum:1217243208006766653> {trophy_infos.trophy_level}"),
        ("Platinum", f"<:TrophyPlatinum:1217243440937570364> {trophy_amounts[config.TROPHY_TEXTS[0]]}"),
        ("Gold", f"<:trophygold:1219614746945523722> {trophy_amounts[config.TROPHY_TEXTS[1]]}"),
        ("Silver", f"<:trophysilver:1219614762330226708> {trophy_amounts[config.TROPHY_TEXTS[2]]}"),
        ("Bronze", f"<:trophybronze:1219614779925204992> {trophy_amounts[config.TROPHY_TEXTS[3]]}"),
        ("Total", f"<:trophynone:1219614724283564112> {sum(trophy_amounts.values())}")
    ]

    return trophy_fields

def format_last_online(last_online_str):
    if last_online_str == "N/A":
        return "N/A"
    last_online_dt = datetime.fromisoformat(last_online_str.replace('Z', '+00:00'))
    return last_online_dt.strftime("%b %d, %Y %I:%M %p")

class PSNCog(commands.Cog):
    def __init__(self, bot):
        self.bot: Bot = bot

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3), retry=retry_if_exception_type(ConnectionError))
    async def fetch_presence_info(self, user):
        return user.get_presence()

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3), retry=retry_if_exception_type(ConnectionError))
    async def fetch_profile_info(self, user):
        return user.profile()

    async def send_account_info(self, interaction: discord.Interaction, user):
        embed = discord.Embed(
            title="",
            description="",
        )
        embed.set_author(
            name="PlayStation Network",
            icon_url="https://lachaisesirv.sirv.com/icons8-playstation-144%20(1).png"
        )
        embed.set_thumbnail(url=user.profile()["avatars"][1]["url"])

        # Fetch online status
        try:
            presence_info = await self.fetch_presence_info(user)
            logging.info(f"Presence info: {presence_info}")
            basic_presence = presence_info.get("basicPresence", {})
            primary_platform_info = basic_presence.get("primaryPlatformInfo", {})
            is_online = primary_platform_info.get("onlineStatus", "Unknown")
            online_status_emoji = "<:Online:1258522610124460112>" if is_online == "online" else "<:FakeNitroEmoji:1258522566382063717>"
            last_online = primary_platform_info.get("lastOnlineDate", "N/A")
        except PSNAWPForbidden:
            is_online = "Unknown"
            online_status_emoji = "<:FakeNitroEmoji:1258522566382063717>"
            last_online = "N/A"

        # Fetch PlayStation Plus status
        try:
            profile_info = await self.fetch_profile_info(user)
            logging.info(f"Profile info: {profile_info}")
            is_ps_plus = profile_info.get("isPlus", False)
            is_verified = profile_info.get("isOfficiallyVerified", False)
            region = profile_info.get("region")
            profile_color = profile_info.get("profileColor", "Unknown")
        except PSNAWPForbidden:
            is_ps_plus = "Unknown"
            is_verified = "Unknown"
            region = "Unknown"
            profile_color = "Unknown"

        verified_emoji = "<:VerifiedLight:1219025459791265802>" if is_verified else ""
        ps_plus_emoji = "| <:PSPlus:1217247847104122910>" if is_ps_plus else ""
        username_field = f"``{user.online_id}``  | {online_status_emoji} {verified_emoji} {ps_plus_emoji}".strip()

        fields = {
            "Username": username_field,
            "Region": f'``{region}``',
            "Profile Color": f'``{profile_color}``',
            "AID": f"``{user.account_id}``",
            "Last Online": f"``{format_last_online(last_online)}``"
        }

        for name, value in fields.items():
            embed.add_field(name=name, value=value, inline=True if name != "Last Online" else False)

        try:
            trophy_infos = user.trophy_summary()
            trophy_fields = format_trophies(trophy_infos)
            for name, value in trophy_fields:
                embed.add_field(name=name, value=value, inline=True)
        except PSNAWPForbidden:
            embed.add_field(name="Trophies", value="❌ Private", inline=False)

        embed.add_field(name="About Me", value=f"```{user.profile()['aboutMe']}                                                                                                    ```", inline=False)

        embed.set_footer(text="Powered by FreehawkX",
                         icon_url="https://lachaisesirv.sirv.com/icons8-playstation-144%20(1).png")

        await interaction.followup.send(content=f"{interaction.user.mention}", embed=embed, ephemeral=True)

    @app_commands.command(
        name="psn",
        description="Display information concerning the given PSN account"
    )
    @app_commands.describe(id="Your online ID (A.K.A PSN username)")
    @app_commands.describe(private="Should the message revealing your account details be private or public")
    async def psn(self, interaction: discord.Interaction, id: str, private: bool = False):
        interaction.response: discord.InteractionResponse
        await interaction.response.defer(ephemeral=private)

        user = self.bot.psnawp.user(online_id=id)

        if not user:
            await interaction.followup.send("Account not found.", ephemeral=True)
            return

        await self.send_account_info(interaction, user)

    @psn.error
    async def psn_error(self, interaction: discord.Interaction, error):
        if isinstance(error, PSNAWPNotFound):
            await interaction.followup.send("Account not found.", ephemeral=True)
        elif isinstance(error, PSNAWPForbidden):
            await interaction.followup.send("You do not have permission to view this account.", ephemeral=True)
        elif isinstance(error, PSNAWPServerError):
            await interaction.followup.send("Server error. Please try again later.", ephemeral=True)
        elif isinstance(error, ConnectionError):
            await interaction.followup.send("Unable to connect to PlayStation Network. Please try again later.", ephemeral=True)
        else:
            await interaction.followup.send(f"An error occurred: `{error}`", ephemeral=True)
        await asyncio.sleep(5)
        await interaction.delete_original_response()

    @app_commands.command(
        name="acc_id",
        description="Display information concerning the given PSN account using the account ID"
    )
    @app_commands.describe(num_id="The account ID (numeric)")
    @app_commands.describe(private="Should the message revealing your account details be private or public")
    async def acc_id(self, interaction: discord.Interaction, num_id: str, private: bool = False):
        interaction.response: discord.InteractionResponse
        await interaction.response.defer(ephemeral=private)

        try:
            num_id = int(num_id)
        except ValueError:
            await interaction.followup.send("Please input a valid integer for the account ID.", ephemeral=True)
            return

        user = self.bot.psnawp.user(account_id=num_id)

        if not user:
            await interaction.followup.send("Account not found.", ephemeral=True)
            return

        await self.send_account_info(interaction, user)

    @acc_id.error
    async def acc_id_error(self, interaction: discord.Interaction, error):
        if isinstance(error, PSNAWPNotFound):
            await interaction.followup.send("Account not found.", ephemeral=True)
        elif isinstance(error, PSNAWPForbidden):
            await interaction.followup.send("You do not have permission to view this account.", ephemeral=True)
        elif isinstance(error, PSNAWPTooManyRequests):
            await interaction.followup.send("Rate limit exceeded. Please try again later.", ephemeral=True)
        elif isinstance(error, PSNAWPServerError):
            await interaction.followup.send("Server error. Please try again later.", ephemeral=True)
        elif isinstance(error, ConnectionError):
            await interaction.followup.send("Unable to connect to PlayStation Network. Please try again later.", ephemeral=True)
        else:
            await interaction.followup.send(f"An error occurred: `{error}`", ephemeral=True)
        await asyncio.sleep(5)
        await interaction.delete_original_response()

    @app_commands.command(
        name="friends",
        description="Display the friends list for the given PSN account"
    )
    @app_commands.describe(id="Your online ID (A.K.A PSN username)")
    async def friends(self, interaction: discord.Interaction, id: str):
        interaction.response: discord.InteractionResponse
        await interaction.response.defer(ephemeral=True)

        user = self.bot.psnawp.user(online_id=id)

        if not user:
            await interaction.followup.send("Account not found.", ephemeral=True)
            return

        try:
            friends_list = user.friends_list()
            friend_ids = friends_list["friendIds"]
            total_friends = friends_list["totalItemCount"]
        except PSNAWPForbidden:
            await interaction.followup.send("Unable to retrieve friends list. It may be private.", ephemeral=True)
            return
        except PSNAWPTooManyRequests:
            await interaction.followup.send("Rate limit exceeded. Please try again later.", ephemeral=True)
            return
        except PSNAWPServerError:
            await interaction.followup.send("Server error. Please try again later.", ephemeral=True)
            return
        except ConnectionError:
            await interaction.followup.send("Unable to connect to PlayStation Network. Please try again later.", ephemeral=True)
            return
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
            await interaction.followup.send(f"An unexpected error occurred: {e}", ephemeral=True)
            return

        friends_str = "\n".join([f"• {fid}" for fid in friend_ids])

        embed = discord.Embed(
            title=f"{user.online_id}'s Friends ({total_friends})",
            description=friends_str or "No friends found."
        )
        embed.set_footer(text="Powered by FreehawkX",
                         icon_url="https://lachaisesirv.sirv.com/icons8-playstation-144%20(1).png")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="recent_games",
        description="Display the recently played games for the given PSN account"
    )
    @app_commands.describe(id="Your online ID (A.K.A PSN username)")
    async def recent_games(self, interaction: discord.Interaction, id: str):
        interaction.response: discord.InteractionResponse
        await interaction.response.defer(ephemeral=True)

        user = self.bot.psnawp.user(online_id=id)

        if not user:
            await interaction.followup.send("Account not found.", ephemeral=True)
            return

        try:
            titles = user.titles()
            recent_games = titles["titles"]
        except PSNAWPForbidden:
            await interaction.followup.send("Unable to retrieve recent games. It may be private.", ephemeral=True)
            return
        except PSNAWPTooManyRequests:
            await interaction.followup.send("Rate limit exceeded. Please try again later.", ephemeral=True)
            return
        except PSNAWPServerError:
            await interaction.followup.send("Server error. Please try again later.", ephemeral=True)
            return
        except ConnectionError:
            await interaction.followup.send("Unable to connect to PlayStation Network. Please try again later.", ephemeral=True)
            return
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
            await interaction.followup.send(f"An unexpected error occurred: {e}", ephemeral=True)
            return

        recent_games_str = "\n".join([f"{game['name']} ({game['lastPlayedDateTime']})" for game in recent_games])

        embed = discord.Embed(
            title=f"{user.online_id}'s Recently Played Games",
            description=recent_games_str or "No recent games found."
        )
        embed.set_footer(text="Powered by FreehawkX",
                         icon_url="https://lachaisesirv.sirv.com/icons8-playstation-144%20(1).png")

        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(PSNCog(bot))

# Entry point for starting the bot
if __name__ == "__main__":
    logging.info("Starting the bot...")
    bot = Bot(command_prefix="!", intents=discord.Intents.all())

    @bot.event
    async def on_ready():
        logging.info(f"Logged in as {bot.user}")

    asyncio.run(setup(bot))
    bot.run(config.TOKEN)
