from src.services.celery_app import celery_app
from src.models.project import Project
from src.models.task import Task
from src.database import db
from src.services.llm_service import llm_service
from src.services.video.stock_footage_service import stock_service
from src.services.video.tts_service import tts_service
from src.services.video.advanced_tts_service import advanced_tts_service
from src.services.video.assembly_service import assembly_service, generate_thumbnail
from src.services.script_parsing_service import script_parsing_service
import time
import json
import os
from flask import Flask

# Directory where final output videos are stored (served by main.py /final route)
FINAL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'final')

def create_app_context():
    """Create Flask app context for database operations"""
    print("Creating app context...")
    app = Flask(__name__)
    
    # Database configuration (same as in main.py)
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database', 'app.db'))
    print(f"Database path: {db_path}")
    # Ensure the database directory exists BEFORE initializing the database
    db_dir = os.path.dirname(db_path)
    os.makedirs(db_dir, exist_ok=True)
    # Ensure the database directory has write permissions
    os.chmod(db_dir, 0o777)
    
    # If database file exists, ensure it has write permissions
    if os.path.exists(db_path):
        os.chmod(db_path, 0o666)  # Read/write for owner, group, and others
    else:
        # Create an empty database file with proper permissions
        with open(db_path, 'w') as f:
            pass
        os.chmod(db_path, 0o666)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', f"sqlite:///{db_path}")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database with app
    print("Initializing database...")
    from src.database import db
    db.init_app(app)
    
    with app.app_context():
        print("Inside app context, importing models...")
        # Import models here to ensure they're registered with SQLAlchemy
        from src.models.user import User
        from src.models.project import Project
        from src.models.task import Task
        from src.models.media_asset import MediaAsset
        from src.models.api_key import ApiKey
        
        print("Creating tables...")
        # Create tables if they don't exist
        db.create_all()

        # Lightweight migrations for columns added after initial creation
        from sqlalchemy import inspect as _inspect, text as _text
        _cols = [c['name'] for c in _inspect(db.engine).get_columns('task')]
        if 'thumbnail_path' not in _cols:
            with db.engine.connect() as _conn:
                _conn.execute(_text("ALTER TABLE task ADD COLUMN thumbnail_path VARCHAR(500)"))
                _conn.commit()
        
        # Debug: Print out what tables were created
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"Database tables: {tables}")
    
    print("App context created successfully")
    return app

def get_default_model():
    """Get the default model from settings or use a fallback"""
    # In a real implementation, this would fetch from a settings table
    # For now, we'll use the updated default model
    return "groq/llama-3.3-70b-versatile"

