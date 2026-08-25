"""Assignment-consumption tests: voice_tts / video_gen assignments must drive
which backend the Celery tasks actually use (comfy_local vs fal-ai/*).

Harnesses are copied verbatim from:
- tests/test_comfy_client.py::test_enabled_generative_task_full_path
- tests/test_tasks.py::test_assembler_task_state_transition_pending_to_completed
"""
import json
import types
from unittest import mock

from src.models.task import Task
from src.models.project import Project
import src.tasks.video_tasks as vt


def test_generative_uses_fal_when_assigned(monkeypatch, client, auth_headers, db_session, tmp_path):
    """video_gen=fal-ai/... routes through fal_adapter.render, not comfy."""
    from src.tasks import video_tasks as vt

    # -- DB rows: project + pending task record (route normally creates it) --
    r = client.post('/api/projects', json={'title': 'Gen e2e'},
                    headers=auth_headers)
    project_id = r.json()['id']

    with mock.patch.object(vt.generate_generative_video_task, 'delay',
                           return_value=mock.Mock(id='fake-celery-id')):
        task_id = client.post('/api/generate/generative',
                              json={'project_id': project_id, 'prompt': 'cat'},
                              headers=auth_headers).json()['task_id']

    # -- Flag + assignment + fal mocks ---------------------------------------
    monkeypatch.setenv('COMFY_ENABLED', 'true')
    monkeypatch.setattr(vt, 'FINAL_DIR', str(tmp_path))
    monkeypatch.setattr(vt, 'resolve_model_for',
                        lambda uid, task: {'video_gen': 'fal-ai/wan-t2v'}[task])

    rendered = {}

    def fake_render(ep, args, api_key=None, work_dir=None, timeout_s=600):
        rendered['ep'] = ep
        rendered['args'] = dict(args)
        return str(tmp_path / 'out.mp4')

    monkeypatch.setattr(vt.fal_adapter, 'render', fake_render)
    (tmp_path / 'out.mp4').write_bytes(b'MP4')

    poll_calls = {'n': 0}

    async def fake_poll(pid, timeout=300):
        poll_calls['n'] += 1
        return {'status': 'success'}

    stored = {}
    fake_storage = mock.Mock()
    fake_storage.put_object = lambda key, data, content_type=None: stored.setdefault(key, data)

    pipeline = [
        mock.patch.object(vt.comfy_client, 'health', lambda: True),
        mock.patch.object(vt.comfy_client, 'poll_result', fake_poll),
        mock.patch.object(vt.llm_service, 'generate_script',
                          lambda *a, **k: 'enhanced prompt'),
        mock.patch.object(vt, 'get_storage', lambda: fake_storage),
    ]
    for p in pipeline:
        p.start()
    try:
        fake_self = types.SimpleNamespace(
            request=types.SimpleNamespace(id='fake-celery-id'))
        fake_self.update_state = lambda *a, **k: None
        vt.generate_generative_video_task.run.__func__(fake_self,
                                                       project_id=project_id,
                                                       prompt='cat')
    finally:
        for p in pipeline:
            p.stop()

    # -- Assertions -----------------------------------------------------------
    assert rendered.get('ep') == 'fal-ai/wan-t2v'
    assert poll_calls['n'] == 0  # comfy flow never touched

    local_file = tmp_path / f'project_{project_id}_generative.mp4'
    assert local_file.exists() and local_file.read_bytes() == b'MP4'

    expected_key = f'generative/{project_id}/project_{project_id}_generative.mp4'
    assert stored.get(expected_key) == b'MP4'

    task = db_session.get(Task, task_id)
    assert task is not None and task.status == 'completed'


def test_assembler_voice_tts_auto_keeps_local_chain(client, db_session, auth_headers, tmp_path):
    """voice_tts='auto' (default) must not attempt fal."""
    import src.tasks.video_tasks as vt
    from src.tasks.video_tasks import generate_assembler_video_task
    project_id = None

    r = client.post('/api/projects', json={'title': 'Task test project'},
                    headers=auth_headers)
    project_id = r.json()['id']

    with mock.patch.object(generate_assembler_video_task, 'delay',
                           return_value=mock.Mock(id='fake-celery-id')):
        task_id = client.post('/api/generate/assembler',
                              json={'project_id': project_id, 'prompt': 'a prompt'},
                              headers=auth_headers).json()['task_id']

    fal_called = {'n': 0}
    monkey_fal = mock.patch.object(vt.fal_adapter, 'render',
                                   lambda *a, **k: fal_called.__setitem__('n', fal_called['n'] + 1))

    # Fake media assets that must exist on disk for the task body to proceed.
    out = tmp_path / 'out.mp4'
    out.write_bytes(b'\x00\x00\x00\x18ftypmp42')
    thumb = tmp_path / 'thumb.jpg'
    thumb.write_bytes(b'\xff\xd8\xff\xe0')
    kokoro = tmp_path / 'kokoro.wav'
    kokoro.write_bytes(b'RIFF\x00')

    pipeline = [
        monkey_fal,
        mock.patch.object(vt, 'llm_service'),
        mock.patch.object(vt, 'script_parsing_service'),
        mock.patch.object(vt, 'advanced_tts_service'),
        mock.patch.object(vt, 'stock_service'),
        mock.patch.object(vt, 'assembly_service'),
    ]
    for p in pipeline:
        p.start()
    vt.llm_service.generate_script.return_value = '# Title\n\nScript body.\n'
    vt.script_parsing_service.parse_script.return_value = {'scenes': []}
    vt.script_parsing_service.extract_voiceover_text.return_value = 'narration text'
    vt.advanced_tts_service.generate_tts.return_value = str(kokoro)
    vt.stock_service.get_stock_videos_for_script.return_value = ['a.mp4', 'b.mp4']
    vt.assembly_service.assemble_video.return_value = str(out)
    thumb_patch = mock.patch.object(vt, 'generate_thumbnail', return_value=str(thumb))
    thumb_patch.start()
    try:
        result = generate_assembler_video_task.run.__func__(
            types.SimpleNamespace(request=types.SimpleNamespace(id='fake-celery-id'),
                                  update_state=lambda *a, **k: None),
            project_id=project_id, prompt='a prompt')
    finally:
        thumb_patch.stop()
        for p in pipeline:
            p.stop()

    assert result['status'] == 'Video generation completed!'
    assert fal_called['n'] == 0

    task = db_session.get(Task, task_id)
    assert task is not None and task.status == 'completed'


