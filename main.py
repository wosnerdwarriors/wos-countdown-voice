#!/usr/bin/env python3
import asyncio
from discord_bot import main_bot
from web_server import main_web

async def main():
	await asyncio.gather(
		main_bot(),
		main_web()
	)

asyncio.run(main())

