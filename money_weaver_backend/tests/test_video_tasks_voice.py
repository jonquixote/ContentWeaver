"""Unit tests for voice_id handling in video generation tasks (fallback behavior).

Mocked TTS / stock / assembly / LLM pipeline; real SQLite DB in a temp dir so
tasks run under a genuine Flask app context without touching app.db.
"""
import os
import shutil
import tempfile
import types
import unittest
from unittest import mock

os.environ.setdefault('SECRET_KEY', 'test-secret-key')

import src.tasks.video_tasks as vt
from src.database import db

FAKE_KOKORO_WAV = b'RIFF\x00kokoro-fallback-wav'
FAKE_CLONED_WAV = b'RIFF\x00moss-cloned-wav\x00'


class FakeTaskSelf:
    """Stand-in for the Celery task instance (no broker/backend required)."""

    def __init__(self, tid='fake-celery-id'):
        self.request = types.SimpleNamespace(id=tid)

    def update_state(self, *args, **kwargs):
        pass


def _invoke(task, *args, **kwargs):
    """Call a bind=True celery task body with a fake self."""
    return task.run.__func__(FakeTaskSelf(), *args, **kwargs)


def _build_app_context(tmpdir):
    """Create the shared temp DB and return (app, user_id, project_id, voice refs)."""
    os.environ['DATABASE_URL'] = f"sqlite:///{os.path.join(tmpdir, 'task.db')}"
    app = vt.create_app_context()
    ref_path = os.path.join(tmpdir, 'ref_sample.wav')
    with open(ref_path, 'wb') as fh:
        fh.write(FAKE_KOKORO_WAV)
    ref_path_missing = os.path.join(tmpdir, 'missing_ref.wav')
    user_id = project_id = voice_uid = other_voice_uid = None
    with app.app_context():
        from src.models.user import User
        from src.models.project import Project
        from src.models.voice import Voice
        db.create_all()
        owner = User(username='owner', email='o@t.com', password_hash='x')
        other = User(username='other', email='r@t.com', password_hash='y')
        db.session.add_all([owner, other])
        db.session.flush()
        project = Project(title='p', user_id=owner.id, voice_type='female', status='draft')
        db.session.add(project)
        db.session.flush()
        mine = Voice(user_id=owner.id, name='mine', reference_audio_url=ref_path,
                     consent_confirmed_at=__import__('datetime').datetime.utcnow())
        theirs = Voice(user_id=other.id, name='theirs', reference_audio_url=ref_path,
                       consent_confirmed_at=__import__('datetime').datetime.utcnow())
        orphan = Voice(user_id=owner.id, name='orphan', reference_audio_url=ref_path_missing, consent_confirmed_at=None)
        db.session.add_all([mine, theirs, orphan])
        db.session.commit()
        user_id, project_id = owner.id, project.id
        voice_uid, other_voice_uid = mine.id, theirs.id
    return app, user_id, project_id, voice_uid, other_voice_uid


class VideoTaskVoiceTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='mw-task-test-')
        self.workdir = os.path.join(self.tmpdir, 'work')
        os.makedirs(self.workdir, exist_ok=True)
        self.app, self.user_id, self.project_id, self.voice_id, self.other_voice_id = _build_app_context(self.tmpdir)

        self._orig_working_dir = vt.advanced_tts_service.working_dir
        vt.advanced_tts_service.working_dir = self.workdir

        self.fake_script = '# Title\n\nSome paragraph.\n'
        self.script_patchers = [
            mock.patch.object(vt, 'llm_service'),
            mock.patch.object(vt, 'script_parsing_service'),
        ]
        for p in self.script_patchers:
            p.start()
        vt.llm_service.generate_script.return_value = self.fake_script
        vt.script_parsing_service.parse_script.return_value = {'scenes': []}
        vt.script_parsing_service.extract_voiceover_text.return_value = 'voiceover narration text'

        self.pipeline_patchers = [
            mock.patch.object(vt, 'stock_service'),
            mock.patch.object(vt, 'assembly_service'),
        ]
        for p in self.pipeline_patchers:
            p.start()
        vt.stock_service.get_stock_videos_for_script.return_value = ['video_a.mp4', 'video_b.mp4']
        self.fake_out = os.path.join(self.tmpdir, 'out.mp4')
        with open(self.fake_out, 'wb') as fh:
            fh.write(b'\x00\x00\x00\x18ftypmp42')
        vt.assembly_service.assemble_video.return_value = self.fake_out
        self.thumb_mock = mock.patch.object(vt, 'generate_thumbnail', autospec=True)
        self.thumb_mock.start()
        vt.generate_thumbnail.return_value = os.path.join(self.tmpdir, 'thumb.jpg')

        self.kokoro_mock = mock.patch.object(vt.advanced_tts_service, 'generate_tts', autospec=True)
        self.kokoro_mock.start()
        self.fake_kokoro_wav = os.path.join(self.workdir, 'kokoro_fallback.wav')
        with open(self.fake_kokoro_wav, 'wb') as fh:
            fh.write(FAKE_KOKORO_WAV)
        vt.advanced_tts_service.generate_tts.return_value = self.fake_kokoro_wav
        self.tts_svc_mock = mock.patch.object(vt, 'tts_service')
        self.tts_svc_mock.start()

    def tearDown(self):
        for p in self.pipeline_patchers + self.script_patchers:
            p.stop()
        self.kokoro_mock.stop()
        self.tts_svc_mock.stop()
        self.thumb_mock.stop()
        vt.advanced_tts_service.working_dir = self._orig_working_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run_assembler(self, voice_id=None):
        return _invoke(
            vt.generate_assembler_video_task,
            project_id=self.project_id, prompt='a prompt', duration=15, voice_id=voice_id
        )

    def test_no_voice_id_uses_kokoro(self):
        result = self._run_assembler()
        self.assertEqual(result['status'], 'Video generation completed!')
        vt.advanced_tts_service.generate_tts.assert_called()
        vt.assembly_service.assemble_video.assert_called_once()
        assert_cfg = vt.assembly_service.assemble_video.call_args.kwargs['audio_file']
        self.assertEqual(assert_cfg, self.fake_kokoro_wav)

    def test_voice_id_clones_through_tts_client(self):
        with mock.patch('src.services.tts_client.synthesize', return_value=FAKE_CLONED_WAV) as synth:
            result = self._run_assembler(voice_id=self.voice_id)
        self.assertEqual(result['status'], 'Video generation completed!')
        synth.assert_called_once()
        self.assertEqual(synth.call_args[0][0], 'voiceover narration text')
        self.assertTrue(synth.call_args[0][1].endswith('ref_sample.wav'))
        self.assertEqual(synth.call_args.kwargs['voice_id'], str(self.voice_id))
        vt.advanced_tts_service.generate_tts.assert_not_called()
        audio = vt.assembly_service.assemble_video.call_args.kwargs['audio_file']
        self.assertIsInstance(audio, str)
        self.assertTrue(os.path.exists(audio))
        with open(audio, 'rb') as fh:
            self.assertEqual(fh.read(), FAKE_CLONED_WAV)

    def test_fallback_when_tts_service_down(self):
        with mock.patch('src.services.tts_client.synthesize',
                        side_effect=RuntimeError('connection refused')):
            result = self._run_assembler(voice_id=self.voice_id)
        self.assertEqual(result['status'], 'Video generation completed!')
        vt.advanced_tts_service.generate_tts.assert_called_once()
        vt.assembly_service.assemble_video.assert_called_once()
        audio = vt.assembly_service.assemble_video.call_args.kwargs['audio_file']
        self.assertEqual(audio, self.fake_kokoro_wav)

    def test_fallback_when_voice_not_owned(self):
        with mock.patch('src.services.tts_client.synthesize') as synth:
            result = self._run_assembler(voice_id=self.other_voice_id)
        self.assertEqual(result['status'], 'Video generation completed!')
        synth.assert_not_called()
        vt.advanced_tts_service.generate_tts.assert_called_once()

    def test_fallback_when_voice_missing(self):
        with mock.patch('src.services.tts_client.synthesize') as synth:
            result = self._run_assembler(voice_id=999999)
        self.assertEqual(result['status'], 'Video generation completed!')
        synth.assert_not_called()
        vt.advanced_tts_service.generate_tts.assert_called_once()

    def test_fallback_when_reference_file_gone(self):
        from src.models.voice import Voice
        orphan_id = None
        with self.app.app_context():
            orphan_id = Voice.query.filter_by(name='orphan').first().id
        with mock.patch('src.services.tts_client.synthesize') as synth:
            result = self._run_assembler(voice_id=orphan_id)
        self.assertEqual(result['status'], 'Video generation completed!')
        synth.assert_not_called()
        vt.advanced_tts_service.generate_tts.assert_called_once()

    def test_clone_voice_task_real_synthesis(self):
        from src.models.project import Project
        ref = os.path.join(self.tmpdir, 'ref_sample.wav')
        with mock.patch('src.services.tts_client.synthesize', return_value=FAKE_CLONED_WAV) as synth:
            with mock.patch.object(vt, 'FINAL_DIR', self.tmpdir):
                result = _invoke(vt.clone_voice_task, ref, 'clone line', self.project_id)
        self.assertEqual(result['status'], 'Voice cloning completed!')
        synth.assert_called_once()
        with self.app.app_context():
            project = db.session.get(Project, self.project_id)
            self.assertEqual(project.status, 'completed')
        self.assertIn('audio_url', result['result'])
        audio_path = result['result']['audio_url'].lstrip('/final/')
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir, audio_path)))

    def test_clone_voice_task_fallback_on_downtime(self):
        ref = os.path.join(self.tmpdir, 'ref_sample.wav')
        vt.advanced_tts_service.generate_tts.return_value = self.fake_kokoro_wav
        with mock.patch('src.services.tts_client.synthesize',
                        side_effect=RuntimeError('down')):
            with mock.patch.object(vt, 'FINAL_DIR', self.tmpdir):
                result = _invoke(vt.clone_voice_task, ref, 'clone line', self.project_id)
        self.assertEqual(result['status'], 'Voice cloning completed!')
        vt.advanced_tts_service.generate_tts.assert_called_once_with(
            'clone line', model_type='kokoro', voice='af_heart')


if __name__ == '__main__':
    unittest.main()