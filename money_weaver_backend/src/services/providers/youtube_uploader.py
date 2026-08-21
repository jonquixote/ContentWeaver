"""YouTube private upload via the official Data API v3 (Task 8).

Google client libraries are lazy-imported so their absence never breaks app
startup; using a YouTube feature without them raises a clear RuntimeError.
OAuth tokens are stored per user under instance/tokens/ with 0600 perms.

Env:
    GOOGLE_CLIENT_SECRET_FILE   path to the Google Cloud OAuth client secret
    YOUTUBE_OAUTH_REDIRECT_URI  redirect URI registered in Google Cloud console
    YOUTUBE_TOKEN_DIR           token storage dir (default instance/tokens)
"""
import hashlib
import hmac
import json
import os
import tempfile

SCOPES = ('https://www.googleapis.com/auth/youtube.upload',)

_BACKEND_ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
FINAL_DIR = os.path.join(_BACKEND_ROOT, 'final')


def _client_secret_file():
    return os.getenv('GOOGLE_CLIENT_SECRET_FILE', 'client_secret.json')


def _redirect_uri():
    return os.getenv('YOUTUBE_OAUTH_REDIRECT_URI',
                     'http://localhost:504/api/youtube/callback')


def token_dir():
    return os.getenv('YOUTUBE_TOKEN_DIR',
                     os.path.join(_BACKEND_ROOT, 'instance', 'tokens'))


def token_path(user_id):
    return os.path.join(token_dir(), f'token_{user_id}.json')


# --- lazy import seams (tests monkeypatch these) ---------------------------

def _flow_class():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError(
            'google-auth-oauthlib is not installed; '
            'run pip install google-auth-oauthlib') from exc
    return InstalledAppFlow


def _make_flow():
    secret = _client_secret_file()
    if not os.path.exists(secret):
        raise RuntimeError(
            f'YouTube OAuth client secret not found at {secret}; '
            'set GOOGLE_CLIENT_SECRET_FILE')
    flow_cls = _flow_class()
    flow = flow_cls.from_client_secrets_file(secret, list(SCOPES))
    flow.redirect_uri = _redirect_uri()
    return flow


def _credentials_cls():
    try:
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise RuntimeError(
            'google-auth is not installed; run pip install '
            'google-api-python-client google-auth-oauthlib') from exc
    return Credentials


def _load_credentials(user_id):
    path = token_path(user_id)
    if not os.path.exists(path):
        raise RuntimeError(
            f'No YouTube credentials for user {user_id} ({path}); '
            'complete OAuth first')
    creds_cls = _credentials_cls()
    return creds_cls.from_authorized_user_file(path, list(SCOPES))


def _build(credentials):
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            'google-api-python-client is not installed; '
            'run pip install google-api-python-client') from exc
    return build('youtube', 'v3', credentials=credentials)


def _media_upload_cls():
    try:
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:
        raise RuntimeError(
            'google-api-python-client is not installed; '
            'run pip install google-api-python-client') from exc
    return MediaFileUpload


# --- OAuth -----------------------------------------------------------------

def _state_sig(user_id):
    secret = os.environ['SECRET_KEY']
    return hmac.new(secret.encode(), str(user_id).encode(),
                    hashlib.sha256).hexdigest()[:16]


def sign_state(user_id):
    """HMAC-signed OAuth state so a callback cannot plant a foreign user id."""
    return f'{user_id}.{_state_sig(user_id)}'


def verify_state(state):
    """Return the user_id embedded in a signed state; ValueError if invalid."""
    user_id, sep, sig = str(state).partition('.')
    if (not sep or not user_id.isdigit()
            or not hmac.compare_digest(sig, _state_sig(user_id))):
        raise ValueError('invalid OAuth state signature')
    return int(user_id)


def get_auth_url(user_id):
    """Return the Google consent URL for the installed-app flow."""
    flow = _make_flow()
    url, _ = flow.authorization_url(access_type='offline', prompt='consent',
                                    state=sign_state(user_id))
    return url


