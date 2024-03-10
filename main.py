import asyncio
import os

import aiosqlite
import colorama
import hikari
import humanfriendly
import miru
import tanjun
from colorama import Fore
from dotenv import load_dotenv
import requests
import base64

requires_db_fetch = not(os.path.exists("./data/database.db") and os.path.exists("./data/qotd.json")
                        and os.path.exists("./data/triggers.json"))

try:
    scf_key = os.getenv('SCFKEY')
    if requires_db_fetch:
        URL = "https://sky.dssoftware.ru/python/backup.php?method=getLatestDatabase&token=" + scf_key

        r = requests.get(url=URL)
        data = r.json()

        if data['response'] != "OK":
            raise Exception("Database backup servers are down.")
        if data['data']['exists']:
            db_contents = base64.b64decode(data['data']['database'])
            qotd_contents = base64.b64decode(data['data']['qotd'])
            triggers_contents = base64.b64decode(data['data']['triggers'])

            with open("./data/database.db", "wb") as db_file:
                db_file.write(db_contents)
            with open("./data/qotd.json", "wb") as qotd_file:
                db_file.write(qotd_contents)
            with open("./data/triggers.json", "wb") as triggers_file:
                triggers_file.write(triggers_contents)

        print("Successfully loaded configuration from backup.")
    else:
        try:
            with open("./data/database.db", "rb") as db_contents:
                file_database = db_contents.read()
        except:
            file_database = None
            print("Failed to backup database!")

        try:
            with open("./data/qotd.json", "rb") as qotd_contents:
                file_qotd = qotd_contents.read()
        except:
            file_qotd = None
            print("Failed to backup QOTD!")

        try:
            with open("./data/triggers.json", "rb") as triggers_contents:
                file_triggers = triggers_contents.read()
        except:
            file_triggers = None
            print("Failed to backup Triggers!")

        files = {
            'database': file_database,
            'qotd': file_qotd,
            'triggers': file_triggers
        }
        requests.post("https://sky.dssoftware.ru/python/backup.php?method=backupDatabase&token=" + scf_key, files=files)
        print("Successfully uploaded backup database.")
except:
    print("Failed to obtain Database Instance, please, make sure backup servers are working properly.")
    quit()

from utils.config.config import Config, ConfigHandler
from utils.database.connection import DBConnection
from utils.webserver.api_handler import APIHandler

from components.join_buttons import JoinButtons

#######################
#    General Setup    #
#######################

colorama.init(autoreset=True)
load_dotenv()

asyncio.run(ConfigHandler().load_config())

asyncio.run(DBConnection().connect_db())
asyncio.run(APIHandler().start())

from utils.handlers import is_warn, handle_warn, is_bridge_message, handle_tatsu
from utils.triggers.triggers import TriggersFileHandler

# trigger_handler = TriggersFileHandler()
# TriggersFileHandler().load_triggers()

###############
#    Hooks    #
###############

command_usage = {
    # ban list
    "banlist add": "+banlist add <IGN> <reason>",
    "banlist check": "+banlist check <IGN>",
    "banlist remove": "+banlist remove <IGN>",
    "banlist info": "+banlist info <IGN>",
    # crisis
    "crisis add": "+crisis add <channel>",
    # masters
    "checkreq": "+checkreq <IGN> [profile]",
    # misc
    "pat": "+pat <user>",
    # moderation
    "ban": "+ban <user> <reason> [--dm yes/no] [--appeal yes/no]",
    "unban": "+unban <user> [reason]",
    "mute": "+mute <user> <duration> [reason]",
    "unmute": "+unmute <user>",
    "warn": "TBI",
    "log": "TBI",
    # stats
    "skycrypt": "+s <ign> [profile]",
    # verify
    "verify": "+verify <ign>",
    "forceverify": "+forceverify <ign> <member>",
    # suggestions
    "suggest": "+suggest <your_suggestion>"
}

hooks = tanjun.Hooks()


