"""Build guide_ar.html: same design as guide.html, right-to-left, Arabic content, Arabic screenshots."""
import re
src = open("guide.html", encoding="utf-8").read()
css = re.search(r"<style>(.*?)</style>", src, re.S).group(1)

# right-to-left adjustments
css = css.replace('font-family: "Segoe UI", "Segoe UI Variable", Arial, sans-serif;',
                  'font-family: "Segoe UI", Tahoma, Arial, sans-serif;')
css = css.replace("th { text-align: left;", "th { text-align: right;")
css = css.replace("padding: 0 0 3mm 11mm;", "padding: 0 11mm 3mm 0;")
css = css.replace("position: absolute; left: 0; top: -.3mm;", "position: absolute; right: 0; top: -.3mm;")
css = css.replace("border-left: 1.2mm solid var(--teal);", "border-right: 1.2mm solid var(--teal);")
css = css.replace("border-radius: 0 2mm 2mm 0;", "border-radius: 2mm 0 0 2mm;")
css = css.replace('.flow div:not(:last-child)::after { content: "›"; position: absolute; right: -2.4mm;',
                  '.flow div:not(:last-child)::after { content: "‹"; position: absolute; left: -2.4mm;')
css = css.replace(".cover .by { position: absolute; top: 26mm; right: 20mm; text-align: right;",
                  ".cover .by { position: absolute; top: 26mm; left: 20mm; text-align: left;")
css = css.replace(".toc b { color: var(--primary); margin-right: 3mm; }", ".toc b { color: var(--primary); margin-left: 3mm; }")
css += """
  .kicker { letter-spacing: 0; }
  .ltr { direction: ltr; unicode-bidi: embed; }
  code, .mono { direction: ltr; unicode-bidi: embed; }
  .cover h1 { letter-spacing: 0; }
  body { font-size: 11pt; }
"""

FOOT = '<div class="foot"><span>Odoo Manager · دليل المستخدم</span><span>Powered by <b>Hossam Ramadan</b> · {n}</span></div>'