def save_token(credentials, user_id):
    """Persist credentials JSON as 0600 under the per-user token path."""
    path = token_path(user_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = (credentials.to_json()
               if hasattr(credentials, 'to_json') else json.dumps(credentials))
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as fh:
        fh.write(payload)
    os.chmod(path, 0o600)  # enforce even if umask loosened it
    return path


def handle_callback(code, user_id):
    """Exchange an OAuth code for tokens and store them for this user."""
    flow = _make_flow()
    flow.fetch_token(code=code)
    return save_token(flow.credentials, user_id)


# --- Upload ----------------------------------------------------------------

def resolve_video_file(video_ref):
    """Map project.video_url to a local file path.

    Local paths pass through; /final/<name> maps into backend final/;
    anything else is treated as a storage key and materialized to a temp
    .mp4 (caller unlinks it).
    """
    if not video_ref:
        raise RuntimeError('Project has no rendered video to upload')
    if os.path.exists(video_ref):
        return video_ref, False
    if video_ref.startswith('/final/'):
        local = os.path.join(FINAL_DIR, os.path.basename(video_ref))
        if os.path.exists(local):
            return local, False
    from src.services.storage import get_storage
    data = get_storage().get_object(video_ref)
    fd, tmp = tempfile.mkstemp(suffix='.mp4', prefix='yt_upload_')
    with os.fdopen(fd, 'wb') as fh:
        fh.write(data)
    return tmp, True


def _upload_captions(youtube, video_id, transcript):
    """Attach an SRT sidecar built from word-level transcript words."""
    from src.services.video.captions import export_srt
    srt_content = export_srt(transcript)
    fd, srt_path = tempfile.mkstemp(suffix='.srt', prefix='yt_caps_')
    try:
        with os.fdopen(fd, 'w') as fh:
            fh.write(srt_content)
        media = _media_upload_cls()(
            srt_path, mimetype='application/octet-stream', resumable=False)
        youtube.captions().insert(
            part='snippet',
            body={'snippet': {'videoId': video_id, 'language': 'en'}},
            media_body=media,
        ).execute()
    finally:
        if os.path.exists(srt_path):
            os.unlink(srt_path)


def upload_video(project_id, privacy='private', video_path=None, transcript=None):
    """Upload the project's rendered video as private (default).

    Requires prior OAuth (token file) and the google client libraries.
    Returns {'youtube_url': ..., 'video_id': ...}. When a word-level
    transcript is available on the project, an SRT caption track is uploaded
    alongside the video (failure there is non-fatal).
    """
    from src.database import db
    from src.models.project import Project

    project = db.session.get(Project, project_id)
    if project is None:
        raise RuntimeError(f'Project {project_id} not found')

    credentials = _load_credentials(project.user_id)
    youtube = _build(credentials)

    if video_path:
        resolved, temp = video_path, False
    else:
        resolved, temp = resolve_video_file(project.video_url)

    try:
        media = _media_upload_cls()(
            resolved, mimetype='video/mp4', resumable=True, chunksize=-1)
        request = youtube.videos().insert(
            part='snippet,status',
            body={
                'snippet': {
                    'title': project.title or f'Project {project_id}',
                    'description': project.description or '',
                },
                'status': {'privacyStatus': privacy},
            },
            media_body=media,
        )
        response = None
        while response is None:
            _chunk, response = request.next_chunk()
        video_id = response['id']

        words = transcript if transcript is not None else getattr(
            project, 'transcript', None)
        # project.transcript is stored as a JSON string; parse before SRT build.
        if isinstance(words, str):
            try:
                words = json.loads(words)
            except (ValueError, TypeError):
                words = None
        if words:
            try:
                _upload_captions(youtube, video_id, words)
            except Exception as exc:  # captions are best-effort
                print(f'Caption upload failed (non-fatal): {exc}')

        return {'youtube_url': f'https://youtu.be/{video_id}',
                'video_id': video_id}
    finally:
        if temp and os.path.exists(resolved):
            try:
                os.unlink(resolved)
            except OSError:
                pass
