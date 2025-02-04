# WOS Countdown Bot for Discord

## Overview
The **WOS Countdown Bot** is a Discord bot that plays countdown audio clips in voice channels. It also provides a web interface for controlling the bot and viewing logs.

---

## 🚀 Setup Guide
### 1️⃣ **Register a New Discord Bot**
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and **create a new application**.
2. In the sidebar, select **Bot** and click **Regenerate Token**.
   - **⚠️ Save this token** – you will need it later!

### 2️⃣ **Invite the Bot to Your Server**
1. In the sidebar, go to **OAuth2 → URL Generator**.
2. Under **Scopes**, select:
   - ✅ `bot`
   - ✅ `applications.commands`
3. Under **Bot Permissions**, select:
   - ✅ `View Channels`
   - ✅ `Connect`
   - ✅ `Speak`
   - ✅ `Send Messages`
   - ✅ `Read Message History`
   - ✅ `Use Slash Commands`
   - ✅ `Manage Messages`
4. Copy the **Generated URL** and open it in your browser.
5. Select a **server you own** and invite the bot.

---

## 🔧 **Configuration**
### 1️⃣ **Set Up the Config File**
1. In the project directory, copy `example.config.json` to `config.json`:
   ```sh
   cp example.config.json config.json
   ```
2. Open `config.json` and **add your bot token**:
   ```json
   {
       "token": "YOUR_BOT_TOKEN_HERE",
       "roles-allowed-to-control-bot": [],
       "purge-and-repost-on-channel-ids": []
   }
   ```
   - Set **`roles-allowed-to-control-bot`** to restrict control to specific roles.
   - Set **`purge-and-repost-on-channel-ids`** to an array of channel IDs if you want the bot to automatically clean and repost control messages.

---

## 🛠️ **Installation**
### 📌 **Step 1: Install Python and Pip**
#### **Linux (Debian/Ubuntu)**:
```sh
sudo apt update && sudo apt install python3 python3-pip ffmpeg
```
#### **Linux (Fedora/RHEL)**:
```sh
sudo dnf install python3 python3-pip ffmpeg
```
#### **Linux (Arch Linux)**:
```sh
sudo pacman -S python python-pip ffmpeg
```
#### **macOS (Homebrew)**:
```sh
brew install python3 ffmpeg
```
#### **Windows**:
1. Download [Python 3](https://www.python.org/downloads/) and install it.
   - **Ensure you select**: ✅ "Add Python to PATH"
2. Open **PowerShell** (Win+X → Terminal) and install FFmpeg:
   ```sh
   winget install -e --id Gyan.FFmpeg
   ```

---

### 📌 **Step 2: Install Required Python Modules**
Run the following command **inside the project directory**:
```sh
pip3 install -r requirements.txt
```

---

## ▶️ **Running the Bot**
#### **Linux/macOS**:
```sh
./main.py
```
#### **Windows (PowerShell)**:
```sh
python main.py
```

### 🔄 **Bypass Module Checks (Optional)**
To skip dependency validation, use:
```sh
./main.py --bypass-module-check
```

---

## 🎮 **Using the Bot**
### 🕹️ **Web Interface**
The bot starts a **web server** on:
   - **URL**: `http://127.0.0.1:5544/`
   - Features:
     - View logs
     - Join/leave voice channels
     - Play sounds

### 🖥️ **Posting Controls in a Channel**
Use the following **slash command** in Discord:
```sh
/postcontrols
```
If you don’t see the command, **restart Discord**.

---

## 🛑 **Known Issues**
- If **CPU performance is low**, countdowns may **go out of sync**. Consider running the bot on a **dedicated server**.

---

## 🐞 **Found a Bug?**
This bot is still **new and under testing**.
- Ping **deathmarcher** on our [Discord Server](https://wosnerds.com/)
- Or **create an issue** on GitHub!

Happy Counting! 🎉