@celery_app.task(bind=True, name='src.tasks.video_tasks.generate_assembler_video_task')
def generate_assembler_video_task(self, project_id, prompt, duration=30, orientation="landscape", width=1920, height=1080):
    """
    Generate video using the assembler workflow (stock footage + TTS)
    """
    print(f"Starting generate_assembler_video_task with project_id: {project_id}")
    
    # Create application context
    app = create_app_context()
    
    with app.app_context():
        try:
            print("Inside app context")
            # Update task status
            task_id = self.request.id
            print(f"Task ID: {task_id}")
            
            # Get project to identify user and associated task
            print(f"Getting project with ID: {project_id}")
            project = db.session.get(Project, project_id)
            if not project:
                raise Exception("Project not found")
            print(f"Project found: {project.title}")
                
            # Store user_id before any operations that might trigger lazy loading
            user_id = project.user_id
            print(f"User ID: {user_id}")
            
            # Find the associated task record in the database
            task_record = Task.query.filter_by(celery_task_id=task_id).first()
            
            # Get default model
            default_model = get_default_model()
            print(f"Default model: {default_model}")
                
            # Update task record in database
            if task_record:
                task_record.status = 'running'
                task_record.progress = 10
                db.session.commit()
                
            # Update task status for Celery progress tracking
            self.update_state(state='PROGRESS', meta={'current': 10, 'total': 100, 'status': 'Generating script...'})
            script = llm_service.generate_script(prompt, user_id, default_model, duration)
            
            # Parse the script for structured data
            parsed_script = script_parsing_service.parse_script(script)
            
            # Update project with generated script
            project.script = script
            db.session.commit()
            
            # Update task record in database
            if task_record:
                task_record.progress = 20
                db.session.commit()
                
            # Generate TTS from parsed voiceover text, not the full script
            self.update_state(state='PROGRESS', meta={'current': 20, 'total': 100, 'status': 'Generating voiceover...'})
            # Extract clean voiceover text from parsed script
            voiceover_text = script_parsing_service.extract_voiceover_text(parsed_script)
            
            # Determine voice based on project settings (default to af_heart_female)
            voice = 'af_heart'
            if hasattr(project, 'voice_type'):
                voice_type = project.voice_type
                if voice_type == 'male':
                    voice = 'af_heart_male'
                elif voice_type == 'female':
                    voice = 'af_heart'
                elif voice_type == 'af_warm':
                    voice = 'af_warm'
                elif voice_type == 'af_cool':
                    voice = 'af_cool'
                elif voice_type == 'af_warm_male':
                    voice = 'af_warm_male'
                elif voice_type == 'af_cool_male':
                    voice = 'af_cool_male'
                elif voice_type == 'neutral':
                    voice = 'af_heart'  # Default to af_heart for neutral
                else:
                    # If it's already a specific voice name, use it directly
                    voice = voice_type
            
            # Try advanced TTS first, fallback to basic TTS
            audio_file = advanced_tts_service.generate_tts(voiceover_text, model_type="kokoro", voice=voice)
            if not audio_file:
                # Fallback to original TTS service
                audio_file = tts_service.generate_tts(voiceover_text)
            
            if not audio_file:
                raise Exception("Failed to generate voiceover")
            
            # Update task record in database
            if task_record:
                task_record.progress = 40
                db.session.commit()
                
            # Search for stock footage based on script with duration information and resolution settings
            self.update_state(state='PROGRESS', meta={'current': 40, 'total': 100, 'status': 'Searching for stock footage...'})
            
            # Get the target scene count from video settings
            from src.services.video.video_settings import VideoSettings
            video_settings = VideoSettings(duration=duration, orientation=orientation, width=width, height=height)
            target_scene_count = video_settings.get_scene_count()
            
            # Request more videos than scenes to ensure variety (aim for 1.5-2x the scene count)
            max_videos_needed = max(target_scene_count * 2, 8)  # At least 8 videos
            
            video_data = stock_service.get_stock_videos_for_script(
                script, 
                target_scenes=parsed_script.get('scenes', []), 
                max_videos=max_videos_needed,
                orientation=orientation,
                min_width=width,
                min_height=height
            )
            
            if not video_data:
                raise Exception("Failed to find relevant stock footage")
            
            # Update task record in database
            if task_record:
                task_record.progress = 80
                db.session.commit()
                
            # Assemble video with stock footage and audio, using scene timings
            self.update_state(state='PROGRESS', meta={'current': 80, 'total': 100, 'status': 'Assembling video...'})
            output_filename = f"project_{project_id}_assembler.mp4"
            
            final_video_path = assembly_service.assemble_video(
                video_files=video_data,  # Pass the full video data with metadata
                audio_file=audio_file,
                scene_timings=parsed_script.get('scenes', []),
                output_filename=output_filename,
                total_duration=duration,
                orientation=orientation,
                width=width,
                height=height
            )
            
            if not final_video_path:
                raise Exception("Failed to assemble final video")
            
            # Check if the video file actually exists
            if not os.path.exists(final_video_path):
                raise Exception(f"Video file was not created at {final_video_path}")

            # Generate thumbnail from the assembled video
            self.update_state(state='PROGRESS', meta={'current': 90, 'total': 100, 'status': 'Generating thumbnail...'})
            thumbnail_path = generate_thumbnail(final_video_path)
            if task_record:
                task_record.progress = 90
                task_record.thumbnail_path = thumbnail_path
                db.session.commit()

            # Final result
            result = {
                'video_url': f'/final/{output_filename}',
                'thumbnail_url': f'/final/{os.path.basename(thumbnail_path)}' if thumbnail_path else None,
                'script': script,
                'duration': duration,
                'resolution': f"{width}x{height}",
                'orientation': orientation,
                'status': 'completed'
            }
            
            # Update project with video URL and completed status
            project.video_url = result['video_url']
            project.status = 'completed'
            db.session.commit()
            
            # Update task record in database
            if task_record:
                task_record.status = 'completed'
                task_record.progress = 100
                task_record.result = json.dumps(result)
                db.session.commit()
            
            return {
                'current': 100,
                'total': 100,
                'status': 'Video generation completed!',
                'result': result
            }
            
        except Exception as exc:
            # Update task record and project status to failed
            try:
                db.session.rollback()
                task_record = Task.query.filter_by(celery_task_id=self.request.id).first()
                if task_record:
                    task_record.status = 'failed'
                    task_record.error_message = str(exc)
                    task_record.result = json.dumps({'error': str(exc), 'status': 'failed'})
                project = db.session.get(Project, project_id)
                if project:
                    project.status = 'failed'
                db.session.commit()
            except:
                pass  # Ignore errors in error handling
                
            # Re-raise so Celery marks the task as FAILURE
            raise exc

