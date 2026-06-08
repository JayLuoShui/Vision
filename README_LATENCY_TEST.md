# Qwen3-Coder LAN Latency Test

## Overview
This guide explains how to test the latency of Qwen3-Coder models in a LAN environment, particularly for systems with limited VRAM (e.g. RTX 4050 6GB).

## Prerequisites
1. **Ollama Server**: A machine running Ollama with Qwen3-Coder models installed (e.g., `qwen3-coder:30b-a3b`)
2. **Network Access**: Both machines must be on the same LAN
3. **Python Environment**: Python 3.7+

## Setup Instructions

### 1. Install Ollama on the Server Machine
```bash
# On the server (with sufficient VRAM)
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Pull Qwen3-Coder Model on Server
```bash
# On the server machine
ollama pull qwen3-coder:30b-a3b
```

### 3. Configure Ollama Server to Accept Remote Connections
Edit `/etc/ollama/ollama.env` (Linux) or equivalent:
```ini
OLLAMA_HOST=0.0.0.0
OLLAMA_PORT=11434
```

Restart Ollama service:
```bash
sudo systemctl restart ollama
```

### 4. Run Latency Tests
From your local machine (RTX 4050 6GB):
```bash
python test_model_speed.py
```

## Expected Results
The script will test three prompt types:
1. **轻量(短)**: Short code generation
2. **中等**: Medium complexity explanation
3. **重度(长)**: Long-form detailed explanation

Results show:
- Token count processed
- Time taken (seconds)
- Tokens per second (tok/s) speed

## Optimization Tips
1. **For RTX 4050 (6GB)**: Use quantized models (AWQ/GGUF) or offload to LAN
2. **For LAN-based inference**: Configure Ollama for remote access
3. **For faster response times**: Reduce prompt length or use lower temperature

## Troubleshooting
1. **Connection refused**: Check firewall settings and Ollama server status
2. **Model not found**: Verify model name matches what's pulled on the server
3. **Slow performance**: Consider quantization or switching to a larger VRAM machine

## Configuration Notes
- Default server addresses: `localhost:11434`, `192.168.10.100:11434`
- Model selection prioritizes Qwen3-Coder variants
- Uses temperature=0.1 for consistent, fast generation