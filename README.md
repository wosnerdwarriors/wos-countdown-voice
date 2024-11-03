# WOS Countdown bot for discord

# Setup Guide
## Register a new discord bot
* Go to https://discord.com/developers/applications and create a new application
* go to bot on the sidebar and regenerate the token. Save this token for later.

## Join the bot to your server
go to oauth2 section on the left and under OAuth2 URL Generator select
* bot
* applications.commands

Now underneath this for Bot Permissions select
* View Channels
* Connect
* Speak
* Send Messages
* Read Message History
* Use Slash Commands
* Manage Messages

Now under "Generated URL" there will be a url. copy that and open it in your browser. It'll prompt you to join the bot to a server you own or are admin of. Join the bot.

## Setup the config/bot code
Now within the code project,
* copy example.config.json to config.json
* add the token you regenerated in the first step to your config file under the "token" key.
* set roles-allowed-to-control-bot to have the roles you want to use or leave empty to allow anyone to control the bot
* set purge-and-repost-on-channel-ids to  [] or if you have a commands channel already, add those IDs to this list
* install pip3 and python3 if you haven't already. you can get these packed together from the windows app store or on ubuntu/linux:
```
apt install pip3 python3
```

* install requirements by running the following:
```
pip3 install -r requirements.txt
```
* now run the script using windows
```
main.py
```

* or linux:

```
./main.py
```


# Managing the bot
webserver by default starts on http://127.0.0.1:5544/ . You can do join/leave channels and play sounds from here including seeing all the logs
Post the controls in a channel
```
/postcontrols
```
If you don't have this option, try restarting discord.

# Bugs?
This was very recently written and hasn't had extensive testing so expect there may be some issues. 
Please ping deathmarcher on our discord server which you can find a link to on https://wosnerds.com/
Or alternatively create an issue on this project in github