@celery_app.task(bind=True, name='src.tasks.video_tasks.generate_generative_video_task')
def generate_generative_video_task(self, project_id, prompt):
    """
    Generate video using the generative workflow (ComfyUI)
    """
    # Create application context
    app = create_app_context()
    
    with app.app_context():
        try:
            # Update task status
            task_id = self.request.id
            
            # Get project to identify user
            project = db.session.get(Project, project_id)
            if not project:
                raise Exception("Project not found")
                
            # Find the associated task record in the database
            task_record = Task.query.filter_by(celery_task_id=self.request.id).first()
            if task_record:
                task_record.status = 'running'
                task_record.progress = 10
                db.session.commit()
                
            # Get default model
            default_model = get_default_model()
                
            # Generate enhanced prompt using LLM
            self.update_state(state='PROGRESS', meta={'current': 10, 'total': 100, 'status': 'Enhancing prompt with AI...'})
            enhanced_prompt = llm_service.generate_script(
                f"Enhance this video generation prompt to be more detailed and creative: {prompt}", 
                project.user_id,
                default_model
            )
            
            # Update project with enhanced prompt
            project.script = enhanced_prompt
            db.session.commit()

            # Update task record in database
            if task_record:
                task_record.progress = 30
                db.session.commit()
            
            # Simulate ComfyUI workflow construction
            self.update_state(state='PROGRESS', meta={'current': 20, 'total': 100, 'status': 'Constructing ComfyUI workflow...'})
            time.sleep(1)
            
            # Simulate ComfyUI job submission
            self.update_state(state='PROGRESS', meta={'current': 30, 'total': 100, 'status': 'Submitting to ComfyUI...'})
            time.sleep(2)
            
            # Simulate generative video creation (this would be much longer in reality)
            self.update_state(state='PROGRESS', meta={'current': 60, 'total': 100, 'status': 'Generating video with AI models...'})
            time.sleep(5)  # Simulate long AI processing
            
            # Simulate post-processing
            self.update_state(state='PROGRESS', meta={'current': 80, 'total': 100, 'status': 'Post-processing video...'})
            time.sleep(2)
            
            # Update task record in database
            if task_record:
                task_record.progress = 80
                db.session.commit()
            
            # Final result
            output_filename = f"project_{project_id}_generative.mp4"
            video_url = f'/final/{output_filename}' if os.path.exists(os.path.join(FINAL_DIR, output_filename)) else None
            result = {
                'video_url': video_url,
                'prompt': enhanced_prompt,
                'duration': 15,
                'model_used': 'Wan2.2',
                'status': 'completed'
            }
            
            # Update project with video URL and completed status
            project.video_url = result['video_url']
            project.status = 'completed'
            db.session.commit()
            
            # Update task record in database
            if task_record:
                task_record.status = 'completed'
                task_record.progress = 100
                task_record.result = json.dumps(result)
                db.session.commit()
            
            return {
                'current': 100,
                'total': 100,
                'status': 'Generative video completed!',
                'result': result
            }
            
        except Exception as exc:
            # Update task record and project status to failed
            try:
                db.session.rollback()
                task_record = Task.query.filter_by(celery_task_id=self.request.id).first()
                if task_record:
                    task_record.status = 'failed'
                    task_record.error_message = str(exc)
                    task_record.result = json.dumps({'error': str(exc), 'status': 'failed'})
                project = db.session.get(Project, project_id)
                if project:
                    project.status = 'failed'
                db.session.commit()
            except:
                pass  # Ignore errors in error handling
                
            # Re-raise so Celery marks the task as FAILURE
            raise exc

