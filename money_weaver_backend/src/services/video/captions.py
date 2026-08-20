import os
import subprocess

ASS_HEADER = (
    "[Script Info]\n"
    "Title: MoneyWeaver\n"
    "ScriptType: v4.00+\n"
    "[V4+ Styles]\n"
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
    "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
    "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
    "Style: Default,{font},48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,"
    "100,100,0,0,1,2,0,2,10,10,10,1\n"
    "[Events]\n"
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
)


def _ass_ts(seconds: float) -> str:
    """Seconds -> ASS H:MM:SS.cc timecode."""
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int(seconds % 3600 // 60)
    cent = int(round(seconds % 60 * 100))
    s, c = divmod(cent, 100)
    if s >= 60:
        s, c = 59, 99
    return f"{h}:{m:02}:{s:02}.{c:02}"


def _srt_ts(seconds: float) -> str:
    """Seconds -> SRT HH:MM:SS,mmm timecode."""
    total_ms = int(round(max(0.0, float(seconds)) * 1000))
    h, rem = divmod(total_ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def _quote_filter_value(value: str) -> str:
    """Single-quote a value for use inside an ffmpeg filtergraph option."""
    escaped = str(value).replace('\\', '\\\\').replace("'", "'\\''")
    return f"'{escaped}'"


def build_ass(transcript, niche=None) -> str:
    """Build word-level ASS caption content with niche highlight/font styling.

    transcript: list of faster-whisper words [{word, start, end}]
    niche: dict with optional captions{font, highlight}; highlight color hex
    """
    niche = niche or {}
    highlight = str(niche.get('highlight', '#00FF88'))
    font = str(niche.get('font', 'Arial'))
    color = highlight.lstrip('#').upper() or '00FF88'
    lines = []
    for w in transcript:
        start = _ass_ts(w['start'])
        end = _ass_ts(w['end'])
        word = str(w['word']).replace('\n', ' ')
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{{\\c&{color}&}}{word}")
    return ASS_HEADER.format(font=font) + "\n".join(lines)


def export_srt(transcript) -> str:
    """Build a standard SRT subtitle file from word-level transcript words."""
    blocks = []
    for i, w in enumerate(transcript, 1):
        start = _srt_ts(w['start'])
        end = _srt_ts(w['end'])
        word = str(w['word']).replace('\n', ' ')
        blocks.append(f"{i}\n{start} --> {end}\n{word}")
    return "\n\n".join(blocks) + "\n"


def burn_ass(input_mp4, ass_path, output_mp4=None) -> str:
    """Burn an .ass subtitle file into a video via ffmpeg's libass filter.

    Returns the output mp4 path. Raises subprocess.CalledProcessError if the
    burn fails (e.g. this ffmpeg build lacks libass) so callers can fall back.
    """
    if not output_mp4:
        root, _ = os.path.splitext(str(input_mp4))
        output_mp4 = f"{root}_captioned.mp4"
    subprocess.run(
        [
            'ffmpeg', '-y', '-i', str(input_mp4),
            '-vf', f"ass={_quote_filter_value(ass_path)}",
            '-c:a', 'copy',
            '-movflags', '+faststart',
            str(output_mp4),
        ],
        check=True,
    )
    return output_mp4