# نسخة Windows

الإصدار الحالي هو `release\Loqta-Setup-1.0.0.exe`. تعرض قائمة الملفات زرين لفتح الملف وإظهاره في مجلده. تستعمل الواجهة خط Cairo، ويظهر علم الجزائر بجانب روابط المطوّر.

شغّل `Loqta-Setup-1.0.0.exe` وثبّت البرنامج. بعد التثبيت تلقى **Loqta** في قائمة Start، وتقدر تختار اختصار سطح المكتب. تفتح الواجهة داخل نافذة برنامج مستقلة. التحميل يحتاج اتصالاً بالإنترنت، والملفات تُحفظ على جهازك.

المثبّت يضم Python وyt-dlp وFFmpeg وFFprobe وNode.js. ما تحتاجش تثبت هذه الأدوات يدوياً على الحاسوب الذي يستعمل البرنامج. Windows WebView2 لازم يكون متوفراً للنوافذ؛ أغلب أنظمة Windows الحديثة تثبته مسبقاً. نتائج التحميل توجد في `%LOCALAPPDATA%\Loqta\downloads` وتبقى عند إزالة البرنامج حتى لا تضيع ملفاتك.

## إعادة بناء المثبّت

على Windows، ثبّت Python 3.11+ وFFmpeg وNode.js و[Inno Setup 6](https://jrsoftware.org/inno-setup). داخل مجلد المشروع:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
powershell -ExecutionPolicy Bypass -File .\build-desktop.ps1
```

النتيجة في `release\Loqta-Setup-1.0.0.exe`. مسار Inno Setup في `build-desktop.ps1` يطابق التثبيت الحالي؛ عدّله إذا ثبّت البرنامج في مكان آخر.

التطبيق يحتفظ بعمليات التحميل والتقطيع نفسها. ملفات `desktop.py` و`installer.iss` و`build-desktop.ps1` تضيف النافذة والتثبيت. التعديلات في `app.py` و`media.py` و`worker.py` تختار مجلد بيانات قابل للكتابة وتشغّل أدوات yt-dlp المجمّعة عند العمل كملف EXE. تستعمل الواجهة خط Cairo المضمّن في `static/fonts`.

## تحقق النسخة الجاهزة

في 24 نوفمبر 2026، اجتاز المشروع 30 اختباراً آلياً وفحص صياغة JavaScript وPython. نجح بناء مثبت 1.0.0، وتأكدنا من وجود `Loqta.exe` و`LoqtaWorker.exe` وFFmpeg وFFprobe وNode.js وخط Cairo ورخصته داخل ملفات الحزمة. تحقّقنا من بيانات المثبت التي تعرض رقم المنتج 1.0.0. جُرّبت عمليات تحميل وقص MP3 في نسخة EXE السابقة؛ لم نكرر تحميل فيديو فعلي لهذه النسخة.
