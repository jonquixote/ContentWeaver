import os
import subprocess as sp

from src.services.video.captions import build_ass, burn_ass, export_srt


def test_build_ass_word_highlight():
    transcript = [
        {"word": "Hello", "start": 0.0, "end": 0.5},
        {"word": "world", "start": 0.5, "end": 1.0},
    ]
    ass = build_ass(transcript, {"highlight": "#00FF88", "font": "Arial"})
    assert "Hello" in ass
    assert "Dialogue:" in ass


def test_build_ass_niche_defaults():
    ass = build_ass([{"word": "Hi", "start": 0, "end": 1}], {})
    assert "Arial" in ass
    assert "00FF88" in ass
    assert "\\c&00FF88&" in ass


def test_build_ass_ass_timecode():
    ass = build_ass([{"word": "Hi", "start": 1.5, "end": 2.0}], {})
    assert "0:00:01.50" in ass
    assert "0:00:02.00" in ass


def test_export_srt():
    transcript = [{"word": "Hi", "start": 0, "end": 1}]
    srt = export_srt(transcript)
    assert "00:00:00,000" in srt
    assert "1\n00:00:00,000 --> 00:00:01,000\nHi" in srt


def test_export_srt_hour_rollover():
    srt = export_srt([{"word": "Hi", "start": 3661, "end": 3662}])
    assert "01:01:01,000 --> 01:01:02,000" in srt


def test_burn_ass(tmp_path, monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured['cmd'] = cmd
        return sp.CompletedProcess(cmd, 0)

    monkeypatch.setattr(sp, 'run', fake_run)
    inp = tmp_path / 'in.mp4'
    inp.write_bytes(b'x')
    ass_path = tmp_path / 'c.ass'
    ass_path.write_text('x')
    out = tmp_path / 'out.mp4'
    result = burn_ass(str(inp), str(ass_path), str(out))
    assert result == str(out)
    cmd = captured['cmd']
    assert cmd[0] == 'ffmpeg'
    assert '-i' in cmd and str(inp) in cmd
    vf_idx = cmd.index('-vf')
    assert str(ass_path) in cmd[vf_idx + 1]


def test_burn_ass_default_output(tmp_path, monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured['cmd'] = cmd
        return sp.CompletedProcess(cmd, 0)

    monkeypatch.setattr(sp, 'run', fake_run)
    inp = tmp_path / 'in.mp4'
    inp.write_bytes(b'x')
    out = burn_ass(str(inp), str(tmp_path / 'c.ass'))
    assert out == str(tmp_path / 'in_captioned.mp4')


def test_burn_captions_routes_word_transcript_to_ass(tmp_path, monkeypatch):
    from src.services.video import captions as caps
    from src.services.video.assembly_service import VideoAssemblyService

    svc = VideoAssemblyService()
    svc.output_dir = str(tmp_path)
    svc.working_dir = str(tmp_path)
    video = tmp_path / 'in.mp4'
    video.write_bytes(b'video')
    transcript = [{"word": "Hello", "start": 0.0, "end": 0.5}]

    captured = {}

    def fake_burn(input_mp4, ass_path, output_mp4):
        with open(ass_path, encoding='utf-8') as f:
            captured['ass'] = f.read()
        captured['in'] = input_mp4
        captured['out'] = output_mp4
        with open(output_mp4, 'wb') as f:
            f.write(b'burned')

    monkeypatch.setattr(caps, 'burn_ass', fake_burn)
    result = svc._burn_captions(str(video), transcript, 30)
    assert result == str(video)
    assert video.read_bytes() == b'burned'
    assert 'Hello' in captured['ass']
    assert os.path.exists(str(tmp_path / 'in.srt'))


def test_burn_captions_png_legacy_path_unaffected(tmp_path, monkeypatch):
    from src.services.video import captions as caps
    from src.services.video.assembly_service import VideoAssemblyService

    svc = VideoAssemblyService()
    svc.output_dir = str(tmp_path)
    svc.working_dir = str(tmp_path)
    video = tmp_path / 'in.mp4'
    video.write_bytes(b'video')
    png = tmp_path / 'c.png'
    png.write_bytes(b'png')

    called = {}

    def fake_run(cmd, **kwargs):
        called['cmd'] = cmd
        return sp.CompletedProcess(cmd, 1, stderr='')

    monkeypatch.setattr(sp, 'run', fake_run)
    monkeypatch.setattr(
        caps, 'burn_ass',
        lambda *a, **k: (_ for _ in ()).throw(AssertionError('should not call burn_ass')),
    )
    captions = [{'text': 'Hi', 'start': 0, 'end': 1, 'path': str(png)}]
    result = svc._burn_captions(str(video), captions, 30)
    assert result == str(video)
    assert '-filter_complex' in called['cmd']
    assert video.read_bytes() == b'video'