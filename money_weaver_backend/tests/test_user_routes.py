"""Route tests: /api/users/me GET/PATCH/DELETE, auth-required, partial update rules."""
import os
import shutil
import tempfile
import unittest

os.environ.setdefault('SECRET_KEY', 'route-test-secret')

from flask import Flask

from src.database import db
from src.models.project import Project
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
            from sqlalchemy import event

            @event.listens_for(db.engine, 'connect')
            def _enable_sqlite_fks(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute('PRAGMA foreign_keys=ON')
                cursor.close()

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

    def test_patch_blank_username_rejected(self):
        resp = self.client.patch(
            '/api/users/me', json={'username': '   '}, headers=self._auth(self.me_id))
        self.assertEqual(resp.status_code, 400)
        with self.app.app_context():
            from src.models.user import User
            self.assertEqual(db.session.get(User, self.me_id).username, 'me')

    def test_patch_blank_email_rejected(self):
        resp = self.client.patch(
            '/api/users/me', json={'email': ''}, headers=self._auth(self.me_id))
        self.assertEqual(resp.status_code, 400)
        with self.app.app_context():
            from src.models.user import User
            self.assertEqual(db.session.get(User, self.me_id).email, 'me@t.com')

    def test_patch_null_username_rejected(self):
        resp = self.client.patch(
            '/api/users/me', json={'username': None}, headers=self._auth(self.me_id))
        self.assertEqual(resp.status_code, 400)
        with self.app.app_context():
            from src.models.user import User
            self.assertEqual(db.session.get(User, self.me_id).username, 'me')

    def test_patch_null_email_rejected(self):
        resp = self.client.patch(
            '/api/users/me', json={'email': None}, headers=self._auth(self.me_id))
        self.assertEqual(resp.status_code, 400)
        with self.app.app_context():
            from src.models.user import User
            self.assertEqual(db.session.get(User, self.me_id).email, 'me@t.com')

    def test_create_user_requires_auth(self):
        resp = self.client.post('/api/users', json={
            'username': 'fresh', 'email': 'fresh@t.com', 'password': 'pw-fresh'})
        self.assertEqual(resp.status_code, 401)

    def test_create_user_creates(self):
        resp = self.client.post('/api/users', json={
            'username': 'fresh', 'email': 'fresh@t.com', 'password': 'pw-fresh'},
            headers=self._auth(self.me_id))
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertEqual(data['username'], 'fresh')
        with self.app.app_context():
            from src.models.user import User
            self.assertIsNotNone(User.query.filter_by(username='fresh').first())

    def test_create_user_duplicate_username_conflict(self):
        resp = self.client.post('/api/users', json={
            'username': 'other', 'email': 'fresh@t.com', 'password': 'pw-fresh'},
            headers=self._auth(self.me_id))
        self.assertEqual(resp.status_code, 409)
        with self.app.app_context():
            from src.models.user import User
            self.assertIsNone(User.query.filter_by(email='fresh@t.com').first())

    def test_create_user_duplicate_email_conflict(self):
        resp = self.client.post('/api/users', json={
            'username': 'fresh', 'email': 'other@t.com', 'password': 'pw-fresh'},
            headers=self._auth(self.me_id))
        self.assertEqual(resp.status_code, 409)
        with self.app.app_context():
            from src.models.user import User
            self.assertIsNone(User.query.filter_by(username='fresh').first())

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

    def test_delete_me_conflict_with_child_data(self):
        with self.app.app_context():
            db.session.add(Project(title='child project', user_id=self.me_id, voice_type='female'))
            db.session.commit()
        headers = self._auth(self.me_id)
        resp = self.client.delete('/api/users/me', headers=headers)
        self.assertEqual(resp.status_code, 409)
        self.assertIn('projects', resp.get_json()['error'])
        with self.app.app_context():
            from src.models.user import User
            self.assertIsNotNone(db.session.get(User, self.me_id))
            self.assertEqual(db.session.query(Project).count(), 1)
        self.assertEqual(self.client.get('/api/users/me', headers=headers).status_code, 200)

    def test_delete_me_409_on_fk_violation(self):
        from unittest import mock
        with self.app.app_context():
            db.session.add(Project(title='child project', user_id=self.me_id, voice_type='female'))
            db.session.commit()
        with mock.patch('src.routes.user._user_has_child_data', return_value=False):
            resp = self.client.delete('/api/users/me', headers=self._auth(self.me_id))
        self.assertEqual(resp.status_code, 409)
        self.assertIn('projects', resp.get_json()['error'])

    def test_delete_me_revokes_token(self):
        headers = self._auth(self.me_id)
        resp = self.client.delete('/api/users/me', headers=headers)
        self.assertEqual(resp.status_code, 204)
        with self.app.app_context():
            from src.models.token_blocklist import TokenBlocklist
            self.assertIsNotNone(TokenBlocklist.query.filter_by(jti='user-route-test').first())
        self.assertEqual(self.client.get('/api/users/me', headers=headers).status_code, 401)

    def test_deleted_user_token_rejected(self):
        headers = self._auth(self.other_id)
        with self.app.app_context():
            from src.models.user import User
            db.session.delete(db.session.get(User, self.other_id))
            db.session.commit()
        resp = self.client.get('/api/users/me', headers=headers)
        self.assertEqual(resp.status_code, 401)


if __name__ == '__main__':
    unittest.main()