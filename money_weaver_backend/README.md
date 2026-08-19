# MoneyWeaver Backend - Enhanced Video Generation

This repository contains the enhanced backend for the MoneyWeaver video generation platform with improved script parsing, video duration checking, and shot timing alignment.

## Improvements Made

### 1. Enhanced Script Parsing Service
- Created a dedicated `script_parsing_service.py` to handle structured parsing of AI-generated scripts
- Improved regex patterns for accurate extraction of titles, scenes, visual descriptions, and voiceover text
- Added fallback parsing methods for handling various script formats

### 2. Improved Prompt Template
- Updated the LLM prompt in `llm_service.py` to request more structured output
- Specified exact format requirements for scene descriptions, timing, and voiceover text
- Added clear examples to guide the AI in generating properly formatted scripts

### 3. Video Duration Checking
- Added `get_video_duration()` method to `stock_footage_service.py` using OpenCV
- Enhanced stock footage search to return video files with duration information
- Added proper error handling for video processing operations

### 4. Video Cutting and Assembly
- Implemented `cut_video_segment()` method in `assembly_service.py` to cut videos to specific durations
- Enhanced the video assembly process to match scene timings with actual video durations
- Added cleanup functionality to remove temporary files after processing

### 5. Better Integration Between Services
- Updated TTS service to use the new parsing service for clean voiceover extraction
- Modified stock footage service to accept parsed scenes for more targeted searches
- Enhanced video assembly service to work with timed scenes and cut videos appropriately

## Key Features

- **Structured Script Parsing**: Accurately extracts titles, scenes, visual descriptions, and voiceover text from AI-generated scripts
- **Shot Matching**: Searches for stock footage based on detailed visual descriptions
- **Duration Alignment**: Automatically cuts video clips to match scene timings
- **Quality Control**: Checks video resolutions and ensures HD quality footage (1280x720 or higher)
- **Error Handling**: Robust error handling throughout the video generation pipeline

## API Endpoints

The backend provides the same API endpoints as before:
- `/api/generate/assembler` - Generate video using stock footage and TTS
- `/api/generate/generative` - Generate video using generative AI (ComfyUI)
- `/api/batch-mix` - Generate multiple video variations
- `/api/task-status/<task_id>` - Check status of video generation tasks

## Running the Backend

FastAPI app served by uvicorn (port 5004):

```bash
cd money_weaver_backend && source venv/bin/activate
python run.py
```

Or via `./start_all_services.sh` (activates `venv`, then starts LiteLLM proxy, Celery worker, and the FastAPI backend with `python run.py`). Stop with `./stop_all_services.sh`.

Database migrations (Alembic):

```bash
cd money_weaver_backend && source venv/bin/activate
python -m alembic upgrade head
```

## Testing

Run the pytest suite from `money_weaver_backend/` (use `venv` — `venv312` is broken):
```bash
source venv/bin/activate && python -m pytest
```
220 tests pass with 56.90% whole-suite coverage (enforced `--cov-fail-under=55`). Tests use a fresh temp SQLite DB (via `tests/conftest.py`) and mock all external services.