body = f"""
<!-- 1. الغلاف -->
<section class="page cover">
  <div class="inner">
    <div class="logo"><i></i></div>
    <div class="by">Powered by<b>Hossam Ramadan</b></div>
    <h1 class="ltr" style="text-align:right">Odoo Manager</h1>
    <div class="tag">برنامج واحد على سطح المكتب لتشغيل كل خوادم Odoo على جهازك ومتابعتها ونسخها احتياطياً وتوسيعها.</div>
    <div class="meta">
      <span class="chip">دليل المستخدم</span><span class="chip">الإصدار 1.1.0</span>
      <span class="chip">ويندوز 10 / 11</span><span class="chip">العربية · English</span>
    </div>
  </div>
  <div class="shot"><img src="img_ar/main_dark_tab0.png"></div>
</section>

<!-- 2. نظرة عامة -->
<section class="page">
  <div class="kicker">نظرة عامة</div>
  <h2>لماذا Odoo Manager</h2>
  <p class="lead">يتعامل المطوّرون ومنفّذو Odoo على ويندوز مع الخوادم من سطر الأوامر: تعديل <code>odoo.conf</code> يدوياً،
    والبحث عن ملفات السجل، وأخذ النسخ الاحتياطية من صفحة قواعد البيانات، وتعارض المنافذ بين الإصدارات.
    يجمع Odoo Manager كل ذلك في نافذة واحدة.</p>

  <div class="grid3">
    <div class="card"><div class="ic">▶</div><h4>التحكم في كل الخوادم</h4><p>خدمات ويندوز وخوادم odoo-bin جنباً إلى جنب: تشغيل وإيقاف وإعادة تشغيل وفتح في المتصفح.</p></div>
    <div class="card"><div class="ic">≡</div><h4>السجل والإعدادات</h4><p>سجل مباشر ملوّن مع فلترة، ومحرر لملف <code>odoo.conf</code> يحفظ بصلاحيات المسؤول عند الحاجة.</p></div>
    <div class="card"><div class="ic">⛁</div><h4>قواعد البيانات</h4><p>نسخ احتياطي واستعادة وحذف بصيغة Odoo نفسها، مع نسخ احتياطي تلقائي يومي.</p></div>
    <div class="card"><div class="ic">+</div><h4>الوحدات (Modules)</h4><p>أضف وحدة من مجلد أو ملف zip، ثم ثبّتها أو حدّثها دون استخدام سطر الأوامر.</p></div>
    <div class="card"><div class="ic">★</div><h4>معالج الخادم الجديد</h4><p>يفحص Git و Python و PostgreSQL، ويثبّت الناقص منها، ثم ينزّل Odoo ويجهّز البيئة.</p></div>
    <div class="card"><div class="ic">◐</div><h4>مصمَّم للاستخدام اليومي</h4><p>عربي وإنجليزي، وضع فاتح وداكن، أيقونة بجوار الساعة، تشغيل مع ويندوز، وتنبيه عند التوقف.</p></div>
  </div>

  <h3 style="margin-top:9mm">المحتويات</h3>
  <div class="toc">
    <div><span><b>1</b>التثبيت</span><span>3</span></div>
    <div><span><b>2</b>أول تشغيل</span><span>4</span></div>
    <div><span><b>3</b>النافذة الرئيسية</span><span>5</span></div>
    <div><span><b>4</b>السجل والإعدادات</span><span>6</span></div>
    <div><span><b>5</b>قواعد البيانات</span><span>7</span></div>
    <div><span><b>6</b>الوحدات المخصصة</span><span>8</span></div>
    <div><span><b>7</b>معالج الخادم الجديد</span><span>9</span></div>
    <div><span><b>8</b>الإعدادات والتشغيل التلقائي</span><span>10</span></div>
    <div><span><b>9</b>حل المشكلات والأسئلة الشائعة</span><span>11</span></div>
    <div><span><b>10</b>مرجع سريع</span><span>12</span></div>
  </div>
  {FOOT.format(n=2)}
</section>

<!-- 3. التثبيت -->
<section class="page">
  <div class="kicker">الفصل 1</div>
  <h2>التثبيت</h2>
  <p class="lead">ملف تثبيت واحد بحجم 54 ميجابايت تقريباً. البرنامج نفسه لا يحتاج إلى Python أو أي برامج إضافية ليعمل.</p>
  <table>
    <tr><th>المتطلب</th><th>التفاصيل</th></tr>
    <tr><td>نظام التشغيل</td><td>ويندوز 10 أو ويندوز 11، 64 بت</td></tr>
    <tr><td>ملف التثبيت</td><td><code>OdooManager-Setup-1.1.0.exe</code> (≈ 54 ميجابايت)</td></tr>
    <tr><td>المساحة</td><td>≈ 60 ميجابايت للبرنامج، وكل خادم Odoo جديد يحتاج ≈ 2 جيجابايت</td></tr>
    <tr><td>لإنشاء خوادم جديدة</td><td>Git و Python من 3.10 إلى 3.13 و PostgreSQL — يفحصها المعالج ويثبّتها لك</td></tr>
  </table>
  <h3>التثبيت في أربع خطوات</h3>
  <ol class="steps">
    <li>شغّل الملف <code>OdooManager-Setup-1.1.0.exe</code>.</li>
    <li>إذا ظهرت رسالة Windows SmartScreen الزرقاء «Windows protected your PC»، اضغط <b>More info</b> ثم <b>Run anyway</b>.</li>
    <li>اختر لغة التثبيت، وحدّد <b>إنشاء اختصار على سطح المكتب</b> إن أردت، ثم اضغط <b>Install</b>.</li>
    <li>اترك خيار <b>تشغيل Odoo Manager</b> محدداً واضغط <b>Finish</b>.</li>
  </ol>
  <div class="note warn"><b>لماذا تظهر رسالة SmartScreen؟</b> لأن ملف التثبيت غير موقّع رقمياً حتى الآن، فلا يتعرّف ويندوز على الناشر.
    يُثبَّت البرنامج في <code>Program Files\\OdooManager</code> أو في مجلد المستخدم، ويمكن إزالته في أي وقت.</div>
  <h3>إلغاء التثبيت</h3>
  <p>إعدادات ويندوز ← التطبيقات ← <b>Odoo Manager</b> ← Uninstall. لا يمسّ إلغاء التثبيت خوادم Odoo ولا قواعد البيانات،
    وتبقى قائمة الخوادم والإعدادات في <code>%APPDATA%\\OdooManager</code> في حال أعدت التثبيت.</p>
  {FOOT.format(n=3)}
</section>

<!-- 4. أول تشغيل -->
<section class="page">
  <div class="kicker">الفصل 2</div>
  <h2>أول تشغيل</h2>
  <p class="lead">تظهر جولة ترحيبية من ثلاث صفحات عند أول تشغيل. وفي الوقت نفسه يكتشف البرنامج خدمات Odoo المثبّتة على الجهاز ويحدد مكان PostgreSQL تلقائياً.</p>
  <div class="grid3">
    <div><div class="shot"><img src="img_ar/welcome1.png"></div><p class="cap">1 · ماذا يفعل البرنامج</p></div>
    <div><div class="shot"><img src="img_ar/welcome2.png"></div><p class="cap">2 · أضف خادمك الأول</p></div>
    <div><div class="shot"><img src="img_ar/welcome3.png"></div><p class="cap">3 · الاستخدام اليومي</p></div>
  </div>
  <h3>أضف خادمك الأول</h3>
  <table>
    <tr><th>لديك…</th><th>ماذا تفعل</th></tr>
    <tr><td>Odoo مثبّت من ملف exe الرسمي</td><td>لا شيء — يظهر في القائمة تلقائياً. ثبّتّه بعد فتح البرنامج؟ استخدم <b>⋯ ← اكتشاف خدمات ويندوز</b>.</td></tr>
    <tr><td>لا شيء بعد</td><td>اضغط <b>خادم جديد</b> واتبع المعالج (الفصل 7).</td></tr>
    <tr><td>خادم odoo-bin جاهز</td><td><b>⋯ ← إضافة خادم موجود</b>، ثم حدّد Python و <code>odoo-bin</code> و <code>odoo.conf</code>.</td></tr>
  </table>
  <div class="note">يمكن فتح الجولة مرة أخرى من <b>ⓘ عن البرنامج ← دليل البدء</b>. يعمل البرنامج بنسخة واحدة فقط؛ وتشغيله مرة ثانية يُظهر النافذة المفتوحة.</div>
  {FOOT.format(n=4)}
</section>

<!-- 5. النافذة الرئيسية -->
<section class="page">
  <div class="kicker">الفصل 3</div>
  <h2>النافذة الرئيسية</h2>
  <p class="lead">الخوادم على الجانب، والخادم المختار في المنتصف. تتحدّث الحالة والمنفذ ورقم العملية والذاكرة ومدة التشغيل كل بضع ثوانٍ.</p>
  <div class="shot clip"><img src="img_ar/main_tab0.png"></div>
  <p class="cap">تبويب «نظرة عامة» لخدمة Odoo 19.</p>
  <table>
    <tr><th>الأداة</th><th>وظيفتها</th></tr>
    <tr><td>تشغيل · إيقاف · إعادة تشغيل</td><td>التحكم في الخادم. خدمات ويندوز تطلب صلاحيات المسؤول (UAC). قبل تشغيل خادم odoo-bin يفحص البرنامج المنفذ ويذكر اسم البرنامج الذي يستخدمه.</td></tr>
    <tr><td>فتح في المتصفح</td><td>يفتح <code>http://localhost:&lt;port&gt;</code>. النقر المزدوج على الخادم في القائمة يفعل الشيء نفسه.</td></tr>
    <tr><td>قائمة ⋯</td><td>تعديل، فتح المجلد، إضافة وحدة وتحديثها، فتح مجلد الوحدات المخصصة، نسخ كلمة المرور الرئيسية، حذف.</td></tr>
    <tr><td>فحص المنافذ</td><td>يعرض منفذ كل خادم وينبّه إلى التعارض بينها أو مع برامج أخرى.</td></tr>
    <tr><td>الشريط العلوي</td><td>تبديل اللغة، الوضع الفاتح والداكن، الإعدادات، عن البرنامج.</td></tr>
  </table>
  {FOOT.format(n=5)}
</section>

<!-- 6. السجل والإعدادات -->
<section class="page">
  <div class="kicker">الفصل 4</div>
  <h2>السجل والإعدادات</h2>
  <p class="lead">تابع ما يفعله Odoo لحظة بلحظة، وغيّر إعداداته دون فتح محرر نصوص.</p>
  <div class="shot clip"><img src="img_ar/main_tab1.png"></div>
  <p class="cap">تبويب «السجل» — ملوّن حسب مستوى الرسالة، مع متابعة تلقائية ومربع فلترة (مثلاً <code>ERROR</code>).</p>
  <div class="shot clip" style="margin-top:5mm"><img src="img_ar/main_tab2.png"></div>
  <p class="cap">تبويب «الإعدادات» — عدّل <code>odoo.conf</code> مباشرة. عند الحفظ يعرض البرنامج إعادة تشغيل الخادم لتطبيق التعديل.</p>
  <div class="note">ملفات الإعدادات داخل <code>Program Files</code> محمية في ويندوز. يحفظها Odoo Manager عبر نافذة صلاحيات UAC، فلا تحتاج أبداً إلى «Run as administrator».</div>
  {FOOT.format(n=6)}
</section>

<!-- 7. قواعد البيانات -->
<section class="page">
  <div class="kicker">الفصل 5</div>
  <h2>قواعد البيانات</h2>
  <p class="lead">يعمل النسخ الاحتياطي والاستعادة والحذف مباشرة على PostgreSQL دون الحاجة إلى كلمة المرور الرئيسية، وبصيغة zip الخاصة بـ Odoo، فتنتقل النسخ بحرية بين Odoo Manager وصفحة قواعد البيانات في Odoo.</p>
  <div class="shot clip"><img src="img_ar/main_tab3.png"></div>
  <p class="cap">تبويب «قواعد البيانات» — لكل قاعدة زر حذف خاص بها.</p>
  <table>
    <tr><th>العملية</th><th>كيف</th><th>ملاحظات</th></tr>
    <tr><td>نسخة احتياطية</td><td>اختر القاعدة ← نسخة احتياطية</td><td>ملف zip يضم <code>dump.sql</code> و filestore، يُحفظ في مجلد النسخ الاحتياطية</td></tr>
    <tr><td>استعادة</td><td>استعادة ← اختر الملف ← اسم جديد</td><td>يقبل zip و dump و backup و sql، ويرفض اسماً موجوداً</td></tr>
    <tr><td>حذف</td><td>زر حذف بجانب القاعدة ← اكتب اسمها للتأكيد</td><td>نهائي، ويعمل حتى والخادم يعمل</td></tr>
    <tr><td>فتح</td><td>نقر مزدوج على القاعدة</td><td>يفتحها في المتصفح</td></tr>
    <tr><td>نسخ تلقائي يومي</td><td>الإعدادات ← التشغيل التلقائي</td><td>كل قاعدة على خادم يعمل، مرة يومياً، مع الاحتفاظ بآخر N نسخة (7 افتراضياً)</td></tr>
  </table>
  <div class="note warn">نسخة من إصدار Odoo أقدم تُستعاد بنجاح، لكن الخادم الأحدث لا يفتحها قبل ترقيتها عبر خدمة الترقية الرسمية من Odoo.</div>
  {FOOT.format(n=7)}
</section>

<!-- 8. الوحدات -->
<section class="page">
  <div class="kicker">الفصل 6</div>
  <h2>الوحدات المخصصة</h2>
  <p class="lead">أضف وحدة بنقرتين. ينسخها Odoo Manager إلى مجلد الوحدات المخصصة ويعيد تشغيل الخادم، ثم تثبّتها أنت من قائمة Apps في Odoo.</p>
  <div class="flow">
    <div><b>⋯ ← إضافة وحدة</b>اختر مجلداً أو ملف zip</div>
    <div><b>النسخ</b>إلى مجلد الوحدات المخصصة</div>
    <div><b>إعادة التشغيل</b>تلقائياً</div>
    <div><b>Apps</b>Update Apps List</div>
    <div><b>Install</b>تثبيت الوحدة</div>
  </div>
  <h3>مجلد الوحدات المخصصة</h3>
  <p>يستخدم البرنامج المجلد الموجود في <code>addons_path</code> الذي يحتوي اسمه على كلمة <i>custom</i> (أو آخر مجلد غير أساسي).
    وإذا لم يوجد — كما في نسخة exe الرسمية — يعرض إنشاء مجلد ويضيفه إلى <code>addons_path</code> تلقائياً:</p>
  <table>
    <tr><th>نوع الخادم</th><th>المجلد المقترح</th></tr>
    <tr><td>أُنشئ بالمعالج</td><td><code>&lt;مجلد الخادم&gt;\\custom_addons</code> (مُعدّ مسبقاً)</td></tr>
    <tr><td>نسخة exe الرسمية (Program Files)</td><td><code>%USERPROFILE%\\Odoo\\custom_addons</code></td></tr>
    <tr><td>أي نوع آخر</td><td><code>custom_addons</code> بجوار <code>odoo.conf</code>، أو مجلد تختاره</td></tr>
  </table>
  <h3>تحديث وحدة</h3>
  <p><b>⋯ ← تحديث وحدة (Upgrade)</b>، اختر قاعدة البيانات واكتب اسم الوحدة. يشغّل البرنامج التحديث في الخلفية، ويعرض أي أخطاء من السجل، ثم يعيد تشغيل الخادم.</p>
  <div class="note">يجب أن تكون الوحدة لنفس إصدار Odoo (قيمة <code>version</code> في <code>__manifest__.py</code> تبدأ بـ <code>19.0</code> لـ Odoo 19)، وأن تكون كل الوحدات المذكورة في <code>depends</code> متوفرة.</div>
  {FOOT.format(n=8)}
</section>

<!-- 9. المعالج -->
<section class="page">
  <div class="kicker">الفصل 7</div>
  <h2>معالج الخادم الجديد</h2>
  <p class="lead">من لا شيء إلى خادم Odoo يعمل — يفحص المعالج المتطلبات، وينزّل Odoo من GitHub، وينشئ بيئة افتراضية، ويكتب <code>odoo.conf</code>. استغرق إنشاء خادم Odoo 19 جديد نحو 3 دقائق في الاختبار.</p>
  <div class="grid2" style="grid-template-columns: 1.05fr 1fr; align-items:start">
    <div><div class="shot"><img src="img_ar/wizard.png"></div><p class="cap">لوحة المتطلبات: العناصر الناقصة يظهر بجانبها زر <b>تثبيت</b>.</p></div>
    <div>
      <h3 style="margin-top:0">فحص المتطلبات</h3>
      <table>
        <tr><th>العنصر</th><th>زر التثبيت</th></tr>
        <tr><td>Git</td><td>يثبّت Git بصمت</td></tr>
        <tr><td>Python 3.10 – 3.13</td><td>يثبّت Python 3.12</td></tr>
        <tr><td>PostgreSQL</td><td>يثبّت PostgreSQL 16، ويطلب كلمة مرور، وينشئ مستخدم <code>odoo</code></td></tr>
      </table>
      <p style="font-size:10pt;color:var(--muted)">يتم التثبيت عبر <b>winget</b> من مايكروسوفت، ويظهر شريط تقدّم مع الوقت المنقضي ورسالة عند الانتهاء. إذا كان موقع EnterpriseDB غير متاح من شبكتك، يُنزَّل PostgreSQL من GitHub تلقائياً.</p>
      <h3>بعد ذلك</h3>
      <ol class="steps">
        <li>اكتب اسم الخادم، واختر الإصدار والنسخة والمجلد.</li>
        <li>تأكّد من Python ومنفذ HTTP (يُقترح منفذ متاح).</li>
        <li>أدخل مستخدم PostgreSQL وكلمة مروره.</li>
        <li>اضغط <b>ابدأ التجهيز</b> وتابع سير العمل.</li>
      </ol>
    </div>
  </div>
  <div class="note"><b>Community أو Enterprise.</b> يتطلب Enterprise اشتراكاً أو صلاحية شريك على <code>github.com/odoo/enterprise</code>. أدخل رابط المستودع أو مجلداً موجوداً، ويضعه المعالج أولاً في <code>addons_path</code>. تُولَّد كلمة المرور الرئيسية وتُحفظ في <code>odoo.conf</code> (<code>admin_passwd</code>).</div>
  {FOOT.format(n=9)}
</section>

<!-- 10. الإعدادات -->
<section class="page">
  <div class="kicker">الفصل 8</div>
  <h2>الإعدادات والتشغيل التلقائي</h2>
  <p class="lead">اضبطها مرة واحدة واتركها تعمل. إغلاق النافذة يُبقي Odoo Manager بجوار الساعة، ومنها يمكن تشغيل أي خادم أو إيقافه أو فتحه بالنقر بزر الفأرة الأيمن.</p>
  <div class="grid2" style="align-items:start">
    <div><div class="shot"><img src="img_ar/settings.png"></div><p class="cap">نافذة الإعدادات.</p></div>
    <div>
      <table>
        <tr><th>الإعداد</th><th>التأثير</th></tr>
        <tr><td>مسار PostgreSQL bin</td><td>أدوات النسخ الاحتياطي والاستعادة (يُكتشف تلقائياً)</td></tr>
        <tr><td>مجلد النسخ الاحتياطية</td><td>مكان حفظ النسخ</td></tr>
        <tr><td>البقاء بجوار الساعة</td><td>إغلاق النافذة يخفيها فقط</td></tr>
        <tr><td>التشغيل مع ويندوز</td><td>يبدأ مصغّراً عند تسجيل الدخول</td></tr>
        <tr><td>نسخ احتياطي يومي</td><td>نسخ تلقائي لكل قواعد البيانات</td></tr>
        <tr><td>عدد النسخ المحفوظة</td><td>تُحذف النسخ التلقائية الأقدم</td></tr>
        <tr><td>تنبيه التوقف</td><td>إشعار عند توقف خادم بشكل غير متوقع</td></tr>
        <tr><td>اللغة · المظهر</td><td>العربية / English · فاتح / داكن</td></tr>
      </table>
      <div class="note">يمكن أيضاً تشغيل كل خادم odoo-bin تلقائياً عند فتح البرنامج (تبويب نظرة عامة).</div>
    </div>
  </div>
  <h3>الوضع الفاتح والداكن</h3>
  <div class="shot clip-s"><img src="img_ar/main_dark_tab0.png"></div>
  {FOOT.format(n=10)}
</section>

<!-- 11. حل المشكلات -->
<section class="page">
  <div class="kicker">الفصل 9</div>
  <h2>حل المشكلات والأسئلة الشائعة</h2>
  <p class="lead">المشكلات التي يواجهها المستخدمون فعلاً، وحل كل منها.</p>
  <table>
    <tr><th>العَرَض</th><th>السبب والحل</th></tr>
    <tr><td>«Access Denied» عند إنشاء قاعدة بيانات</td><td>كلمة المرور الرئيسية خاطئة. استخدم <b>⋯ ← نسخ كلمة المرور الرئيسية</b>، أو عيّن <code>admin_passwd</code> جديدة من تبويب الإعدادات وأعد التشغيل.</td></tr>
    <tr><td>كلمة المرور الرئيسية تبدأ بـ <code>$pbkdf2</code></td><td>شفّرها Odoo ولا يمكن استرجاعها. عيّن كلمة جديدة من تبويب الإعدادات.</td></tr>
    <tr><td>«no password supplied» على المنفذ 5432</td><td>قيم <code>db_user</code> و <code>db_password</code> في <code>odoo.conf</code> لا تطابق مستخدماً في PostgreSQL. صحّحها وأعد التشغيل.</td></tr>
    <tr><td>الخادم يعمل ثم يتوقف</td><td>افتح تبويب السجل. من الأسباب الشائعة حذف Python الذي بُني عليه الخادم مع إزالة نسخة Odoo قديمة — أعد إنشاء الخادم بالمعالج.</td></tr>
    <tr><td>«المنفذ … مستخدم بالفعل»</td><td>خادم أو برنامج آخر يستخدم المنفذ. استخدم <b>فحص المنافذ</b> ثم غيّر <code>http_port</code>.</td></tr>
    <tr><td>Internal Server Error مع أكثر من إصدار</td><td>كل إصدار من Odoo يرى قواعد بيانات الإصدارات الأخرى. أضف <code>dbfilter</code> في إعدادات كل خادم.</td></tr>
    <tr><td>قاعدة مستعادة لا تفتح</td><td>هي من إصدار أقدم، أو وحداتها المخصصة غير موجودة — أضفها عبر <b>إضافة وحدة</b>.</td></tr>
    <tr><td>لا يمكن الدخول إلى نسخة مستعادة</td><td>نسخ Odoo Online و Odoo.sh غالباً بلا كلمة مرور محلية. أعد تعيين كلمة مرور المستخدم في قاعدة البيانات.</td></tr>
    <tr><td>PostgreSQL عليه ✕ في المعالج</td><td>PostgreSQL لا يعمل — قد تحذفه إزالة نسخة Odoo قديمة. اضغط <b>تثبيت</b> أو شغّل خدمته.</td></tr>
  </table>
  {FOOT.format(n=11)}
</section>

<!-- 12. مرجع سريع -->
<section class="page back">
  <div class="kicker" style="color:#9FE3E6">الفصل 10</div>
  <h2 style="color:#fff">مرجع سريع</h2>
  <p class="lead" style="color:rgba(255,255,255,.85)">أين تجد كل شيء.</p>
  <table style="background:rgba(255,255,255,.06);border-radius:3mm;overflow:hidden">
    <tr><th style="background:rgba(255,255,255,.14);color:#fff">أريد أن…</th><th style="background:rgba(255,255,255,.14);color:#fff">اذهب إلى</th></tr>
    {"".join(f'<tr><td style="border-color:rgba(255,255,255,.15)">{a}</td><td style="border-color:rgba(255,255,255,.15)">{b}</td></tr>' for a, b in [
        ("أشغّل أو أوقف أو أعيد التشغيل", "الأزرار أعلى التبويبات، أو أيقونة البرنامج بجوار الساعة"),
        ("أرى الأخطاء", "تبويب السجل ← فلترة <b>ERROR</b>"),
        ("أعدّل odoo.conf", "تبويب الإعدادات ← حفظ ← إعادة تشغيل"),
        ("أنسخ أو أستعيد أو أحذف قاعدة", "تبويب قواعد البيانات"),
        ("أضيف وحدة أو أحدّثها", "⋯ ← إضافة وحدة / تحديث وحدة"),
        ("أحصل على كلمة المرور الرئيسية", "⋯ ← نسخ كلمة المرور الرئيسية"),
        ("أنشئ خادماً جديداً", "خادم جديد"),
        ("النسخ التلقائي والتنبيهات", "⚙ الإعدادات ← التشغيل التلقائي"),
        ("الجولة الترحيبية والإصدار", "ⓘ عن البرنامج"),
    ])}
  </table>
  <div style="display:flex;align-items:center;gap:6mm;margin-top:16mm">
    <div class="logo" style="width:18mm;height:18mm"><i style="width:9.5mm;height:9.5mm;border-width:2.1mm"></i></div>
    <div><div style="font-size:18pt;font-weight:700" class="ltr">Odoo Manager 1.1.0</div>
      <div style="opacity:.85">Powered by <b>Hossam Ramadan</b></div></div>
  </div>
  <p style="margin-top:8mm;font-size:8.5pt;opacity:.7">Odoo علامة تجارية مملوكة لشركة Odoo S.A. وبرنامج Odoo Manager أداة مستقلة غير تابعة لها ولا معتمدة منها.</p>
  {FOOT.format(n=12)}
</section>
"""

html = f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<title>Odoo Manager — دليل المستخدم</title>
<style>{css}</style>
</head>
<body>
{body}
</body>
</html>
"""
open("guide_ar.html", "w", encoding="utf-8").write(html)
print("ok")
