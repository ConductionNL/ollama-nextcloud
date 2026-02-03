# Ollama Nextcloud ExApp
# Combines Ollama LLM server with AppAPI lifecycle management

FROM ollama/ollama:latest

# Install Python for the AppAPI wrapper
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir -r /app/requirements.txt

# Install FRP client for HaRP support
RUN set -ex; \
    ARCH=$(uname -m); \
    if [ "$ARCH" = "aarch64" ]; then \
      FRP_URL="https://raw.githubusercontent.com/nextcloud/HaRP/main/exapps_dev/frp_0.61.1_linux_arm64.tar.gz"; \
      FRP_DIR="frp_0.61.1_linux_arm64"; \
    else \
      FRP_URL="https://raw.githubusercontent.com/nextcloud/HaRP/main/exapps_dev/frp_0.61.1_linux_amd64.tar.gz"; \
      FRP_DIR="frp_0.61.1_linux_amd64"; \
    fi; \
    curl -L "$FRP_URL" -o /tmp/frp.tar.gz; \
    tar -C /tmp -xzf /tmp/frp.tar.gz; \
    cp /tmp/${FRP_DIR}/frpc /usr/local/bin/frpc; \
    chmod +x /usr/local/bin/frpc; \
    rm -rf /tmp/frp* /tmp/${FRP_DIR}

# Copy ExApp wrapper
COPY ex_app /app/ex_app

# Create data directory
RUN mkdir -p /data

WORKDIR /app

# Expose ports
EXPOSE 9000 11434

# Environment defaults
ENV APP_HOST=0.0.0.0
ENV APP_PORT=9000
ENV PYTHONUNBUFFERED=1
ENV OLLAMA_HOST=0.0.0.0:11434

# Entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
