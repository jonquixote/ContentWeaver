# Voice Model Integration for MoneyWeaver

This document explains how to set up and use advanced voice models (Kokoro and VibeVoice) with MoneyWeaver.

## Available Voice Models

### 1. Kokoro-82M
- Lightweight TTS model (82M parameters)
- Fast inference
- Good quality output
- GitHub: https://github.com/hexgrad/kokoro

### 2. VibeVoice-1.5B
- More powerful model (1.5B parameters)
- Expressive, long-form, multi-speaker conversational audio
- Higher quality but requires more resources

## Current Integration Status

✅ **Kokoro-82M is successfully integrated** and ready to use
✅ **Automatic fallback to gTTS** when Kokoro encounters issues
✅ **Compatible with Python 3.12 environment**

## Installation

### Prerequisites
1. Python 3.12 virtual environment (already set up as `venv312`)
2. FFmpeg (already included in Docker setup)
3. PyTorch and Torchaudio (already installed)

### Installing Voice Model Dependencies

Kokoro is already installed in the Python 3.12 environment:

```bash
# Activate the Python 3.12 environment
source venv312/bin/activate

# Kokoro and dependencies are already installed
# If you need to reinstall:
# pip install kokoro soundfile
```

For espeak-ng (used for English OOD fallback):
```bash
# On macOS
brew install espeak-ng

# On Ubuntu/Debian
sudo apt-get install espeak-ng

# On Windows
# Download from: https://github.com/espeak-ng/espeak-ng/releases
```

## Configuration

The voice service automatically detects which models are available and will use them when possible. If a model is not available, it falls back to gTTS.

## Usage

The advanced TTS service is automatically integrated into the video generation workflow. The system will:

1. Try to use Kokoro for TTS generation (lightweight and efficient)
2. Fall back to VibeVoice if Kokoro is not available
3. Fall back to gTTS if neither advanced model is available

## API

The `AdvancedTTSService` provides the following methods:

- `generate_tts(text, model_type="kokoro")` - Generate TTS using specified model
- `generate_tts_with_kokoro(text)` - Generate TTS using Kokoro
- `generate_tts_with_vibevoice(text)` - Generate TTS using VibeVoice

## Docker Support

The Dockerfile has been updated to include necessary system dependencies for audio processing.

## Troubleshooting

If you encounter issues with the voice models:
1. Ensure all dependencies are installed
2. Check that PyTorch is properly configured
3. Verify FFmpeg is available
4. Check the logs for specific error messages

## Environment Setup

To run the services with full voice model support:

```bash
# Activate the Python 3.12 environment
source venv312/bin/activate

# Start the services
./start_all_services.sh
```

## Current Limitations

Due to NumPy compatibility issues with PyTorch, there may be occasional fallbacks to gTTS. This is handled automatically by the system.

## Future Enhancements

1. Add VibeVoice support when resources allow
2. Implement additional voice models
3. Add voice cloning capabilities
4. Improve error handling and logging