def _assembler_harness(client, auth_headers, tmp_path):
    """Create project + pending assembler task; return (project_id, task_id)."""
    r = client.post('/api/projects', json={'title': 'Script assignment'},
                    headers=auth_headers)
    project_id = r.json()['id']
    with mock.patch.object(vt.generate_assembler_video_task, 'delay',
                           return_value=mock.Mock(id='fake-celery-id')):
        task_id = client.post('/api/generate/assembler',
                              json={'project_id': project_id, 'prompt': 'a prompt'},
                              headers=auth_headers).json()['task_id']
    return project_id, task_id


_ASSEMBLER_MEDIA = dict(
    out_name='out.mp4', out_bytes=b'\x00\x00\x00\x18ftypmp42',
    thumb_bytes=b'\xff\xd8\xff\xe0', kokoro_bytes=b'RIFF\x00')


def _run_assembler_with_mocks(monkeypatch, tmp_path, project_id, assignments,
                              explicit_model=None):
    """Run generate_assembler_video_task with resolve_model_for returning
    `assignments` (task->model) and llm_service mocked. Returns the
    generate_script Mock for call assertions."""
    import src.tasks.video_tasks as vt
    from src.tasks.video_tasks import generate_assembler_video_task

    monkeypatch.setattr(vt, 'resolve_model_for',
                        lambda uid, task: assignments[task])
    monkeypatch.setattr(vt, 'llm_service', mock.Mock())
    monkeypatch.setattr(vt, 'script_parsing_service', mock.Mock())
    monkeypatch.setattr(vt, 'advanced_tts_service', mock.Mock())
    monkeypatch.setattr(vt, 'stock_service', mock.Mock())
    monkeypatch.setattr(vt, 'assembly_service', mock.Mock())
    vt.llm_service.generate_script.return_value = '# Title\n\nScript body.\n'
    vt.script_parsing_service.parse_script.return_value = {'scenes': []}
    vt.script_parsing_service.extract_voiceover_text.return_value = 'narration'
    vt.advanced_tts_service.generate_tts.return_value = str(tmp_path / 'kokoro.wav')
    vt.advanced_tts_service.working_dir = str(tmp_path)
    vt.stock_service.get_stock_videos_for_script.return_value = ['a.mp4']
    vt.assembly_service.assemble_video.return_value = str(tmp_path / 'out.mp4')
    (tmp_path / 'kokoro.wav').write_bytes(b'RIFF\x00')
    (tmp_path / 'out.mp4').write_bytes(b'\x00\x00\x00\x18ftypmp42')
    thumb_patch = mock.patch.object(vt, 'generate_thumbnail',
                                    return_value=str(tmp_path / 'thumb.jpg'))
    storage_patch = mock.patch.object(vt, 'get_storage',
                                      lambda: mock.Mock())
    thumb_patch.start()
    storage_patch.start()
    try:
        result = generate_assembler_video_task.run.__func__(
            types.SimpleNamespace(request=types.SimpleNamespace(id='fake-celery-id'),
                                  update_state=lambda *a, **k: None),
            project_id=project_id, prompt='a prompt',
            model=explicit_model)
    finally:
        thumb_patch.stop()
        storage_patch.stop()
    assert result['status'] == 'Video generation completed!'
    return vt.llm_service.generate_script


def test_assembler_uses_script_assignment(client, db_session, auth_headers,
                                          tmp_path, monkeypatch):
    """script assignment must be consumed server-side by the assembler task."""
    project_id, task_id = _assembler_harness(client, auth_headers, tmp_path)

    gen_script = _run_assembler_with_mocks(
        monkeypatch, tmp_path, project_id,
        {'script': 'groq/assigned-script-model', 'voice_tts': 'auto'},
        explicit_model=None)

    kwargs = gen_script.call_args.kwargs
    assert kwargs['model'] == 'groq/assigned-script-model'

    task = db_session.get(Task, task_id)
    assert task is not None and task.status == 'completed'


def test_assembler_explicit_model_beats_assignment(client, auth_headers,
                                                   tmp_path, monkeypatch):
    """Wizard override (explicit task arg) > assignment."""
    project_id, _task_id = _assembler_harness(client, auth_headers, tmp_path)

    gen_script = _run_assembler_with_mocks(
        monkeypatch, tmp_path, project_id,
        {'script': 'groq/assigned-script-model', 'voice_tts': 'auto'},
        explicit_model='openai/wizard-override')

    assert gen_script.call_args.kwargs['model'] == 'openai/wizard-override'
