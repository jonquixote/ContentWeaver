"""Route tests: /api/users/me GET/PATCH/DELETE, auth-required, partial update rules."""
import os
import shutil
import tempfile
import unittest

os.environ.setdefault('SECRET_KEY', 'route-test-secret')

from flask import Flask

from src.database import db
from src.routes.user import user_bp


class UserRouteTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='mw-user-test-')
        os.environ['DATABASE_URL'] = f"sqlite:///{os.path.join(self.tmpdir, 'user.db')}"
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(self.app)
        with self.app.app_context():
            from src.models.user import User
            db.create_all()
            self.me = User(username='me', email='me@t.com')
            self.me.hash_password('pw-me')
            self.other = User(username='other', email='other@t.com')
            self.other.hash_password('pw-other')
            db.session.add_all([self.me, self.other])
            db.session.commit()
            self.me_id, self.other_id = self.me.id, self.other.id
        self.app.register_blueprint(user_bp, url_prefix='/api')
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _auth(self, user_id):
        import datetime
        import jwt
        token = jwt.encode(
            {'user_id': user_id, 'jti': 'user-route-test',
             'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)},
            os.environ['SECRET_KEY'], algorithm='HS256')
        return {'Authorization': f'Bearer {token}'}

    def test_get_me_requires_auth(self):
        self.assertEqual(self.client.get('/api/users/me').status_code, 401)

    def test_patch_me_requires_auth(self):
        self.assertEqual(
            self.client.patch('/api/users/me', json={'username': 'x'}).status_code, 401)

    def test_delete_me_requires_auth(self):
        self.assertEqual(self.client.delete('/api/users/me').status_code, 401)

    def test_get_me_returns_user(self):
        resp = self.client.get('/api/users/me', headers=self._auth(self.me_id))
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['id'], self.me_id)
        self.assertEqual(data['username'], 'me')
        self.assertEqual(data['email'], 'me@t.com')

    def test_patch_username(self):
        resp = self.client.patch(
            '/api/users/me', json={'username': 'me2'}, headers=self._auth(self.me_id))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()['username'], 'me2')

    def test_patch_password(self):
        resp = self.client.patch(
            '/api/users/me', json={'password': 'new-pass'}, headers=self._auth(self.me_id))
        self.assertEqual(resp.status_code, 200)
        with self.app.app_context():
            from src.models.user import User
            user = db.session.get(User, self.me_id)
            self.assertTrue(user.verify_password('new-pass'))
            self.assertFalse(user.verify_password('pw-me'))

    def test_patch_password_non_string(self):
        resp = self.client.patch(
            '/api/users/me', json={'password': 12345}, headers=self._auth(self.me_id))
        self.assertEqual(resp.status_code, 400)

    def test_patch_duplicate_username_conflict(self):
        resp = self.client.patch(
            '/api/users/me', json={'username': 'other'}, headers=self._auth(self.me_id))
        self.assertEqual(resp.status_code, 409)
        with self.app.app_context():
            from src.models.user import User
            user = db.session.get(User, self.me_id)
            self.assertEqual(user.username, 'me')

    def test_patch_me_scoped_to_token_owner(self):
        resp = self.client.patch(
            '/api/users/me', json={'username': 'other2'}, headers=self._auth(self.other_id))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()['username'], 'other2')
        with self.app.app_context():
            from src.models.user import User
            self.assertEqual(db.session.get(User, self.me_id).username, 'me')

    def test_delete_me_removes_user(self):
        resp = self.client.delete('/api/users/me', headers=self._auth(self.me_id))
        self.assertEqual(resp.status_code, 204)
        with self.app.app_context():
            from src.models.user import User
            self.assertIsNone(db.session.get(User, self.me_id))


if __name__ == '__main__':
    unittest.main()