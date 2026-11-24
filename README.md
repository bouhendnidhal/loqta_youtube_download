# لقطة 1.0.0

تطبيق Windows لتحميل فيديو YouTube بصيغة MP4 أو استخراج MP3، مع اختيار الجودة وقص المدة ومتابعة التقدم. افتح الملف المكتمل مباشرة أو أظهره في مجلده. الواجهة عربية بخط Cairo.

## تثبيت التطبيق

حمّل وشغّل [Loqta-Setup-1.0.0.exe](https://github.com/bouhendnidhal/loqta_youtube_download/releases/download/version_1.0.0/Loqta-Setup-1.0.0.exe). يضم المثبّت Python وyt-dlp وFFmpeg وFFprobe وNode.js؛ المستخدم لا يثبتها منفصلة. يحتاج البرنامج Windows 64-bit واتصالاً بالإنترنت. قد تحتاج إلى Microsoft Edge WebView2 Runtime إذا لم يكن موجوداً في النظام.

للمزيد عن خطوات التثبيت وإعادة البناء، اقرأ [DESKTOP.md](DESKTOP.md). يشرح [PROJECT_GUIDE_AR.md](PROJECT_GUIDE_AR.md) لغات المشروع ومكوّناته.

## بناء نسخة Windows من المصدر

على جهاز المطوّر، ثبّت Python 3.11+ وFFmpeg وNode.js وInno Setup 6، ثم نفّذ:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
powershell -ExecutionPolicy Bypass -File .\build-desktop.ps1
```

ستجد المثبّت في `release/Loqta-Setup-1.0.0.exe`. يستبعد `.gitignore` بيئة التطوير، مجلدات البناء، السجلات، وتنزيلات المستخدم من ملفات GitHub. ارفع المثبّت في GitHub Releases إذا أردت توزيعه.

## الملفات الأساسية

- `desktop.py`: نافذة Windows وفتح الملفات والمجلدات.
- `app.py`, `media.py`, `worker.py`: مهام التحميل والمعالجة.
- `templates/`, `static/`: الواجهة التي تظهر داخل نافذة التطبيق.
- `installer.iss`, `build-desktop.ps1`: تجميع التطبيق والمثبّت.
- `tests/`: اختبارات المشروع.

الواجهة تستعمل خادماً محلياً على `127.0.0.1` داخل التطبيق. ملفات HTML وCSS وJavaScript جزء من برنامج سطح المكتب، وليست نسخة ويب مستقلة.
