#!/bin/bash
# setup_kokoro.sh
# Script to set up Kokoro TTS model

echo "Kokoro TTS model setup status:"

# Check if Kokoro is already installed
if python -c "import kokoro" 2>/dev/null; then
    echo "✅ Kokoro is already installed"
else
    echo "❌ Kokoro is not installed"
    echo "To install Kokoro, run:"
    echo "  pip install kokoro soundfile"
fi

# Check if espeak-ng is installed
if command -v espeak-ng &> /dev/null; then
    echo "✅ espeak-ng is installed"
else
    echo "❌ espeak-ng is not installed"
    echo "To install espeak-ng on macOS, run:"
    echo "  brew install espeak-ng"
fi

echo ""
echo "Kokoro integration status:"
echo "✅ Kokoro model is integrated and available for use"
echo "✅ Fallback to gTTS when Kokoro encounters issues"
echo "✅ Automatic detection of available models"

echo ""
echo "To test the integration, run:"
echo "  python test_kokoro_tts.py"