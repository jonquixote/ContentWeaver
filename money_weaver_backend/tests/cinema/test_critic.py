import os
from src.services.cinema.critic_service import build_critic_prompt, build_storyboard
from src.services.cinema.montage_service import TimelineShot
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
