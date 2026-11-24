"""Desktop shell for the unchanged local application."""
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path

import webview
from waitress import create_server
from app import create_app


def main():
    if getattr(sys, 'frozen', False):
        os.environ['PATH'] = str(Path(sys.executable).parent / 'tools') + os.pathsep + os.environ.get('PATH', '')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    app = create_app()
    server = create_server(app, host='127.0.0.1', port=port, threads=6)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    class DesktopApi:
        def choose_folder(self):
            result = window.create_file_dialog(webview.FOLDER_DIALOG)
            return result[0] if result else None

        def show_in_folder(self, job_id):
            path = app.extensions['result_path'](job_id)
            if path is None:
                return {'ok': False, 'error': 'الملف غير موجود في مكان حفظه.'}
            try:
                subprocess.Popen(['explorer.exe', '/select,', str(path)],
                                 creationflags=subprocess.CREATE_NO_WINDOW)
                return {'ok': True}
            except OSError:
                return {'ok': False, 'error': 'تعذّر فتح مجلد الملف.'}

        def open_file(self, job_id):
            path = app.extensions['result_path'](job_id)
            if path is None:
                return {'ok': False, 'error': 'الملف غير موجود في مكان حفظه.'}
            try:
                os.startfile(path)
                return {'ok': True}
            except OSError:
                return {'ok': False, 'error': 'تعذّر فتح الملف.'}

    window = webview.create_window('لقطة | YouTube Local', f'http://127.0.0.1:{port}', width=1160, height=800, min_size=(780, 580), js_api=DesktopApi())
    try:
        webview.start(gui='edgechromium')
    finally:
        server.close()


if __name__ == '__main__':
    main()
