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
   - ✅ `**Presence Intentents**`
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
- The bot may disconnect randomly. This is a known issue with the `discord.py` library. It can be resolved by installing the latest development version from the Git repository: `pip3 install --no-cache-dir --upgrade "git+https://github.com/Rapptz/discord.py.git"`

---

## 🐞 **Found a Bug?**
This bot is still **new and under testing**.
- Ping **deathmarcher** on our [Discord Server](https://wosnerds.com/)
- Or **create an issue** on GitHub!

Happy Counting! 🎉

---

## 🧪 Automated Tests
Basic unit tests cover rally storage logic (players, rallies, events, arrival pattern, pet expiration, long-poll behavior).

### Run Tests
```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

### Isolated Data File
Tests use a temporary file path passed directly to `RallyStore(data_file=...)` so they do not touch the production `data.json`.

### Adding More Tests
Create additional files in `tests/` named `test_*.py`. For async logic, subclass `unittest.IsolatedAsyncioTestCase` like the existing examples.

### Forcing Flush (If Needed)
`await store.force_flush()` ensures buffered writes are persisted immediately when asserting file contents.


