import os
from src.services.cinema.critic_service import build_storyboard
from src.services.cinema.montage_service import TimelineShot


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
