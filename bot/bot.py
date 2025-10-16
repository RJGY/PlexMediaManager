import asyncio
from aiohttp import web
import os
from pathlib import Path
import logging
import discord
from discord import app_commands # Added
from discord.ext import commands
from dotenv import load_dotenv

async def health_check(request):
    return web.Response(text="ok")

async def start_web_app():
    app = web.Application()
    app.router.add_get("/health", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", os.getenv("HEALTH_CHECK_PORT"))
    await site.start()
    print(f"Health check server running on port {os.getenv('HEALTH_CHECK_PORT')}")


class MusicBot(commands.Bot):
    def __init__(self, cogs):
        if not cogs:
            self._cogs = [p.stem for p in Path(".").glob("./bot/cogs/*.py")]
        else:
            self._cogs = cogs
        super().__init__(command_prefix=self.prefix, case_insensitve=True, intents=discord.Intents.all())
        logging.basicConfig(level=logging.DEBUG,
                            format="%(levelname)s %(asctime)s: %(name)s: %(message)s (Line: %(lineno)d) [%(filename)s]",
                            datefmt="%d/%m/%Y %I:%M:%S %p")

    async def setup(self):
        logging.info("Running setup...")

        for cog in self._cogs:
            await self.load_extension(f"bot.cogs.{cog}")
            logging.info(f"Loaded '{cog}' cog.")
        
        logging.info("Starting health check server...")
        await start_web_app()
        logging.info("Health check server started.")

        logging.info("Setup completed.")

    def run(self):
        logging.info("Running bot.")
        load_dotenv()
        asyncio.run(self.setup())
        super().run(os.getenv("DISCORD_TOKEN"), reconnect=True)

    async def shutdown(self):
        logging.info("Closing connection to Discord...")
        await super().close()

    async def close(self):
        logging.info("Closing on keyboard interrupt...")
        await self.shutdown()

    async def on_connect(self):
        logging.info(f"Connected to Discord (latency: {self.latency*1000:,.0f} ms).")

    async def on_resumed(self):
        logging.info("Bot resumed.")

    async def on_disconnect(self):
        logging.info("Bot disconnected.")

    async def on_error(self, err, *args, **kwargs):
        raise

    async def on_command_error(self, ctx, exc):
        raise getattr(exc, "original", exc)

    async def on_ready(self):
        self.client_id = (await self.application_info()).id
        try:
            synced = await self.tree.sync()
            logging.info(f"Synced {len(synced)} application commands globally.")
        except Exception as e:
            logging.error(f"Failed to sync application commands: {e}")
        logging.info("Bot ready.")

    async def prefix(self, bot, msg):
        return commands.when_mentioned_or(os.getenv("SYMBOL"))(bot, msg)

    async def process_commands(self, msg):
        ctx = await self.get_context(msg, cls=commands.Context)

        if ctx.command is not None:
            logging.info(ctx.message.content)
            await self.invoke(ctx)

    async def on_message(self, msg):
        if not msg.author.bot:
            await self.process_commands(msg)