import asyncio
import logging
from collections import defaultdict
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands
from requests.exceptions import ConnectionError
from tenacity import retry, wait_fixed, stop_after_attempt, retry_if_exception_type

from psnawp_api.core.psnawp_exceptions import PSNAWPForbidden, PSNAWPNotFound, PSNAWPServerError
from psnawp_api.models.trophies.trophy_summary import TrophySummary
from custom_bot import Bot
import config

# Configure logging
logging.basicConfig(level=logging.INFO)

# Constants for emojis
ONLINE_EMOJI = "<:Online:1258522610124460112>"
OFFLINE_EMOJI = "<:FakeNitroEmoji:1258522566382063717>"
VERIFIED_EMOJI = "<:VerifiedLight:1219025459791265802>"
PSPLUS_EMOJI = "<:PSPlus:1217247847104122910>"
PLATINUM_EMOJI = "<:TrophyPlatinum:1217243440937570364>"
GOLD_EMOJI = "<:trophygold:1219614746945523722>"
SILVER_EMOJI = "<:trophysilver:1219614762330226708>"
BRONZE_EMOJI = "<:trophybronze:1219614779925204992>"
TOTAL_EMOJI = "<:trophynone:1219614724283564112>"

def format_trophies(trophy_infos: TrophySummary):
    trophy_amounts = {
        config.TROPHY_TEXTS[3]: trophy_infos.earned_trophies.bronze,
        config.TROPHY_TEXTS[2]: trophy_infos.earned_trophies.silver,
        config.TROPHY_TEXTS[1]: trophy_infos.earned_trophies.gold,
        config.TROPHY_TEXTS[0]: trophy_infos.earned_trophies.platinum
    }

    trophy_fields = [
        ("Level", f"{PLATINUM_EMOJI} {trophy_infos.trophy_level} | {trophy_infos.progress:.0f}%"),
        ("Platinum", f"{PLATINUM_EMOJI} {trophy_amounts[config.TROPHY_TEXTS[0]]}"),
        ("Gold", f"{GOLD_EMOJI} {trophy_amounts[config.TROPHY_TEXTS[1]]}"),
        ("Silver", f"{SILVER_EMOJI} {trophy_amounts[config.TROPHY_TEXTS[2]]}"),
        ("Bronze", f"{BRONZE_EMOJI} {trophy_amounts[config.TROPHY_TEXTS[3]]}"),
        ("Total", f"{TOTAL_EMOJI} {sum(trophy_amounts.values())}")
    ]

    return trophy_fields

def format_last_online(last_online_str):
    if last_online_str == "N/A":
        return "N/A"
    last_online_dt = datetime.fromisoformat(last_online_str.replace('Z', '+00:00'))
    return f"<t:{int(last_online_dt.timestamp())}:R>"

async def handle_error(interaction, message):
    await interaction.followup.send(message, ephemeral=True)

