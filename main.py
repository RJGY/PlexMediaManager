from bot import MusicBot

def main():
    bot = MusicBot(cogs=['download']) # Just load the download cog for now
    bot.run()

if __name__ == "__main__":
    main()
