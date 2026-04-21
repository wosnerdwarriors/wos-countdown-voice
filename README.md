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
4. Navigate to **Bot**, and enable:
   - ✅ `**Presence Intent**`
   - ✅ `**Server Members Intent**`
   - ✅ `**Message Content Intent**`
5. Copy the **Generated URL** and open it in your browser.
6. Select a **server you own** and invite the bot.

Alternatively, here's the url you would use if you replace your clientID

```
https://discord.com/oauth2/authorize?scope=bot%20applications.commands&permissions=274878221440&client_id=YOUR_CLIENT_ID
```

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
3. Configure the system path for FFmpeg:
   - Add FFmpeg to system PATH(replace actual path as needed) using commands or via UI:
   ```bash
   setx PATH "%PATH%;C:\ffmpeg\bin"
   ```
   Or, if needed temporarily during runtime in powershell:
   ```powershell
   $env:Path += ";C:\Users\<Your-User>\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_<hash>\ffmpeg\bin"
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

## 🐳 **Docker Run Instructions**

You can run the bot using prebuilt Docker images available on Docker Hub.

### **Main Branch (`latest`)**  
This image is built from the `main` branch and tagged as `latest`.

#### **Linux/macOS** (With `sound-clips` folder binding):
```sh
docker run -it --rm \
  --name wos-countdown-bot \
  -v $(pwd)/config.json:/app/config.json \
  -v $(pwd)/sound-clips:/app/sound-clips \
  -p 127.0.0.1:5544:5544 \
  deathmarcher/wos-countdown-bot:latest
```

#### **Linux/macOS** (Without `sound-clips` folder binding):
```sh
docker run -it --rm \
  --name wos-countdown-bot \
  -v $(pwd)/config.json:/app/config.json \
  -p 127.0.0.1:5544:5544 \
  deathmarcher/wos-countdown-bot:latest
```

#### **Windows PowerShell** (With `sound-clips` folder binding):
```powershell
docker run -it --rm `
  --name wos-countdown-bot `
  -v ${PWD}/config.json:/app/config.json `
  -v ${PWD}/sound-clips:/app/sound-clips `
  -p 127.0.0.1:5544:5544 `
  deathmarcher/wos-countdown-bot:latest
```

#### **Windows PowerShell** (Without `sound-clips` folder binding):
```powershell
docker run -it --rm `
  --name wos-countdown-bot `
  -v ${PWD}/config.json:/app/config.json `
  -p 127.0.0.1:5544:5544 `
  deathmarcher/wos-countdown-bot:latest
```

---

### **Release Tags**  
If you want to run a specific release version, replace `latest` with the release tag (e.g., `v1.0.0`).

#### **Linux/macOS** (With `sound-clips` folder binding):
```sh
docker run -it --rm \
  --name wos-countdown-bot \
  -v $(pwd)/config.json:/app/config.json \
  -v $(pwd)/sound-clips:/app/sound-clips \
  -p 127.0.0.1:5544:5544 \
  deathmarcher/wos-countdown-bot:v1.0.0
```

#### **Windows PowerShell** (With `sound-clips` folder binding):
```powershell
docker run -it --rm `
  --name wos-countdown-bot `
  -v ${PWD}/config.json:/app/config.json `
  -v ${PWD}/sound-clips:/app/sound-clips `
  -p 127.0.0.1:5544:5544 `
  deathmarcher/wos-countdown-bot:v1.0.0
```

---

## 🎮 **Using the Bot**
### 🖥️ **Posting Controls in a Channel**
Use the following **slash command** in Discord:
```sh
/postcontrols
```
If you don’t see the command, **restart Discord**.



### 🕹️ **Web Interface**
The bot starts a **web server** on:
- **URL**: `http://127.0.0.1:5544/`

It has three views (top left):
- **Servers** – Select a server, join/leave a voice channel, play/stop any sound.
- **Logs** – Live log stream with category filter.
- **Rally Tracker** – Plan & run chained countdowns used for reinforcements.

#### Rally Tracker
1) **March Times** – build a list of players and their march time (in seconds).
   - Add / Edit / Delete players.
   - Fine-tune with **±1s** buttons.

2) **Rallies**
   - Pick the **Rally Starter** (one of the players you added).
   - Enter the **Launch Time** (minutes / seconds) and press **Start Rally**.
   - A live card appears showing **Launch** and **Land** times; adjust launch with **±1s** or **Delete**.
   - **Stop Audio** stops the currently playing clip.  
     **Reset** clears all rallies and stops audio.

3) **Settings** (left side below “Add player”)
   - **Voice pack** – choose the `name-language` prefix of your files (e.g. `countdown-en`).  
     Files must be named:  
     `name-language-START-END.mp3` (e.g. `countdown-en-50-0.mp3`, `countdown-en-30-0.mp3`).
   - **First call second** – the second before land for the first audio (e.g., 55s/50s/45s). Options are derived from the chosen voice pack.
   - **First trigger lead (ms)** – timing offset for the first call (positive = earlier).
   - **Chain lead (ms)** – offset applied to every chained file after the first.
   - **Fallback tolerance (s)** – if an exact gap file doesn’t exist, use the next **lower** file within this window (e.g., 12s gap with 5s tolerance → use 10s).
   - Settings are saved in your browser (localStorage). Click **Save** after changes.

#### How the audio logic works
- When the first rally reaches the configured **First call second** (after applying the lead), the app plays  
  ``${voicePack}-${firstCallSecond}-0.mp3`` via the API.
- For each subsequent rally, the app automatically plays the best-matching **gap** file based on the time
  between land times (prefers exact match, otherwise the nearest lower within the fallback window).  
- A safety **gate** prevents the first call from re-triggering while any rally is already inside the first-call window.

#### Keyboard shortcuts
- **Tab** cycles `Starter → Minutes → Seconds → Starter`.
- **Enter** in Minutes/Seconds = **Start Rally**.
- Type **:**, **.** or **,** in Minutes to jump to Seconds.
- **Esc** stops audio.
- When tabbing into Minutes/Seconds the whole value is selected for quick overwrite.



---

## 🛑 **Known Issues**
- If **CPU performance is low**, countdowns may **go out of sync**. Consider running the bot on a **dedicated server**.
- The bot may disconnect randomly. This is a known issue with the `discord.py` library. It can be resolved by installing the latest development version from the Git repository: `pip3 install --no-cache-dir --upgrade "git+https://github.com/Rapptz/discord.py.git"`

---

## 🐞 **Found a Bug?**
This bot is still **new and under testing**.
- Ping **deathmarcher** on our [Discord Server](https://wosnerds.com/)
- Or **create an issue** on GitHub!

Happy Counting! 🎉