class PSNCog(commands.Cog):
    def __init__(self, bot):
        self.bot: Bot = bot
        self.cooldowns = defaultdict(lambda: 0)

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3), retry=retry_if_exception_type(ConnectionError))
    async def fetch_presence_info(self, user):
        return user.get_presence()

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3), retry=retry_if_exception_type(ConnectionError))
    async def fetch_profile_info(self, user):
        return user.profile()

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3), retry=retry_if_exception_type(ConnectionError))
    async def fetch_friendship_info(self, user):
        return user.friendship()

    async def send_account_info(self, interaction: discord.Interaction, user):
        embed = discord.Embed(
            title="PlayStation Network",
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
            online_status_emoji = ONLINE_EMOJI if is_online == "online" else OFFLINE_EMOJI
            last_online = primary_platform_info.get("lastOnlineDate", "N/A")
            platform = primary_platform_info.get("platform", "Unknown")
            game_title_info_list = basic_presence.get("gameTitleInfoList", [])
        except PSNAWPForbidden:
            is_online = "Unknown"
            online_status_emoji = OFFLINE_EMOJI
            last_online = "N/A"
            platform = "Unknown"
            game_title_info_list = []
        except PSNAWPServerError:
            await handle_error(interaction, "Server error while trying to fetch presence details. Please try again later.")
            return
        except Exception as e:
            logging.error(f"Unexpected error while fetching presence info: {e}")
            await handle_error(interaction, "An unexpected error occurred while fetching presence details. Please try again later.")
            return

        # Fetch PlayStation Plus status and other profile info
        try:
            profile_info = await self.fetch_profile_info(user)
            logging.info(f"Profile info: {profile_info}")
            is_ps_plus = profile_info.get("isPlus", False)
            is_verified = profile_info.get("isOfficiallyVerified", False)
            region = profile_info.get("region", "soon")
            profile_color = profile_info.get("profileColor", "soon")
            recent_games = profile_info.get("recentPlayedGames", [])
            total_games = profile_info.get("totalGamesPlayed", "N/A")
        except PSNAWPForbidden:
            await handle_error(interaction, "The profile is private or you do not have permission to access it.")
            return
        except PSNAWPServerError:
            await handle_error(interaction, "Server error while trying to fetch profile details. Please try again later.")
            return
        except Exception as e:
            logging.error(f"Unexpected error while fetching profile info: {e}")
            await handle_error(interaction, "An unexpected error occurred while fetching profile details. Please try again later.")
            return

        # Fetch friends count
        try:
            friendship_info = await self.fetch_friendship_info(user)
            logging.info(f"Friendship info: {friendship_info}")
            friends_count = friendship_info.get("friendsCount", "N/A")
        except PSNAWPForbidden:
            friends_count = "N/A"
        except PSNAWPServerError:
            await handle_error(interaction, "Server error while trying to fetch friends count. Please try again later.")
            return
        except Exception as e:
            logging.error(f"Unexpected error while fetching friendship info: {e}")
            await handle_error(interaction, "An unexpected error occurred while fetching friends count. Please try again later.")
            return

        verified_emoji = VERIFIED_EMOJI if is_verified else ""
        ps_plus_emoji = f"| {PSPLUS_EMOJI}" if is_ps_plus else ""
        username_field = f"``{user.online_id}``  | {online_status_emoji} {verified_emoji} {ps_plus_emoji}".strip()

        fields = {
            "Username": username_field,
            "Region": f'``{region}``',
            "Profile Color": f'``{profile_color}``',
            "AID": f"``{user.account_id}``",
            "Friends Count": f"``{friends_count}``",
            "Recent Games": "soon",
            "Total Games": "soon",
        }

        for name, value in fields.items():
            embed.add_field(name=name, value=value, inline=True)

        if is_online == "online":
            if not game_title_info_list:
                platform_readable = "PS5" if platform == "PS5" else "PS4" if platform == "PS4" else "Unknown Platform"
                embed.add_field(
                    name="Online",
                    value=f"Online on {platform_readable}",
                    inline=False
                )
            else:
                game_info = game_title_info_list[0]
                np_title_id = game_info.get("npTitleId", "Unknown")
                title_name = game_info.get("titleName", "Unknown")
                launch_platform = game_info.get("launchPlatform", "Unknown")
                embed.add_field(
                    name="Online",
                    value=f"{title_name} | {launch_platform}\n-# {np_title_id}",
                    inline=False
                )
        else:
            embed.add_field(name="Last Online", value=f"{format_last_online(last_online)}", inline=False)

        try:
            trophy_infos = user.trophy_summary()
            trophy_fields = format_trophies(trophy_infos)
            for name, value in trophy_fields:
                embed.add_field(name=name, value=value, inline=True)
        except PSNAWPForbidden:
            logging.info("The trophy information is private or not accessible.")
        except PSNAWPServerError:
            await handle_error(interaction, "Server error while trying to fetch trophy information. Please try again later.")
            return
        except Exception as e:
            logging.error(f"Unexpected error while fetching trophy info: {e}")
            await handle_error(interaction, "An unexpected error occurred while fetching trophy information. Please try again later.")
            return

        embed.add_field(name="About Me", value=f"```{user.profile()['aboutMe']}```", inline=False)

        account_image_url = f"https://image.api.playstation.com/profile/images/acct/prod/{user.account_id}/profile.JPEG"
        embed.set_image(url=account_image_url)

        embed.set_footer(text="IN BETA, ISSUES MAY OCCUR", icon_url="https://lachaisesirv.sirv.com/icons8-playstation-144%20(1).png")

        view = discord.ui.View()
        button = discord.ui.Button(label="Tutorial", style=discord.ButtonStyle.primary, custom_id="tutorial_button")
        view.add_item(button)

        async def button_callback(interaction):
            await interaction.response.send_message("BETA TEST", ephemeral=True)

        button.callback = button_callback

        await interaction.followup.send(content=f"{interaction.user.mention}", embed=embed, view=view, ephemeral=True)

    async def check_cooldown(self, interaction, user_id, command_name, cooldown_seconds):
        current_time = datetime.now().timestamp()
        if current_time < self.cooldowns[(user_id, command_name)]:
            retry_after = self.cooldowns[(user_id, command_name)] - current_time
            await interaction.followup.send(f"This command is on cooldown. Try again after {retry_after:.2f} seconds.", ephemeral=True)
            return False
        self.cooldowns[(user_id, command_name)] = current_time + cooldown_seconds
        return True

    @app_commands.command(
        name="psn",
        description="Display information concerning the given PSN account"
    )
    @app_commands.describe(id="Your online ID (A.K.A PSN username)")
    @app_commands.describe(private="Should the message revealing your account details be private or public")
    async def psn(self, interaction: discord.Interaction, id: str, private: bool = False):
        await interaction.response.defer(ephemeral=private)

        user_id = interaction.user.id
        command_name = "psn"
        cooldown_seconds = 18

        if not await self.check_cooldown(interaction, user_id, command_name, cooldown_seconds):
            return

        user = self.bot.psnawp.user(online_id=id)

        try:
            await self.send_account_info(interaction, user)
        except PSNAWPNotFound:
            await handle_error(interaction, f"The user `{id}` could not be found.")
        except PSNAWPServerError:
            await handle_error(interaction, f"Server error while trying to fetch details for `{id}`. Please try again later.")
        except Exception as e:
            logging.error(f"Unexpected error while processing the command: {e}")
            await handle_error(interaction, "An unexpected error occurred. Please try again later.")

async def setup(bot):
    await bot.add_cog(PSNCog(bot))
