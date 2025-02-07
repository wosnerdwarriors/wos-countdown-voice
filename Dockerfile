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
COPY . /app/

# Expose necessary ports (only needed if using the webserver)
EXPOSE 5544

# Command to run the bot (expects an external config.json)
CMD ["python", "main.py"]

