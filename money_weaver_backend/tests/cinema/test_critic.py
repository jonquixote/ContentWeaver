import json
import os
from src.services.cinema.critic_service import (
    GeminiCriticClient,
    build_critic_prompt,
    build_storyboard,
    critique_plan_for_render,
    parse_critique,
    run_critique,
)
from src.services.cinema.montage_service import TimelinePlan, TimelineShot
from src.services.cinema.shot import ShotSpec
from src.services.cinema.types import CameraMove, ShotFunction, ShotScale


def _shot(i, clip="c"):
    return TimelineShot(clip_id=f"{clip}{i}", in_point_s=0.0, out_point_s=2.5)


def test_build_storyboard_skips_unresolvable(tmp_path):
    shots = [_shot(0), _shot(1)]
    out = build_storyboard(shots, lambda cid: None, str(tmp_path))
    assert out == []


def test_build_storyboard_extracts_middle_frame(tmp_path):
    import subprocess
    src = str(tmp_path / "src.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "testsrc=duration=4:size=320x240:rate=10",
                    "-pix_fmt", "yuv420p", src], check=True, timeout=60)
    shots = [_shot(0, clip="v")]
    out = build_storyboard(shots, lambda cid: src, str(tmp_path / "sb"), image_size=160)
    assert len(out) == 1
    assert out[0]["shot_index"] == 0
    assert os.path.exists(out[0]["frame_path"])


def test_build_storyboard_index_survives_skips():
    # A skipped (unresolvable) shot must NOT shift alignment: shot_index is the
    # position in plan.shots, so frames stay aligned with specs.
    import subprocess
    import tempfile
    tmp = tempfile.mkdtemp()
    src = os.path.join(tmp, "src.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "testsrc=duration=4:size=320x240:rate=10",
                    "-pix_fmt", "yuv420p", src], check=True, timeout=60)
    shots = [_shot(0), _shot(1), _shot(2)]
    def resolve(cid):
        return src if cid in ("c0", "c2") else None
    out = build_storyboard(shots, resolve, os.path.join(tmp, "sb"), image_size=160)
    assert [r["shot_index"] for r in out] == [0, 2]
    assert [r["clip_id"] for r in out] == ["c0", "c2"]


def _spec(i):
    return ShotSpec(scene_number=1, shot_index=i, narrative_beats="jokes fly",
                    subject_concrete="comedian with microphone on stage",
                    scale=ShotScale.MS, move=CameraMove.STATIC,
                    function=ShotFunction.CONTEXT, mood="dim")


def test_prompt_lists_every_shot_spec():
    prompt = build_critic_prompt([_spec(0), _spec(1)], n_frames=2)
    assert "comedian with microphone on stage" in prompt
    assert "shot_index" in prompt
    assert "match" in prompt and "mismatch" in prompt


def test_prompt_demands_strict_json_shape():
    prompt = build_critic_prompt([_spec(0)], n_frames=1)
    assert "overall_verdict" in prompt
    assert "reason" in prompt


def test_agentic_prompt_requests_timestamps():
    prompt = build_critic_prompt([_spec(0)], n_frames=0, agentic=True)
    assert "timestamp" in prompt.lower()


def test_parse_critique_accepts_valid_json():
    raw = ('{"shots": [{"shot_index": 0, "verdict": "mismatch", "reason": "shows a duck, spec needs a comedian"}], '
           '"overall_verdict": "review", "summary": "one off-theme pick"}')
    c = parse_critique(raw)
    assert c is not None
    assert c.overall_verdict == "review"
    assert c.shots[0].verdict == "mismatch"


def test_parse_critique_rejects_garbage_silently():
    assert parse_critique(None) is None
    assert parse_critique("not json at all") is None
    assert parse_critique('{"shots": "wrong-shape"}') is None


def test_parse_critique_extracts_json_from_prose():
    raw = 'Here is my review:\n{"shots": [], "overall_verdict": "pass", "summary": "clean"}'
    c = parse_critique(raw)
    assert c is not None and c.overall_verdict == "pass"


