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
from src.services.storage import get_storage
import time
import json
import os
import uuid
from flask import Flask

# Directory where final output videos are stored (served by main.py /final route)
FINAL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'final')


def write_voice_wav(wav_bytes, prefix='voice', work_dir=None):
    """Persist synthesized WAV bytes into the shared work/ dir.

    Returns the file path. Location matches where advanced_tts_service writes
    Kokoro output (money_weaver_backend/work), so the MOSS 24kHz WAV slots into
    the assembly pipeline interchangeably with Kokoro.
    """
    if not wav_bytes:
        return None
    work_dir = work_dir or advanced_tts_service.working_dir
    os.makedirs(work_dir, exist_ok=True)
    path = os.path.join(work_dir, f'{prefix}_{uuid.uuid4().hex}.wav')
    with open(path, 'wb') as fh:
        fh.write(wav_bytes)
    return path

def find_task_record(task_id, project_id, task_type):
    """Find the DB task record for a Celery task, tolerating the dispatch race.

    Routes commit the Task row (pending) before .delay(), then update
    celery_task_id after dispatch returns. A fast worker may start before that
    second commit, so the celery_task_id lookup can miss; retry briefly, then
    fall back to the newest pending task for the project.
    """
    for _ in range(10):
        task_record = Task.query.filter_by(celery_task_id=task_id).first()
        if task_record:
            return task_record
        time.sleep(0.1)
    return (
        Task.query
        .filter_by(project_id=project_id, task_type=task_type, status='pending')
        .order_by(Task.id.desc())
        .first()
    )

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
def generate_assembler_video_task(self, project_id, prompt, duration=30, orientation="landscape", width=1920, height=1080, voice_id=None, model=None, niche_id=None):
    """
    Generate video using the assembler workflow (stock footage + TTS).

    When voice_id is provided and names a Voice the project owner owns, the
    narration is synthesized through the MOSS-TTS real voice-cloning service.
    On ANY failure (service down, voice missing, bad reference) we fall back to
    the Kokoro voice so video generation never hard-fails because TTS is down.
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
            task_record = find_task_record(task_id, project_id, 'assembler_video_generation')
            
            # Get default model
            default_model = get_default_model()
            print(f"Default model: {default_model}")
                
            # Update task record in database
            if task_record:
                task_record.status = 'running'
                task_record.progress = 10
                task_record.generation_type = 'assembler'
                db.session.commit()
                
            # Update task status for Celery progress tracking
            self.update_state(state='PROGRESS', meta={'current': 10, 'total': 100, 'status': 'Generating script...'})
            script = llm_service.generate_script(prompt, user_id, model=model or default_model, duration=duration, niche_id=niche_id)
            
            # Parse the script for structured data
            parsed_script = script_parsing_service.parse_script(script)
            
            # Update project with generated script
            project.script = script
            db.session.commit()
            
            # Update task record in database
            if task_record:
                task_record.progress = 20
                task_record.generation_type = 'assembler'
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
            
            # Try voice cloning first when the owner supplied a Voice id.
            # Real cloning only runs for a Voice the project owner owns.
            audio_file = None
            if voice_id:
                try:
                    from src.models.voice import Voice
                    from src.services.tts_client import synthesize
                    from src.services.storage import resolve_reference_for_tts
                    voice_model = Voice.query.filter_by(id=voice_id, user_id=user_id).first()
                    ref = resolve_reference_for_tts(voice_model.reference_audio_url) if voice_model else None
                    if ref and (os.path.isfile(ref) or ref.startswith(('http://', 'https://'))):
                        wav_bytes = synthesize(
                            voiceover_text,
                            ref,
                            voice_id=str(voice_model.id),
                        )
                        audio_file = write_voice_wav(wav_bytes, prefix=f'voice_{voice_model.id}')
                    else:
                        print(f"Voice {voice_id} not found / not owned by user {user_id} / reference missing; falling back to Kokoro")
                except Exception as e:
                    print(f"MOSS-TTS unavailable, falling back to Kokoro for voice_id={voice_id}: {e}")
                    audio_file = None

            # Fallback: Kokoro (or basic TTS) keeps video generation working
            if not audio_file:
                audio_file = advanced_tts_service.generate_tts(voiceover_text, model_type="kokoro", voice=voice)
                if not audio_file:
                    # Fallback to original TTS service
                    audio_file = tts_service.generate_tts(voiceover_text)
            
            if not audio_file:
                raise Exception("Failed to generate voiceover")
            
            # Update task record in database
            if task_record:
                task_record.progress = 40
                task_record.generation_type = 'assembler'
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
                task_record.generation_type = 'assembler'
                db.session.commit()

            # Upload final video + thumbnail to storage (durable keys, served as
            # expiring presigned URLs on read). Local files stay in final/ during
            # dev; production may delete them after a successful upload. task_record
            # may be None (dispatch race) — skip the upload and keep /final URLs.
            storage = get_storage()
            key_video = f'videos/{project.user_id}/{project_id}/{task_record.id}.mp4' if task_record else None
            key_thumb = f'thumbs/{project.user_id}/{project_id}/{task_record.id}.jpg' if task_record else None
            video_uploaded = False
            thumb_uploaded = False
            if task_record:
                try:
                    with open(final_video_path, 'rb') as f:
                        storage.put_object(key_video, f.read(), 'video/mp4')
                    video_uploaded = True
                    if thumbnail_path:
                        with open(thumbnail_path, 'rb') as f:
                            storage.put_object(key_thumb, f.read(), 'image/jpeg')
                        thumb_uploaded = True
                except Exception as e:
                    print(f"Storage upload failed, falling back to /final URLs: {e}")

            # Final result
            result = {
                'video_url': key_video if video_uploaded else f'/final/{output_filename}',
                'thumbnail_url': key_thumb if thumb_uploaded else (f'/final/{os.path.basename(thumbnail_path)}' if thumbnail_path else None),
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
                task_record.generation_type = 'assembler'
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
                task_record = find_task_record(self.request.id, project_id, 'assembler_video_generation')
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
def generate_generative_video_task(self, project_id, prompt, voice_id=None):
    """
    Generate video using the generative workflow (ComfyUI).

    voice_id is accepted for parity with the assembler task. This workflow has
    no narration/audio stage (ComfyUI image/video generation only), so the id
    is validated for ownership and recorded, but no speech is synthesized here.
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
            task_record = find_task_record(self.request.id, project_id, 'generative_video_generation')
            if task_record:
                task_record.status = 'running'
                task_record.progress = 10
                db.session.commit()

            # Validate an optional owner-scoped voice id (no audio stage here)
            if voice_id is not None:
                try:
                    from src.models.voice import Voice
                    voice_model = Voice.query.filter_by(id=voice_id, user_id=project.user_id).first()
                    if voice_model:
                        print(f"Generative task using voice {voice_model.id} ({voice_model.name})")
                    else:
                        print(f"Voice {voice_id} not found / not owned by user {project.user_id}; generative workflow has no narration stage, ignoring")
                except Exception as e:
                    print(f"Could not resolve voice {voice_id}: {e}")

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
                task_record.progress = 80
                task_record.generation_type = 'assembler'
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
                task_record = find_task_record(self.request.id, project_id, 'generative_video_generation')
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
            task_record = find_task_record(self.request.id, project_id, 'batch_mix_generation')
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
                task_record = find_task_record(self.request.id, project_id, 'batch_mix_generation')
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

            # Real zero-shot cloning via MOSS-TTS; fall back to the Kokoro
            # default when the service is down so this never hard-fails.
            from src.services.tts_client import synthesize
            try:
                wav_bytes = synthesize(text, reference_audio_path)
                audio_file = write_voice_wav(wav_bytes, prefix='clone')
            except Exception as e:
                print(f"MOSS-TTS unavailable, falling back to Kokoro default for clone: {e}")
                audio_file = advanced_tts_service.generate_tts(text, model_type="kokoro", voice='af_heart')

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
            task_record = find_task_record(self.request.id, project_id, 'voice_cloning')
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
                task_record = find_task_record(self.request.id, project_id, 'voice_cloning')
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