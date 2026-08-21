"""Project.transcript persistence (Phase D Task 2).

persist_transcript must write word-level JSON to project.transcript using its
own session (fastapi_app.db), so it works inside Celery workers and in tests
without a Flask app context.
"""
import json

from src.models.project import Project
from src.models.user import User


def _make_project(db_session):
    user = User(username='tr-owner', email='tr@t.com', password_hash='x')
    db_session.add(user)
    db_session.flush()
    project = Project(title='t', description='d', user_id=user.id,
                      workflow_type='assembler')
    db_session.add(project)
    db_session.commit()
    return project


def test_project_model_has_transcript_column():
    assert hasattr(Project, 'transcript')


def test_assembler_persists_transcript(client, auth_headers, db_session, monkeypatch):
    """After assembler task runs, project.transcript holds whisper word JSON."""
    fake_words = [{"word": "Hello", "start": 0.0, "end": 0.5}]
    monkeypatch.setattr(
        "src.tasks.video_tasks.extract_transcript_words",
        lambda audio_path: fake_words,
    )
    monkeypatch.setattr(
        "fastapi_app.routers.generation.generate_assembler_video_task.delay",
        lambda **k: type("R", (), {"id": "celery-x"})(),
    )

    p = _make_project(db_session)

    from src.tasks.video_tasks import persist_transcript
    persist_transcript(p.id, fake_words)
    db_session.expire_all()
    assert json.loads(db_session.get(Project, p.id).transcript) == fake_words