@celery_app.task(bind=True, name='src.tasks.video_tasks.batch_mix_videos_task')
def batch_mix_videos_task(self, project_id, variations):
    """
    Generate multiple video variations using batch mixing
    """
    # Create application context
    app = create_app_context()
    
    with app.app_context():
        try:
            total_variations = len(variations)
            
            # Find the associated task record in the database
            task_record = Task.query.filter_by(celery_task_id=self.request.id).first()
            if task_record:
                task_record.status = 'running'
                task_record.progress = 10
                db.session.commit()
            
            for i, variation in enumerate(variations):
                progress = int((i / total_variations) * 100)
                self.update_state(
                    state='PROGRESS', 
                    meta={
                        'current': progress, 
                        'total': 100, 
                        'status': f'Processing variation {i+1} of {total_variations}...'
                    }
                )
                if task_record:
                    task_record.progress = progress
                    db.session.commit()
                time.sleep(2)  # Simulate processing each variation
            
            # Final result
            video_urls = []
            for i in range(total_variations):
                variation_filename = f"project_{project_id}_variation_{i}.mp4"
                if os.path.exists(os.path.join(FINAL_DIR, variation_filename)):
                    video_urls.append(f'/final/{variation_filename}')
            result = {
                'variations_generated': total_variations,
                'video_urls': video_urls,
                'status': 'completed'
            }
            
            # Update task record in database
            if task_record:
                task_record.status = 'completed'
                task_record.progress = 100
                task_record.result = json.dumps(result)
                db.session.commit()
            
            # Update project with completed status and video URL
            project = db.session.get(Project, project_id)
            if project:
                project.status = 'completed'
                project.video_url = result['video_urls'][0] if result['video_urls'] else None
                db.session.commit()
            
            return {
                'current': 100,
                'total': 100,
                'status': f'Batch mixing completed! Generated {total_variations} variations.',
                'result': result
            }
            
        except Exception as exc:
            # Update task record status to failed
            try:
                db.session.rollback()
                task_record = Task.query.filter_by(celery_task_id=self.request.id).first()
                if task_record:
                    task_record.status = 'failed'
                    task_record.error_message = str(exc)
                    task_record.result = json.dumps({'error': str(exc), 'status': 'failed'})
                project = db.session.get(Project, project_id)
                if project:
                    project.status = 'failed'
                db.session.commit()
            except:
                pass  # Ignore errors in error handling

            # Re-raise so Celery marks the task as FAILURE
            raise exc


@celery_app.task(bind=True, name='src.tasks.video_tasks.clone_voice_task')
def clone_voice_task(self, reference_audio_path, text, project_id):
    """
    Clone a voice from reference audio and generate TTS with it
    """
    # Create application context
    app = create_app_context()
    
    with app.app_context():
        try:
            # Update task status
            self.update_state(state='PROGRESS', meta={'current': 10, 'total': 100, 'status': 'Processing reference audio...'})
            
            # Get project
            project = db.session.get(Project, project_id)
            if not project:
                raise Exception("Project not found")
                
            # Update task status
            self.update_state(state='PROGRESS', meta={'current': 30, 'total': 100, 'status': 'Cloning voice...'})
            
            # Use advanced TTS service to clone voice and generate audio
            from src.services.video.advanced_tts_service import advanced_tts_service
            audio_file = advanced_tts_service.clone_voice(reference_audio_path, text)
            
            if not audio_file:
                raise Exception("Failed to clone voice and generate audio")

            # Copy the generated audio into the served final/ directory
            import shutil
            os.makedirs(FINAL_DIR, exist_ok=True)
            final_audio_path = os.path.join(FINAL_DIR, os.path.basename(audio_file))
            if os.path.abspath(audio_file) != os.path.abspath(final_audio_path):
                shutil.copy2(audio_file, final_audio_path)
            audio_file = final_audio_path
                
            # Update task status
            self.update_state(state='PROGRESS', meta={'current': 80, 'total': 100, 'status': 'Saving cloned voice...'})
            
            # Update project with the generated audio
            project.video_url = f'/final/{os.path.basename(audio_file)}'
            project.status = 'completed'
            db.session.commit()
            
            # Final result
            result = {
                'audio_url': f'/final/{os.path.basename(audio_file)}',
                'status': 'completed'
            }
            
            # Update task record in database
            task_record = Task.query.filter_by(celery_task_id=self.request.id).first()
            if task_record:
                task_record.status = 'completed'
                task_record.progress = 100
                task_record.result = json.dumps(result)
                db.session.commit()
            
            return {
                'current': 100,
                'total': 100,
                'status': 'Voice cloning completed!',
                'result': result
            }
            
        except Exception as exc:
            # Update project and task record status to failed
            try:
                db.session.rollback()
                task_record = Task.query.filter_by(celery_task_id=self.request.id).first()
                if task_record:
                    task_record.status = 'failed'
                    task_record.error_message = str(exc)
                    task_record.result = json.dumps({'error': str(exc), 'status': 'failed'})
                project = db.session.get(Project, project_id)
                if project:
                    project.status = 'failed'
                db.session.commit()
            except:
                pass  # Ignore errors in error handling

            # Re-raise so Celery propagates a real FAILURE state
            raise exc