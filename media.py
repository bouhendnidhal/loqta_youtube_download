"""YouTube inspection, bounded downloads and accurate FFmpeg conversion."""
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse


class MediaError(Exception):
    pass


def canonical_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError('أدخل رابط YouTube صالح.')
    parsed = urlparse(value.strip())
    if parsed.scheme not in ('https', 'http') or parsed.username or parsed.password:
        raise ValueError('استعمل رابط http أو https من YouTube.')
    host = parsed.netloc.lower()
    if host == 'youtu.be':
        video_id = parsed.path.strip('/')
    elif host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'):
        parts = parsed.path.strip('/').split('/')
        video_id = parse_qs(parsed.query).get('v', [''])[0] if parsed.path == '/watch' else (
            parts[1] if len(parts) == 2 and parts[0] in ('shorts', 'embed', 'live') else '')
    else:
        raise ValueError('هذه الأداة تقبل روابط YouTube فقط.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
        raise ValueError('الرابط لازم يشير لفيديو واحد، وليس قائمة تشغيل.')
    return 'https://www.youtube.com/watch?v=' + video_id


def parse_time(value):
    if value is None or value == '':
        return None
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise ValueError('الوقت يكون بالثواني أو HH:MM:SS.')
    parts = str(value).strip().split(':')
    if not 1 <= len(parts) <= 3 or any(not re.fullmatch(r'\d+(?:\.\d+)?', p) for p in parts):
        raise ValueError('الوقت يكون بالثواني أو HH:MM:SS.')
    numbers = [float(p) for p in parts]
    if len(parts) > 1 and (any(n >= 60 for n in numbers[1:]) or any('.' in p for p in parts[:-1])):
        raise ValueError('الدقائق والثواني بعد النقطتين لازم تكون أقل من 60.')
    result = sum(n * 60 ** i for i, n in enumerate(reversed(numbers)))
    if not math.isfinite(result):
        raise ValueError('وقت غير صالح.')
    return result


def options(data, duration):
    kind = data.get('kind', 'mp4')
    if kind not in ('mp4', 'mp3'):
        raise ValueError('اختر MP4 أو MP3.')
    quality = str(data.get('quality', '1080'))
    if quality not in ('144', '240', '360', '480', '720', '1080', '1440', '2160', '4320'):
        raise ValueError('جودة فيديو غير صالحة.')
    bitrate = str(data.get('bitrate', '192'))
    if bitrate not in ('128', '192', '256', '320'):
        raise ValueError('جودة صوت غير صالحة.')
    start = parse_time(data.get('start')) or 0
    end = parse_time(data.get('end'))
    if start >= duration or (end is not None and (end <= start or end > duration + 0.05)):
        raise ValueError('البداية لازم تكون قبل النهاية، والمدة داخل طول الفيديو.')
    return dict(kind=kind, quality=int(quality), bitrate=int(bitrate), start=start, end=end)


def dependencies():
    return {name: bool(shutil.which(name)) for name in ('ffmpeg', 'ffprobe', 'node')}


def base_command():
    prefix = [str(Path(sys.executable).with_name('LoqtaWorker.exe')), 'inspect'] if getattr(sys, 'frozen', False) else [sys.executable, '-m', 'yt_dlp']
    return prefix + ['--ignore-config', '--no-plugin-dirs',
            '--no-playlist', '--no-colors', '--socket-timeout', '20', '--retries', '3',
            '--fragment-retries', '3', '--js-runtimes', 'node']


def friendly_error(raw):
    low = raw.lower()
    if 'sign in' in low or 'bot' in low:
        return 'YouTube طلب تسجيل الدخول أو التحقق. جرّب تحديث yt-dlp أو فيديو عمومي آخر.'
    if 'private' in low or 'unavailable' in low or 'removed' in low:
        return 'الفيديو خاص، محذوف، أو غير متاح من اتصالك.'
    if '403' in low:
        return 'YouTube رفض رابط التحميل (403). حدّث yt-dlp ثم أعد المحاولة.'
    if '429' in low:
        return 'YouTube قيّد الطلبات مؤقتاً. انتظر قبل إعادة المحاولة.'
    if any(s in low for s in ('resolve', 'timed out', 'network', 'connection')):
        return 'تعذّر الاتصال. راجع الإنترنت ثم أعد المحاولة.'
    if 'requested format' in low:
        return 'الجودة المطلوبة غير متاحة لهذا الفيديو. جرّب جودة أخرى.'
    if 'space' in low:
        return 'المساحة على القرص لا تكفي. حرّر مساحة ثم أعد المحاولة.'
    return 'تعذّر إكمال العملية. افتح التفاصيل لمعرفة السبب.'


def inspect_video(url):
    try:
        result = subprocess.run(base_command() + ['--dump-single-json', '--skip-download', '--', url],
                                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=90,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    except subprocess.TimeoutExpired as exc:
        raise MediaError('انتهت مهلة قراءة الفيديو. راجع الاتصال وأعد المحاولة.') from exc
    if result.returncode:
        raise MediaError(friendly_error(result.stderr) + '\n' + result.stderr[-1800:])
    info = json.loads(result.stdout)
    duration = info.get('duration')
    if info.get('is_live') or info.get('live_status') == 'is_upcoming' or not duration:
        raise MediaError('استعمل فيديو منشور بمدة محددة. البث المباشر غير مدعوم.')
    heights = sorted({f['height'] for f in info.get('formats', []) if f.get('height') and f.get('vcodec') != 'none'})
    return dict(url=url, title=info.get('title', 'YouTube video'), duration=float(duration),
                channel=info.get('channel', ''), heights=heights, video_id=info['id'])


def stream_process(command, line_handler, log_path, timeout=7200):
    """Separate processes permit a hard time bound; no shell or user-built commands."""
    import threading
    with open(log_path, 'w', encoding='utf-8') as log:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=log,
                                   text=True, encoding='utf-8', errors='replace',
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        expired = threading.Event()
        def stop():
            expired.set()
            process.kill()
        timer = threading.Timer(timeout, stop)
        timer.daemon = True
        timer.start()
        try:
            for line in process.stdout:
                line_handler(line.strip())
            code = process.wait()
        finally:
            timer.cancel()
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
    if expired.is_set():
        raise MediaError('انتهت المهلة القصوى للعملية (ساعتان). جرّب فيديو أقصر.')
    if code:
        raw = Path(log_path).read_text(encoding='utf-8')[-2400:]
        raise MediaError(friendly_error(raw) + '\n' + raw)


def convert(source, target, settings, duration, update, log_path):
    start, end = settings['start'], settings['end']
    length = (end if end is not None else duration) - start
    command = ['ffmpeg', '-hide_banner', '-nostdin', '-y', '-ss', str(start), '-i', str(source), '-t', str(length)]
    if settings['kind'] == 'mp3':
        command += ['-map', '0:a:0', '-vn', '-c:a', 'libmp3lame', '-b:a', f"{settings['bitrate']}k"]
    else:
        command += ['-map', '0:v:0', '-map', '0:a:0?', '-c:v', 'libx264', '-preset', 'fast',
                    '-crf', '20', '-pix_fmt', 'yuv420p', '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                    '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart']
    command += ['-progress', 'pipe:1', '-nostats', str(target)]
    def progress(line):
        if line.startswith('out_time_us='):
            try:
                seconds = int(line.split('=', 1)[1]) / 1_000_000
                update(progress=min(99, 70 + 29 * seconds / length), stage='تحويل وتقطيع بـFFmpeg')
            except ValueError:
                pass
    stream_process(command, progress, log_path)
    if not target.is_file() or target.stat().st_size == 0:
        raise MediaError('FFmpeg لم ينتج ملفاً صالحاً.')


def download_video(info, settings, folder, update):
    folder.mkdir(parents=True, exist_ok=True)
    # Download separate streams without spawning FFmpeg inside yt-dlp.
    # Conversion is performed below, with its own measured progress and timeout.
    # A custom postprocessor-free worker downloads streams via the Python API.
    payload = dict(info=info, settings=settings, folder=str(folder))
    request_path = folder / 'request.json'
    request_path.write_text(json.dumps(payload), encoding='utf-8')
    def on_line(line):
        if line.startswith('PROGRESS:'):
            try:
                data = json.loads(line[9:])
                update(**data)
            except (ValueError, TypeError):
                pass
    worker_command = ([str(Path(sys.executable).with_name('LoqtaWorker.exe'))] if getattr(sys, 'frozen', False) else [sys.executable, str(Path(__file__).with_name('worker.py'))])
    stream_process(worker_command + [str(request_path)],
                   on_line, folder / 'download.log')
    sources = json.loads((folder / 'sources.json').read_text(encoding='utf-8'))
    target = folder / ('result.' + settings['kind'])
    if len(sources) == 2:
        # Merge locally before transcoding, keeping the final transform simple.
        merged = folder / 'merged.mkv'
        stream_process(['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', sources[0], '-i', sources[1],
                        '-map', '0:v:0', '-map', '1:a:0', '-c', 'copy', str(merged)],
                       lambda line: None, folder / 'merge.log')
        source = merged
    else:
        source = Path(sources[0])
    update(progress=70, stage='تحويل وتقطيع بـFFmpeg')
    convert(source, target, settings, info['duration'], update, folder / 'convert.log')
    for path in folder.iterdir():
        if path.name.startswith('source.') or path.name in ('merged.mkv', 'request.json', 'sources.json'):
            path.unlink(missing_ok=True)
    return target
