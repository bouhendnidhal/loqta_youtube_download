import atexit
import json
import logging
import os
import re
import secrets
import shutil
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file
from werkzeug.exceptions import HTTPException
from media import MediaError, canonical_url, dependencies, download_video, inspect_video, options

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
TERMINAL = {'done', 'error'}


def create_app(storage=None):
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=8192, TRUSTED_HOSTS=['localhost', '127.0.0.1', '[::1]'])
    folder = Path(storage) if storage else (Path(os.environ['LOCALAPPDATA']) / 'Loqta' / 'downloads' if getattr(sys, 'frozen', False) else ROOT / 'downloads')
    folder.mkdir(parents=True, exist_ok=True)
    preferences_path = folder.parent / 'preferences.json'
    preferences = {'theme': 'dark', 'output_folder': str(folder.resolve())}
    if preferences_path.exists():
        try:
            loaded = json.loads(preferences_path.read_text(encoding='utf-8'))
            if loaded.get('theme') in ('dark', 'light'):
                preferences['theme'] = loaded['theme']
            if Path(loaded.get('output_folder', '')).is_dir():
                preferences['output_folder'] = str(Path(loaded['output_folder']).resolve())
        except (ValueError, TypeError, OSError):
            logging.exception('Could not load preferences')
    token = secrets.token_urlsafe(32)
    lock = threading.RLock()
    inspection_slots = threading.BoundedSemaphore(2)
    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='download')
    jobs, cache = {}, {}
    app.extensions['jobs'] = jobs
    app.extensions['token'] = token
    app.extensions['executor'] = executor
    app.extensions['preferences'] = preferences
    atexit.register(executor.shutdown, wait=False, cancel_futures=True)
    for path in folder.glob('*/job.json'):
        try:
            job = json.loads(path.read_text(encoding='utf-8'))
            if job['id'] != path.parent.name:
                continue
            if job['status'] not in TERMINAL:
                job.update(status='error', stage='توقفت العملية بعد إغلاق التطبيق. أعد المحاولة.')
            jobs[job['id']] = job
        except (ValueError, KeyError, OSError):
            logging.exception('Could not load saved job')

    def result_path(job_id):
        if not isinstance(job_id, str) or not re.fullmatch(r'[0-9a-f]{32}', job_id):
            return None
        with lock:
            job = jobs.get(job_id)
            if not job or job.get('status') != 'done':
                return None
            saved_to = job.get('saved_to')
            path = Path(saved_to) if saved_to else folder / job_id / ('result.' + job['settings']['kind'])
            return path if path.is_file() else None

    app.extensions['result_path'] = result_path

    def save(job):
        destination = folder / job['id'] / 'job.json'
        destination.parent.mkdir(exist_ok=True)
        temporary = destination.with_suffix('.tmp')
        temporary.write_text(json.dumps(job, ensure_ascii=False), encoding='utf-8')
        temporary.replace(destination)

    @app.before_request
    def protect_local():
        origin = request.headers.get('Origin')
        if origin and origin != request.host_url.rstrip('/'):
            abort(403, description='الطلب جاء من موقع آخر.')
        if request.headers.get('Sec-Fetch-Site') == 'cross-site':
            abort(403)
        if request.method in ('POST', 'DELETE') and not secrets.compare_digest(request.headers.get('X-App-Token', ''), token):
            abort(403, description='حدّث الصفحة ثم أعد المحاولة.')

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.errorhandler(Exception)
    def unexpected(error):
        app.logger.exception('Unexpected request error')
        return jsonify(error='خطأ داخلي. راجع نافذة تشغيل التطبيق.'), 500

    def body():
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            abort(400, description='أرسل بيانات JSON صالحة.')
        return value

    @app.get('/')
    def home():
        return render_template('index.html', token=token)

    @app.get('/api/health')
    def health():
        tools = dependencies()
        return jsonify(ready=all(tools.values()), tools=tools)

    @app.get('/api/settings')
    def get_settings():
        with lock:
            return jsonify(preferences)

    @app.post('/api/settings')
    def set_settings():
        data = body()
        with lock:
            new = dict(preferences)
            if 'theme' in data:
                if data['theme'] not in ('dark', 'light'):
                    return jsonify(error='اختر المظهر الداكن أو الفاتح.'), 400
                new['theme'] = data['theme']
            if 'output_folder' in data:
                candidate = data['output_folder']
                if not isinstance(candidate, str) or not candidate.strip() or not Path(candidate).is_dir():
                    return jsonify(error='اختر مجلداً موجوداً على جهازك.'), 400
                destination = Path(candidate).resolve()
                try:
                    probe = destination / ('.loqta-write-' + uuid.uuid4().hex)
                    probe.write_bytes(b'')
                    probe.unlink()
                except OSError:
                    return jsonify(error='لا يمكن الكتابة في هذا المجلد.'), 400
                new['output_folder'] = str(destination)
            temporary = preferences_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(new, ensure_ascii=False), encoding='utf-8')
            temporary.replace(preferences_path)
            preferences.update(new)
            return jsonify(preferences)

    @app.post('/api/inspect')
    def inspect():
        try:
            url = canonical_url(body().get('url'))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        if not inspection_slots.acquire(blocking=False):
            return jsonify(error='كاين طلبان لتحليل الفيديو. انتظر قليلاً.'), 429
        try:
            info = inspect_video(url)
        except MediaError as error:
            return jsonify(error=str(error)), 422
        finally:
            inspection_slots.release()
        key = uuid.uuid4().hex
        with lock:
            now = time.time()
            for old in list(cache):
                if now - cache[old][0] > 3600:
                    cache.pop(old)
            if len(cache) >= 100:
                cache.pop(next(iter(cache)))
            cache[key] = (now, info)
        return jsonify(**info, inspection_id=key)

    def run(job_id, info, settings):
        def update(**changes):
            with lock:
                job = jobs[job_id]
                if 'progress' in changes:
                    changes['progress'] = max(job['progress'], changes['progress'])
                job.update(changes)
        try:
            update(status='working', stage='قراءة روابط التحميل', progress=2)
            with lock:
                save(jobs[job_id])
            result = download_video(info, settings, folder / job_id, update)
            with lock:
                output_folder = jobs[job_id]['output_folder']
            if Path(output_folder).resolve() != folder.resolve():
                title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', info['title']).strip(' .')[:100] or 'YouTube-video'
                destination = Path(output_folder) / f'{title}-{job_id[:8]}.{settings["kind"]}'
                shutil.copy2(result, destination)
                update(saved_to=str(destination))
            update(status='done', progress=100, stage='الملف جاهز', size=result.stat().st_size, speed=None, eta=None)
        except Exception as error:
            app.logger.exception('Download failed: %s', job_id)
            text = str(error) if isinstance(error, (MediaError, OSError)) else 'حدث خطأ أثناء التحميل. راجع سجل التطبيق.'
            update(status='error', stage=text.split('\n')[0], error=text[-3000:], speed=None, eta=None)
        finally:
            with lock:
                save(jobs[job_id])

    @app.post('/api/jobs')
    def create_job():
        data = body()
        if not all(dependencies().values()):
            return jsonify(error='ثبّت FFmpeg وFFprobe وNode.js ثم أعد تشغيل التطبيق.'), 503
        with lock:
            key = data.get('inspection_id')
            cached = cache.get(key) if isinstance(key, str) else None
            if not cached or time.time() - cached[0] > 3600:
                return jsonify(error='حلّل رابط الفيديو من جديد قبل التحميل.'), 400
            info = cached[1]
            try:
                settings = options(data, info['duration'])
            except ValueError as error:
                return jsonify(error=str(error)), 400
            if sum(job['status'] not in TERMINAL for job in jobs.values()) >= 10:
                return jsonify(error='قائمة الانتظار ممتلئة. انتظر حتى ينتهي تحميل.'), 429
            if shutil.disk_usage(folder).free < 256 * 1024 * 1024:
                return jsonify(error='المساحة الحرة أقل من 256 MB. حرّر مساحة قبل التحميل.'), 507
            job_id = uuid.uuid4().hex
            job = dict(id=job_id, title=info['title'], url=info['url'], settings=settings,
                       status='queued', progress=0, stage='في قائمة الانتظار', created=time.time(),
                       output_folder=preferences['output_folder'])
            jobs[job_id] = job
            save(job)
            executor.submit(run, job_id, dict(info), settings)
        return jsonify(job), 202

    @app.get('/api/jobs')
    def list_jobs():
        with lock:
            return jsonify(sorted(jobs.values(), key=lambda j: j['created'], reverse=True))

    @app.get('/api/jobs/<job_id>/file')
    def file(job_id):
        with lock:
            job = jobs.get(job_id)
            if not job or job['status'] != 'done':
                abort(404, description='الملف غير جاهز.')
            ext = job['settings']['kind']
            # The server chooses the path, never a client-supplied filename.
            path = folder / job_id / ('result.' + ext)
            if not path.is_file():
                abort(404, description='الملف لم يعد موجوداً على القرص.')
            from werkzeug.utils import secure_filename
            name = secure_filename(job['title'])[:120] or 'YouTube-video'
            return send_file(path, as_attachment=True, download_name=name + '.' + ext)

    @app.delete('/api/jobs/<job_id>')
    def delete(job_id):
        with lock:
            job = jobs.get(job_id)
            if not job:
                abort(404)
            if job['status'] not in TERMINAL:
                abort(409, description='انتظر انتهاء العملية قبل حذفها.')
            target = (folder / job_id).resolve()
            if target.parent != folder.resolve():
                abort(400)
            if target.exists():
                shutil.rmtree(target)
            jobs.pop(job_id)
        return jsonify(ok=True)

    return app


if __name__ == '__main__':
    from waitress import serve
    port = int(os.environ.get('PORT', '8080'))
    print(f'YouTube Local: http://127.0.0.1:{port}', flush=True)
    serve(create_app(), host='127.0.0.1', port=port, threads=6)
