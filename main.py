from bot import MusicBot

def main():
    bot = MusicBot(cogs=None) # Modified to load all cogs
    bot.run()

if __name__ == "__main__":
    main()
