FROM mcr.microsoft.com/devcontainers/python:3.11

# Install desktop environment and noVNC dependencies
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    xvfb \
    fluxbox \
    x11vnc \
    novnc \
    python3-pip \
    python3-setuptools \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    # Clean up
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Setup start script for VNC
USER vscode
WORKDIR /home/vscode

# Copy source code
COPY . .

# Environment variables for Display
ENV DISPLAY=:0
ENV SCREEN_WIDTH=1280
ENV SCREEN_HEIGHT=720

# Command to start desktop services and then dummy process
CMD ["sh", "-c", "Xvfb :0 -screen 0 ${SCREEN_WIDTH}x${SCREEN_HEIGHT}x24 & fluxbox & x11vnc -display :0 -forever -nopw -listen localhost -xkb & /usr/share/novnc/utils/launch.sh --vnc localhost:5900 --listen 6080"]
