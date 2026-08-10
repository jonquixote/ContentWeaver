# MoneyWeaver Project

This is the complete MoneyWeaver project with a video generation platform that combines stock footage with AI-generated scripts.

## Project Structure

- `money_weaver_backend/` - Flask backend with video generation pipeline
- `money_weaver_frontend/` - React frontend dashboard
- `tests/` - Test files and scripts
- `video_env/` - Virtual environment for video processing

## Key Features

### Backend (money_weaver_backend/)
- Flask REST API for project management
- User authentication and authorization
- Video script generation using AI (Groq/Llama)
- Stock video integration (Pexels, Pixabay)
- Background task processing with Celery
- SQLite database for persistent storage

### Frontend (money_weaver_frontend/)
- React dashboard for managing projects
- Video preview and playback
- Project creation and editing interface
- User authentication flows

## Setup Instructions

### Prerequisites
1. Python 3.13+
2. Node.js 16+
3. Redis server
4. FFmpeg

### Backend Setup
```bash
cd money_weaver_backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Frontend Setup
```bash
cd money_weaver_frontend
npm install
```

### Environment Variables
Create a `.env` file in `money_weaver_backend/` with:
```
DATABASE_URL=sqlite:///src/database/app.db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key
GROQ_API_KEY=your-groq-api-key
PEXELS_API_KEY=your-pexels-api-key
PIXABAY_API_KEY=your-pixabay-api-key
```

### Starting Services
1. Start Redis: `redis-server`
2. Start Celery worker: `cd money_weaver_backend && celery -A src.services.celery_app.celery_app worker --loglevel=info`
3. Start Flask backend: `cd money_weaver_backend && python src/main.py`
4. Start frontend: `cd money_weaver_frontend && npm run dev`

## Testing
Test files are organized in the `tests/` directory:
```bash
cd tests
python test_assembler_pipeline.py
```

## Current Status

✅ Database configuration working correctly
✅ User authentication functional
✅ Project ownership enforced
✅ Video script generation working
✅ Stock video downloading functional
✅ Background task processing with Celery
✅ API endpoints functional
✅ Frontend dashboard operational

The video assembler pipeline is fully operational and can generate complete videos using AI prompts.