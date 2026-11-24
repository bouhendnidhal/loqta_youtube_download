import json
import subprocess
import time
from pathlib import Path
import pytest
import app as application
from media import canonical_url, parse_time, options, convert, MediaError


@pytest.mark.parametrize('url', ['https://youtu.be/BaW_jenozKc?t=4', 'https://www.youtube.com/watch?v=BaW_jenozKc&list=abc', 'https://youtube.com/shorts/BaW_jenozKc'])
def test_urls(url):
    assert canonical_url(url) == 'https://www.youtube.com/watch?v=BaW_jenozKc'


@pytest.mark.parametrize('url', ['file:///etc/passwd', 'https://youtube.com.evil.com/watch?v=BaW_jenozKc', 'https://youtube.com@127.0.0.1/watch?v=BaW_jenozKc', 'https://127.0.0.1/a', 'https://youtube.com/playlist?list=abc', None, 'https://youtube.com:443/watch?v=BaW_jenozKc'])
def test_bad_urls(url):
    with pytest.raises(ValueError): canonical_url(url)


@pytest.mark.parametrize('value,expected', [('01:02:03.5', 3723.5), ('12:34', 754), ('3.5', 3.5), ('', None)])
def test_times(value, expected):
    assert parse_time(value) == expected


@pytest.mark.parametrize('value', ['-1', 'NaN', 'Infinity', '1:60', '1:2:3:4', '1.5:20', [], True])
def test_bad_times(value):
    with pytest.raises(ValueError): parse_time(value)


def test_invalid_range():
    for data in [dict(start='11'), dict(start='5', end='4'), dict(end='20'), dict(kind='exe'), dict(quality='999')]:
        with pytest.raises(ValueError): options(data, 10)


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setattr(application, 'dependencies', lambda: {'ffmpeg': True, 'ffprobe': True, 'node': True})
    monkeypatch.setattr(application, 'inspect_video', lambda url: dict(title='<script>alert(1)</script>', url=url, duration=10, channel='Test', heights=[360], video_id='BaW_jenozKc'))
    def download(info, settings, folder, update):
        folder.mkdir(exist_ok=True)
        result = folder / ('result.' + settings['kind'])
        update(progress=55, stage='testing')
        result.write_bytes(b'test-media')
        return result
    monkeypatch.setattr(application, 'download_video', download)
    app = application.create_app(tmp_path)
    yield app, app.test_client(), {'X-App-Token': app.extensions['token']}
    app.extensions['executor'].shutdown(wait=True)


def test_security(web):
    app, client, headers = web
    assert client.post('/api/inspect', json={'url': 'x'}).status_code == 403
    assert client.post('/api/inspect', json={}, headers={**headers, 'Origin': 'https://evil.test'}).status_code == 403
    assert client.get('/', headers={'Host': 'evil.test'}).status_code == 400
    assert client.post('/api/inspect', json=[], headers=headers).status_code == 400
    assert client.post('/api/inspect', json={'url': 'https://127.0.0.1'}, headers=headers).status_code == 400
    assert client.get('/api/jobs/unknown/file').status_code == 404
    assert 'frame-ancestors' in client.get('/').headers['Content-Security-Policy']


def test_full_lifecycle(web):
    app, client, headers = web
    info = client.post('/api/inspect', json={'url': 'https://youtu.be/BaW_jenozKc'}, headers=headers).json
    response = client.post('/api/jobs', json={'inspection_id': info['inspection_id'], 'kind': 'mp3', 'start': '2', 'end': '4'}, headers=headers)
    assert response.status_code == 202
    job_id = response.json['id']
    app.extensions['executor'].shutdown(wait=True)
    job = client.get('/api/jobs').json[0]
    assert job['status'] == 'done' and job['progress'] == 100
    assert app.extensions['result_path'](job_id).read_bytes() == b'test-media'
    assert app.extensions['result_path']('../outside') is None
    assert client.get(f'/api/jobs/{job_id}/file').data == b'test-media'
    assert client.delete(f'/api/jobs/{job_id}', headers=headers).status_code == 200
    assert client.get('/api/jobs').json == []


def test_preferences_and_output_folder(web, tmp_path):
    app, client, headers = web
    destination = tmp_path / 'chosen'
    destination.mkdir()
    assert client.post('/api/settings', json={'theme': 'blue'}, headers=headers).status_code == 400
    assert client.post('/api/settings', json={'output_folder': str(tmp_path / 'missing')}, headers=headers).status_code == 400
    saved = client.post('/api/settings', json={'theme': 'light', 'output_folder': str(destination)}, headers=headers)
    assert saved.status_code == 200
    assert client.get('/api/settings').json['theme'] == 'light'
    info = client.post('/api/inspect', json={'url': 'https://youtu.be/BaW_jenozKc'}, headers=headers).json
    client.post('/api/jobs', json={'inspection_id': info['inspection_id'], 'kind': 'mp3'}, headers=headers)
    app.extensions['executor'].shutdown(wait=True)
    job = client.get('/api/jobs').json[0]
    assert job['status'] == 'done'
    assert (destination / Path(job['saved_to']).name).read_bytes() == b'test-media'
    assert app.extensions['result_path'](job['id']) == Path(job['saved_to'])
    assert client.get('/api/jobs/' + job['id'] + '/file').data == b'test-media'
    assert json.loads((tmp_path.parent / 'preferences.json').read_text(encoding='utf-8'))['theme'] == 'light'


def test_failure_visible(web, monkeypatch):
    app, client, headers = web
    def fail(*args): raise MediaError('فشل الاتصال\nNetwork failure')
    monkeypatch.setattr(application, 'download_video', fail)
    info = client.post('/api/inspect', json={'url': 'https://youtu.be/BaW_jenozKc'}, headers=headers).json
    client.post('/api/jobs', json={'inspection_id': info['inspection_id']}, headers=headers)
    app.extensions['executor'].shutdown(wait=True)
    job = client.get('/api/jobs').json[0]
    assert job['status'] == 'error'
    assert 'Network failure' in job['error']
    assert client.get(f"/api/jobs/{job['id']}/file").status_code == 404


def test_recovery(tmp_path):
    folder = tmp_path / ('a' * 32)
    folder.mkdir()
    (folder / 'job.json').write_text(json.dumps(dict(id=folder.name, status='working', created=1)), encoding='utf-8')
    app = application.create_app(tmp_path)
    assert app.test_client().get('/api/jobs').json[0]['status'] == 'error'
    app.extensions['executor'].shutdown()


@pytest.mark.parametrize('kind', ['mp4', 'mp3'])
def test_real_ffmpeg_trim(tmp_path, kind):
    source = tmp_path / 'source.mp4'
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=25', '-f', 'lavfi', '-i', 'sine=frequency=440', '-t', '3', '-c:v', 'libx264', '-c:a', 'aac', str(source)], check=True)
    target = tmp_path / ('output.' + kind)
    progress = []
    convert(source, target, options(dict(kind=kind, start='0.5', end='2'), 3), 3, lambda **x: progress.append(x), tmp_path / 'log')
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(target)], capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    assert abs(float(info['format']['duration']) - 1.5) < .12
    assert any(s['codec_type'] == 'audio' for s in info['streams'])
    assert any(s['codec_name'] == ('h264' if kind == 'mp4' else 'mp3') for s in info['streams'])
    assert progress
