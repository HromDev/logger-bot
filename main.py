import logging
import os

import disnake
from disnake.ext import commands
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("server_logger_bot")


def create_bot() -> commands.Bot:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError("DISCORD_TOKEN is missing; configure it in the .env file")

    from cogs.server_logs import DEFAULT_LOG_CHANNEL_ID

    if DEFAULT_LOG_CHANNEL_ID <= 0:
        raise RuntimeError(
            "LOG_CHANNEL_DEFAULT must be a positive Discord channel ID in .env"
        )

    intents = disnake.Intents.none()
    intents.guilds = True
    intents.members = True
    intents.moderation = True
    intents.voice_states = True
    intents.messages = True
    intents.message_content = True
    intents.reactions = True
    intents.polls = True
    intents.guild_scheduled_events = True
    intents.automod = True

    bot = commands.Bot(
        command_prefix=commands.when_mentioned,
        intents=intents,
        help_command=None,
    )
    bot.load_extension("cogs.server_logs")
    logger.info("Loaded server logging extension")
    return bot


def main() -> None:
    bot = create_bot()
    bot.run(os.environ["DISCORD_TOKEN"])


if __name__ == "__main__":
    main()
