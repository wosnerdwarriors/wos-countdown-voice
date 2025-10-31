# Use an official Python runtime as a parent image
FROM python:3.11-slim
ENV RUNNING_IN_DOCKER=true

# Set the working directory inside the container
WORKDIR /app

# Install debugging and networking tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    net-tools \
    iproute2 \
    curl \
    procps \
    lsof \
    dnsutils \
    iputils-ping \
    tcpdump \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for better caching
COPY requirements.txt /app/

# Install dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy the bot files to the container (excluding config.json)
# Copy only the application files we need. Be explicit rather than "COPY ." to
# avoid accidentally including secrets or other artifacts in the image.
COPY ["requirements.txt", "main.py", "web_server.py", "discord_bot.py", "rally_audio.py", "rally_store.py", "generate-countdown.py", "generate-tts-mp3-general.py", "config_enums.py", "rally_audio_config.json", "README.md", "/app/"] /app/
# Copy directories (templates, static UI, sound clips). These must exist in the
# repository root. Adjust as needed if you add/remove folders.
COPY rallytracker/ /app/rallytracker/
COPY templates/ /app/templates/
COPY sound-clips/ /app/sound-clips/

# Expose necessary ports (only needed if using the webserver)
EXPOSE 5544

# Command to run the bot (expects an external config.json)
CMD ["python", "main.py"]

