"""Isolated yt-dlp worker. A killed worker has no FFmpeg subprocesses."""
import json
import sys
from pathlib import Path
from yt_dlp import YoutubeDL


def main():
    payload = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    info, settings, folder = payload['info'], payload['settings'], Path(payload['folder'])
    def emit(**data):
        print('PROGRESS:' + json.dumps(data), flush=True)
    common = dict(quiet=True, noprogress=True, no_warnings=False, noplaylist=True, socket_timeout=20,
                  retries=3, fragment_retries=3, js_runtimes={'node': {}},
                  fixup='never', skip_unavailable_fragments=False, cachedir=False)
    selector = 'bestaudio/best' if settings['kind'] == 'mp3' else (
        f"bestvideo[height<={settings['quality']}]+bestaudio/best[height<={settings['quality']}]"
    )
    with YoutubeDL({**common, 'format': selector}) as ydl:
        selected = ydl.extract_info(info['url'], download=False)
    streams = selected.get('requested_formats') or [selected]
    paths = []
    for index, stream in enumerate(streams):
        destination = folder / f"source.{index}.{stream['ext']}"
        def hook(progress, index=index):
            total = progress.get('total_bytes') or progress.get('total_bytes_estimate')
            downloaded = progress.get('downloaded_bytes', 0)
            fraction = min(1, downloaded / total) if total else 0
            emit(progress=5 + 65 * (index + fraction) / len(streams),
                 stage=f'تحميل المسار {index + 1} من {len(streams)}',
                 speed=progress.get('speed'), eta=progress.get('eta'),
                 downloaded=downloaded, total=total)
        with YoutubeDL({**common, 'progress_hooks': [hook], 'outtmpl': str(destination)}) as ydl:
            single = dict(stream)
            for key in ('id', 'title', 'webpage_url', 'extractor', 'extractor_key'):
                if key in selected:
                    single[key] = selected[key]
            single.pop('requested_formats', None)
            ydl.process_info(single)
        if not destination.exists():
            raise RuntimeError('The downloaded stream is missing')
        paths.append(str(destination))
    (folder / 'sources.json').write_text(json.dumps(paths), encoding='utf-8')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'inspect':
        from yt_dlp import main as yt_dlp_main
        yt_dlp_main(sys.argv[2:])
    else:
        main()