def test_client_skips_without_keys(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("src.services.cinema.critic_service._gemini_keys", lambda: [])
    client = GeminiCriticClient()
    assert client.critique([], "prompt") is None


def _plan():
    from src.services.cinema.types import MontageMode
    return TimelinePlan(mode=MontageMode.OVERTONAL, shots=[
        TimelineShot(clip_id="c0", in_point_s=0.0, out_point_s=2.5),
    ])


def _specs():
    from src.services.cinema.types import MontageMode  # noqa: F401 (keep parity with brief)
    return [ShotSpec(scene_number=1, shot_index=0, narrative_beats="jokes",
                     subject_concrete="comedian", scale=ShotScale.MS,
                     move=CameraMove.STATIC, function=ShotFunction.CONTEXT, mood="dim")]


def test_run_critique_disabled_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("CINEMA_CRITIC_ENABLED", "false")
    assert run_critique(_plan(), _specs(), lambda cid: None,
                        project_id="p", render_id="r",
                        persist_dir=str(tmp_path)) is None


def test_run_critique_persists_valid_critique(monkeypatch, tmp_path):
    monkeypatch.setenv("CINEMA_CRITIC_ENABLED", "true")
    from src.services.cinema import critic_service as cs
    _one_row(monkeypatch)
    fake = {"shots": [], "overall_verdict": "pass", "summary": "clean"}
    monkeypatch.setattr(cs.GeminiCriticClient, "critique", lambda self, f, p, **k: cs.parse_critique(__import__("json").dumps(fake)))
    out = run_critique(_plan(), _specs(), lambda cid: None,
                       project_id="p1", render_id="r1", persist_dir=str(tmp_path))
    assert out is not None and out.overall_verdict == "pass"
    saved = list(tmp_path.glob("*.json"))
    assert len(saved) == 1
    assert json.loads(saved[0].read_text())["overall_verdict"] == "pass"


def test_run_critique_never_raises_on_client_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("CINEMA_CRITIC_ENABLED", "true")
    from src.services.cinema import critic_service as cs
    _one_row(monkeypatch)
    def boom(self, f, p, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(cs.GeminiCriticClient, "critique", boom)
    assert run_critique(_plan(), _specs(), lambda cid: None,
                        project_id="p", render_id="r", persist_dir=str(tmp_path)) is None


def _one_row(monkeypatch):
    # One scored storyboard row so tests exercise the client path
    # (zero real frames short-circuits before the client).
    from src.services.cinema import critic_service as cs
    monkeypatch.setattr(cs, "build_storyboard",
                        lambda shots, resolve, out_dir, **k:
                        [{"shot_index": 0, "clip_id": "c0", "frame_path": "sb.jpg"}])


def test_wiring_synthesizes_plan_wrapper_when_no_timing_plan():
    # Timing off: a TimelinePlan wrapper (not a bare list) so run_critique's
    # plan.shots works in both paths.
    plan = critique_plan_for_render(None, [2.5, 2.5])
    assert isinstance(plan, TimelinePlan)
    assert len(plan.shots) == 2
    assert all(isinstance(s, TimelineShot) for s in plan.shots)


def test_run_critique_works_with_synthesized_plan(monkeypatch, tmp_path):
    # The timing-off wrapper must flow through run_critique without
    # AttributeError (previously: bare list had no .shots).
    monkeypatch.setenv("CINEMA_CRITIC_ENABLED", "true")
    from src.services.cinema import critic_service as cs
    _one_row(monkeypatch)
    fake = {"shots": [], "overall_verdict": "pass", "summary": "clean"}
    monkeypatch.setattr(cs.GeminiCriticClient, "critique", lambda self, f, p, **k: cs.parse_critique(json.dumps(fake)))
    plan = critique_plan_for_render(None, [2.5])
    out = run_critique(plan, _specs(), lambda cid: None,
                       project_id="p", render_id="r", persist_dir=str(tmp_path))
    assert out is not None and out.overall_verdict == "pass"


def test_run_critique_threads_video_path_and_skips_frames_when_agentic(monkeypatch, tmp_path):
    # Agentic + final video: video carries the visuals, storyboard skipped,
    # video_path reaches the client.
    monkeypatch.setenv("CINEMA_CRITIC_ENABLED", "true")
    monkeypatch.setenv("CRITIC_MODE", "agentic")
    from src.services.cinema import critic_service as cs
    def boom_sb(*a, **k):
        raise AssertionError("storyboard must be skipped when agentic video present")
    monkeypatch.setattr(cs, "build_storyboard", boom_sb)
    seen = {}
    fake = {"shots": [], "overall_verdict": "pass", "summary": "clean"}
    def fake_critique(self, frames, prompt, **k):
        seen["frames"] = frames
        seen.update(k)
        return cs.parse_critique(json.dumps(fake))
    monkeypatch.setattr(cs.GeminiCriticClient, "critique", fake_critique)
    out = run_critique(_plan(), _specs(), lambda cid: None,
                       project_id="p", render_id="r", persist_dir=str(tmp_path),
                       video_path="/tmp/final.mp4")
    assert out is not None
    assert seen.get("video_path") == "/tmp/final.mp4"
    assert seen.get("frames") == []
    assert seen.get("agentic") is True


def test_maybe_critique_render_threads_video_path(monkeypatch):
    monkeypatch.setenv("CINEMA_CRITIC_ENABLED", "true")
    from src.services.cinema import critic_service as cs
    seen = {}
    def fake_run(plan, specs, resolve, **k):
        seen.update(k)
        return None
    monkeypatch.setattr(cs, "run_critique", fake_run)
    cs.maybe_critique_render(_plan(), _specs(), lambda cid: None, "p", "r",
                             video_path="/tmp/final.mp4")
    assert seen.get("video_path") == "/tmp/final.mp4"


def _spec_named(i, subject):
    return ShotSpec(scene_number=1, shot_index=i, narrative_beats="beats",
                    subject_concrete=subject, scale=ShotScale.MS,
                    move=CameraMove.STATIC, function=ShotFunction.CONTEXT, mood="dim")


def test_prompt_filters_specs_to_scored_frames():
    # Truncated frames → filtered specs: only shot 0 was scored.
    specs = [_spec_named(0, "comedian-alpha"), _spec_named(1, "comedian-beta"),
             _spec_named(2, "comedian-gamma")]
    frames = [{"shot_index": 0, "clip_id": "c0", "frame_path": "a.jpg"}]
    prompt = build_critic_prompt(specs, n_frames=1, frames=frames)
    assert "comedian-alpha" in prompt
    assert "comedian-beta" not in prompt
    assert "comedian-gamma" not in prompt


def test_prompt_labels_frames_with_shot_index():
    # Skipped shot 1 keeps its index: frames labeled, spec 1 absent.
    specs = [_spec_named(0, "comedian-alpha"), _spec_named(1, "comedian-beta"),
             _spec_named(2, "comedian-gamma")]
    frames = [{"shot_index": 0, "clip_id": "c0", "frame_path": "a.jpg"},
              {"shot_index": 2, "clip_id": "c2", "frame_path": "c.jpg"}]
    prompt = build_critic_prompt(specs, n_frames=2, frames=frames)
    assert "shot 0" in prompt.lower()
    assert "shot 2" in prompt.lower()
    assert "comedian-beta" not in prompt


def test_run_critique_zero_frames_returns_none_without_call(monkeypatch, tmp_path):
    # Static mode, nothing scored: no Gemini call, no persisted verdict.
    monkeypatch.setenv("CINEMA_CRITIC_ENABLED", "true")
    monkeypatch.setenv("CRITIC_MODE", "static")
    from src.services.cinema import critic_service as cs
    called = []
    def record(self, f, p, **k):
        called.append((f, p))
        return None
    monkeypatch.setattr(cs.GeminiCriticClient, "critique", record)
    out = run_critique(_plan(), _specs(), lambda cid: None,
                       project_id="p", render_id="r", persist_dir=str(tmp_path))
    assert out is None
    assert called == []
    assert list(tmp_path.glob("*.json")) == []


def test_wiring_reuses_timing_plan_when_present():
    from src.services.cinema.montage_service import TimelinePlan, TimelineShot
    from src.services.cinema.types import MontageMode
    plan = TimelinePlan(mode=MontageMode.OVERTONAL, shots=[
        TimelineShot(clip_id="a", in_point_s=0.0, out_point_s=2.5),
    ])
    assert critique_plan_for_render(plan, []) is plan  # same object, no parallel structure


def test_wiring_returns_none_when_disabled(monkeypatch):
    monkeypatch.setenv("CINEMA_CRITIC_ENABLED", "false")
    from src.services.cinema.critic_service import maybe_critique_render
    assert maybe_critique_render(None, [], lambda cid: None, "p", "r") is None
