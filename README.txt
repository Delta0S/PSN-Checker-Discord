# Project README

## Important Information

Welcome to our project! This guide will help you set up and run the bot smoothly. Please follow the instructions below.

First, you'll need to install all the required packages. The easiest way is to use the `requirements.txt` file. Open your command prompt or terminal and run the following command: `py -m pip install -r requirements.txt`. If this doesn't work, you can manually install the required packages one by one: `pip install PSNAWP` and `pip install discord.py==2.3.2`. After installing the packages, you'll need to fill in some configuration details. Specifically, you'll need: **npsso** (a key required for accessing the PlayStation Network API) and **Discord bot token** (necessary for your bot to connect to Discord). Make sure to replace the placeholder values with your actual keys in the configuration file. If you encounter the `ModelNotFoundError` error, it might be due to an issue with the `discord.py` package. To resolve this, you can reinstall the package: `pip uninstall discord.py` and `pip install discord.py`. Once everything is set up, you can run the bot using the following command: `python main.py`. You don't need to give me credit, but it would be appreciated. Just don't claim it as your own work. Some credits to: [Killerjeremy07's Psn_Checker](https://github.com/Killerjeremy07/Psn_Checker). Enjoy!
