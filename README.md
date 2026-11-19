# Odoo Manager

برنامج لإدارة سيرفرات Odoo اللوكال (odoo-bin و Windows Services).

## التشغيل
- البرنامج الجاهز: `dist\OdooManager.exe`
- من الكود: `.venv\Scripts\python app.py`
- إعادة بناء الـ exe: `powershell -ExecutionPolicy Bypass -File build.ps1`

## المميزات
- تشغيل / إيقاف / إعادة تشغيل لكل سيرفر أو الكل مرة واحدة
- يكتشف سيرفسز Odoo المتسطبة تلقائياً (زي odoo-server-18.0)
- **سيرفر جديد**: ينزّل Odoo من GitHub (أي إصدار) + venv + requirements + odoo.conf + بورت فاضي
- لوج live ملوّن مع فلتر
- تعديل odoo.conf وإعادة تشغيل بعد الحفظ
- قواعد البيانات: عرض، فتح، Backup (zip بصيغة Odoo مع filestore)، Restore، حذف
- فحص تعارض البورتات، ومنع التشغيل لو البورت مشغول
- أيقونة جنب الساعة (Tray) فيها التحكم في كل السيرفرات
- تشغيل مع ويندوز + تشغيل سيرفرات معينة تلقائياً

## ملاحظات
- Odoo 19 محتاج **Python 3.10 – 3.13** (الأفضل 3.12). Python 3.14 غالباً مش هيعرف يسطّب المتطلبات.
- Odoo 19 من الـ source محتاج كمان **wkhtmltopdf** عشان تقارير PDF.
- التحكم في Windows Services بيطلب صلاحية Admin (هيظهرلك UAC).
- البيانات محفوظة في `%APPDATA%\OdooManager` (instances.json, settings.json, logs).
