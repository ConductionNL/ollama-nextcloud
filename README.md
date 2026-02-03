# Ollama Nextcloud ExApp

A Nextcloud External Application (ExApp) that integrates [Ollama](https://ollama.ai) for local LLM inference directly into Nextcloud.

## Features

- **Run LLMs Locally** - Complete privacy with on-premise AI
- **GPU Acceleration** - Support for NVIDIA and AMD GPUs
- **Model Library** - Easy access to Llama, Mistral, CodeLlama, and more
- **OpenAI-compatible API** - Drop-in replacement for OpenAI endpoints
- **Efficient Memory Management** - Run large models with optimized memory usage

## Supported Models

| Model | Size | Use Case |
|-------|------|----------|
| llama3.2:1b | 1.3GB | Fast, lightweight tasks |
| llama3.2:3b | 2.0GB | Balanced performance |
| mistral:7b | 4.1GB | General purpose |
| codellama:7b | 3.8GB | Code generation |
| phi3:mini | 2.2GB | Efficient reasoning |

## Requirements

- Nextcloud 30 or higher
- [AppAPI](https://apps.nextcloud.com/apps/app_api) installed and configured
- Docker with a configured Deploy Daemon (HaRP recommended)
- 8GB+ RAM (16GB+ recommended for larger models)
- NVIDIA GPU with CUDA (optional, for acceleration)

## Installation

### Via Nextcloud App Store

1. Install and enable the **AppAPI** app in Nextcloud
2. Configure a Deploy Daemon with GPU support if available
3. Search for "Ollama" in the External Apps section
4. Click Install

### Manual Installation

```bash
# Register the ExApp with Nextcloud
occ app_api:app:register \
    ollama \
    <your-daemon-name> \
    --info-xml https://raw.githubusercontent.com/ConductionNL/ollama-nextcloud/main/appinfo/info.xml \
    --force-scopes
```

## Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `OLLAMA_DEFAULT_MODEL` | Model to pull on startup | llama3.2:3b |
| `OLLAMA_NUM_PARALLEL` | Concurrent inference requests | 2 |
| `OLLAMA_KEEP_ALIVE` | Model unload timeout | 15m |
| `OLLAMA_MAX_LOADED_MODELS` | Max models in memory | 1 |

## Usage

After installation, access the Ollama API through Nextcloud:

```bash
# List models
curl https://your-nextcloud/index.php/apps/app_api/proxy/ollama/api/tags

# Generate text
curl https://your-nextcloud/index.php/apps/app_api/proxy/ollama/api/generate \
    -d '{"model": "llama3.2", "prompt": "Hello!"}'

# Chat (OpenAI-compatible)
curl https://your-nextcloud/index.php/apps/app_api/proxy/ollama/v1/chat/completions \
    -d '{"model": "llama3.2", "messages": [{"role": "user", "content": "Hello!"}]}'
```

### Pulling New Models

Models can be pulled via the API:

```bash
curl -X POST https://your-nextcloud/index.php/apps/app_api/proxy/ollama/api/pull \
    -d '{"name": "mistral:7b"}'
```

## Development

### Building the Docker Image

```bash
docker build -t ollama-exapp:dev .
```

### Running Locally

```bash
docker run -it --rm \
    -e APP_ID=ollama \
    -e APP_SECRET=dev-secret \
    -e NEXTCLOUD_URL=http://localhost:8080 \
    -e OLLAMA_DEFAULT_MODEL=llama3.2:1b \
    -p 9000:9000 \
    -p 11434:11434 \
    --gpus all \
    ollama-exapp:dev
```

### Testing Endpoints

```bash
# Health check
curl http://localhost:9000/heartbeat

# List models
curl http://localhost:9000/api/tags

# Generate
curl http://localhost:9000/api/generate -d '{"model":"llama3.2:1b","prompt":"Hi"}'
```

## Architecture

```
┌─────────────────────────────────────┐
│         Nextcloud + AppAPI          │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│    Ollama ExApp Container           │
│  ┌───────────────────────────────┐  │
│  │  FastAPI Wrapper (port 9000)  │  │
│  │  - /heartbeat                 │  │
│  │  - /init                      │  │
│  │  - /enabled                   │  │
│  │  - /api/* (proxy to Ollama)   │  │
│  │  - /v1/* (OpenAI compat)      │  │
│  └───────────────┬───────────────┘  │
│                  │                  │
│  ┌───────────────▼───────────────┐  │
│  │  Ollama Server (port 11434)   │  │
│  │  ┌─────────────────────────┐  │  │
│  │  │    Model Storage        │  │  │
│  │  │    /data/models         │  │  │
│  │  └─────────────────────────┘  │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

## Integration with Open WebUI

This ExApp works seamlessly with the [Open WebUI ExApp](https://github.com/ConductionNL/open-webui-nextcloud) to provide a chat interface for your models.

## License

AGPL-3.0 - See [LICENSE](LICENSE) for details.

## Links

- [Ollama Documentation](https://ollama.ai)
- [Ollama Model Library](https://ollama.ai/library)
- [Nextcloud AppAPI Documentation](https://docs.nextcloud.com/server/stable/developer_manual/exapp_development/Introduction.html)
- [Conduction](https://conduction.nl)