@hooks.set_on_parser_error
async def parser_error_hook(ctx: tanjun.abc.MessageContext, error: tanjun.ParserError) -> bool | None:
    # Creates the appropriate embed and sends it
    description = ''
    # Argument number errors
    if isinstance(error, (tanjun.errors.NotEnoughArgumentsError, tanjun.errors.TooManyArgumentsError)):
        # Find the full command to get its usage
        command = list(ctx.command.names)[0]
        if ctx.command.parent is not None:
            command = list(ctx.command.parent.names)[0] + ' ' + command

        if command in command_usage.keys():
            description = f'Incorrect format. Use `{command_usage[command]}`'

    # Argument conversion errors
    elif isinstance(error, tanjun.errors.ConversionError):
        inner_error = error.errors[0]
        # Raised from to_timestamp() converter
        if inner_error.__cause__.__class__ is humanfriendly.InvalidTimespan:
            description = f'{inner_error.args[0]}: `{inner_error.args[1]}`\nTime examples: *1d -> 1 day*, *1h -> 1 hour*.'
        # Raised from to_player_info() converter
        elif inner_error.__cause__.__class__ is NameError:
            description = f'{inner_error.args[0]}: `{inner_error.args[1]}`'
        # Raised from to_member() converter
        elif inner_error.args[0] == "Couldn't find member in this guild":
            description = 'User not a server member or invalid.'
        # Raised from to_user() converter
        elif inner_error.args[0] == "Couldn't find user":
            description = 'User not found.'

    if len(description) == 0:
        description = f'Something went wrong.\nPlease contract an administrator'

    embed = hikari.Embed(
        title='Error',
        description=description,
        color=ConfigHandler().get_config()['colors']['error']
    )
    await ctx.respond(embed=embed)
    return None


######################
#    Client Setup    #
######################

intents = hikari.Intents.ALL_UNPRIVILEGED | hikari.Intents.MESSAGE_CONTENT

bot = hikari.impl.GatewayBot(os.getenv('TOKEN'), intents=intents)
client: tanjun.Client = tanjun.Client.from_gateway_bot(bot, declare_global_commands=ConfigHandler().get_config()[
    'server_id']) \
    .add_prefix("+").set_hooks(hooks).add_check(tanjun.checks.GuildCheck())

client.load_directory("./components")
(
    tanjun.InMemoryConcurrencyLimiter()
    .set_bucket("database_commands", tanjun.BucketResource.GLOBAL, 1)
    .disable_bucket("plugin.meta")
    .add_to_client(client)
)
(
    tanjun.InMemoryCooldownManager()
    .set_bucket("api_commands", tanjun.BucketResource.GLOBAL, 60, 60)
    .set_bucket("crisis", tanjun.BucketResource.GUILD, 1, 300)
    .set_bucket("spam", tanjun.BucketResource.USER, 1, 20)
    .disable_bucket("plugin.meta")
    .add_to_client(client)
)
client.set_type_dependency(aiosqlite.Connection, DBConnection().get_db())
client.set_type_dependency(Config, ConfigHandler().get_config())
miru.install(bot)


###################
#    Listeners    #
###################

@bot.listen(hikari.StartedEvent)
async def on_started(_) -> None:
    view = JoinButtons(ConfigHandler().get_config())
    await view.start()

    print(f'{Fore.YELLOW}{bot.get_me()} is ready')


@bot.listen(hikari.GuildMessageCreateEvent)
async def on_message(event: hikari.GuildMessageCreateEvent) -> None:
    if is_bridge_message(event.message, ConfigHandler().get_config()):
        await handle_tatsu(event)

    if not event.member or event.member.is_bot or event.message.content is None:
        return

    if is_warn(event.message.content):
        await handle_warn(event, ConfigHandler().get_config())

    if TriggersFileHandler().is_trigger(event.message.content):
        await TriggersFileHandler().handle_trigger(event, ConfigHandler().get_config())

if __name__ == "__main__":
    if os.name != "nt":
        import uvloop

        uvloop.install()

    bot.run(asyncio_debug=True)
    asyncio.run(APIHandler().stop())
    asyncio.run(DBConnection().close_db())
    colorama.deinit()
