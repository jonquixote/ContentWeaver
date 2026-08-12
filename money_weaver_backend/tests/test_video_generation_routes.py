"""Route tests: /api/generate/assembler and /api/generate/generative voice_id pass-through."""
import os
import shutil
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('SECRET_KEY', 'route-test-secret')

from flask import Flask

from src.database import db
from src.routes.video_generation import video_bp, _resolve_owned_voice


class VideoGenerationRouteTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='mw-route-test-')
        os.environ['DATABASE_URL'] = f"sqlite:///{os.path.join(self.tmpdir, 'route.db')}"
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(self.app)
        with self.app.app_context():
            from src.models.user import User
            from src.models.project import Project
            from src.models.voice import Voice
            db.create_all()
            self.owner = User(username='owner', email='owner@t.com', password_hash='x')
            self.other = User(username='other', email='other@t.com', password_hash='y')
            db.session.add_all([self.owner, self.other])
            db.session.flush()
            self.owner_id, self.other_id = self.owner.id, self.other.id
            ref = os.path.join(self.tmpdir, 'ref.wav')
            with open(ref, 'wb') as fh:
                fh.write(b'RIFF\x00ref')
            self.voice = Voice(user_id=self.owner_id, name='v', reference_audio_url=ref)
            db.session.add(self.voice)
            db.session.commit()
            self.voice_id = self.voice.id
        self.app.register_blueprint(video_bp, url_prefix='/api')
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _auth_headers(self, user_id):
        import jwt, datetime
        token = jwt.encode(
            {'user_id': user_id, 'jti': 'route-test', 'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)},
            os.environ['SECRET_KEY'], algorithm='HS256')
        return {'Authorization': f'Bearer {token}'}

    def _seed_project(self, owner_id):
        from src.models.project import Project
        with self.app.app_context():
            p = Project(title='p', user_id=owner_id, voice_type='female')
            db.session.add(p)
            db.session.commit()
            return p.id

    def test_assembler_passes_voice_id_to_task(self):
        pid = self._seed_project(self.owner_id)
        from src.tasks.video_tasks import generate_assembler_video_task
        with mock.patch.object(generate_assembler_video_task, 'delay', return_value=mock.Mock(id='c-1')) as delay:
            resp = self.client.post(
                '/api/generate/assembler',
                json={'project_id': pid, 'prompt': 'p', 'voice_id': self.voice_id},
                headers=self._auth_headers(self.owner_id),
            )
        self.assertEqual(resp.status_code, 202)
        delay.assert_called_once()
        _, kwargs = delay.call_args
        self.assertEqual(kwargs['voice_id'], self.voice_id)

    def test_assembler_rejects_unowned_voice(self):
        pid = self._seed_project(self.owner_id)
        resp = self.client.post(
            '/api/generate/assembler',
            json={'project_id': pid, 'prompt': 'p', 'voice_id': self.voice_id},
            headers=self._auth_headers(self.other_id),
        )
        self.assertEqual(resp.status_code, 403)

    def test_assembler_rejects_nonexistent_voice(self):
        pid = self._seed_project(self.owner_id)
        resp = self.client.post(
            '/api/generate/assembler',
            json={'project_id': pid, 'prompt': 'p', 'voice_id': 999999},
            headers=self._auth_headers(self.owner_id),
        )
        self.assertEqual(resp.status_code, 404)

    def test_assembler_rejects_non_integer_voice_id(self):
        pid = self._seed_project(self.owner_id)
        resp = self.client.post(
            '/api/generate/assembler',
            json={'project_id': pid, 'prompt': 'p', 'voice_id': 'abc'},
            headers=self._auth_headers(self.owner_id),
        )
        self.assertEqual(resp.status_code, 400)

    def test_generative_passes_voice_id_to_task(self):
        pid = self._seed_project(self.owner_id)
        from src.tasks.video_tasks import generate_generative_video_task
        with mock.patch.object(generate_generative_video_task, 'delay', return_value=mock.Mock(id='c-2')) as delay:
            resp = self.client.post(
                '/api/generate/generative',
                json={'project_id': pid, 'prompt': 'p', 'voice_id': self.voice_id},
                headers=self._auth_headers(self.owner_id),
            )
        self.assertEqual(resp.status_code, 202)
        delay.assert_called_once()
        _, kwargs = delay.call_args
        self.assertEqual(kwargs['voice_id'], self.voice_id)

    def test_assembler_without_voice_id_passes_none(self):
        pid = self._seed_project(self.owner_id)
        from src.tasks.video_tasks import generate_assembler_video_task
        with mock.patch.object(generate_assembler_video_task, 'delay', return_value=mock.Mock(id='c-3')) as delay:
            resp = self.client.post(
                '/api/generate/assembler',
                json={'project_id': pid, 'prompt': 'p'},
                headers=self._auth_headers(self.owner_id),
            )
        self.assertEqual(resp.status_code, 202)
        _, kwargs = delay.call_args
        self.assertIsNone(kwargs['voice_id'])

    def test_resolve_owned_voice_helper(self):
        with self.app.app_context():
            self.assertEqual(_resolve_owned_voice(None, 1), (None, None))
            self.assertEqual(_resolve_owned_voice('nope', 1)[1][1], 400)
            self.assertEqual(_resolve_owned_voice(999999, 1)[1][1], 404)
            self.assertEqual(_resolve_owned_voice(self.voice_id, self.other_id)[1][1], 403)
            v, err = _resolve_owned_voice(self.voice_id, self.owner_id)
            self.assertIsNone(err)
            self.assertEqual(v.id, self.voice_id)


if __name__ == '__main__':
    unittest.main()