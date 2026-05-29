<div align="center">
  <img src="https://mazad-plus.com/static/assets/images/logo.png" alt="Mazad Plus Logo" width="180" style="margin-bottom: 10px;">
  <h1 align="center" style="color: #4f46e5; font-size: 2.5em; margin: 5px 0;">Mazad Plus</h1>
  <p align="center" style="font-size: 1.2em; color: #6b7280;">
    نظام إدارة متكامل للمتاجر والمخازن — <strong>Mazad Plus</strong>
  </p>
  <p align="center">
    <strong>النسخة:</strong> 1.0.0 &nbsp;|&nbsp;
    <strong>الحالة:</strong> قيد التطوير
  </p>
</div>

---

## 📋 نبذة عن النظام

**Mazad Plus** هو نظام إدارة متكامل للمتاجر والمخازن، مبني باستخدام **Flask** و **SQLAlchemy**، يتيح لك إدارة المخزون والمبيعات والمشتريات والعملاء والموردين والفروع والمخازن والمصروفات والسندات والموظفين، مع نظام اشتراكات متكامل.

---

## ✨ المميزات

- **إدارة المخزون** — إضافة وتعديل وحذف الأصناف مع متابعة الكميات والحد الأدنى للتنبيه
- **المبيعات والمشتريات** — فواتير بيع وشراء مع إدارة المدفوعات والأرصدة
- **المرتجعات** — إدارة مرتجعات المبيعات
- **العملاء والموردين** — قاعدة بيانات متكاملة مع إمكانية تتبع المعاملات
- **الفروع والمخازن** — إدارة فروع ومخازن متعددة
- **المصروفات** — تسجيل وتصنيف المصروفات
- **السندات** — سندات قبض ودفع
- **الموظفين** — إضافة موظفين مع صلاحيات مخصصة
- **الاشتراكات** — نظام خطط واشتراكات (مجاني / تجريبي / مدفوع)
- **التقارير** — إحصائيات المبيعات والمشتريات والأرباح والرسوم البيانية
- **متعدد المستخدمين** — كل مستخدم يرى بياناته الخاصة فقط
- **تسجيل الدخول عبر Google** — OAuth 2.0
- **تأكيد البريد الإلكتروني** — إرسال إيميل تأكيد بعد التسجيل
- **استعادة كلمة المرور** — إرسال رابط إعادة التعيين على البريد
- **قابلية التوسع** — قاعدة بيانات SQLite (افتراضي) مع دعم PostgreSQL / MySQL

---

## 🛠 التقنيات المستخدمة

| التقنية | الوصف |
|---------|-------|
| **Flask 3.0** | إطار العمل الرئيسي |
| **Flask-SQLAlchemy** | ORM للتعامل مع قاعدة البيانات |
| **Flask-Login** | إدارة جلسات المستخدمين |
| **Flask-WTF / WTForms** | حماية CSRF والنماذج |
| **Flask-CORS** | دعم Cross-Origin |
| **Authlib** | تسجيل الدخول عبر Google OAuth |
| **SQLite / PostgreSQL** | قاعدة البيانات |
| **Bootstrap 5 RTL** | واجهة المستخدم |
| **Font Awesome 6** | الأيقونات |
| **Chart.js** | الرسوم البيانية |

---

## 🚀 طريقة التشغيل

### المتطلبات

- Python 3.10+
- pip

### 1. تنزيل المشروع

```bash
git clone https://github.com/Mohammed-hani69/mazad-plus.git
cd mazad-plus
```

### 2. إنشاء البيئة الافتراضية (اختياري)

```bash
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate   # Linux / macOS
```

### 3. تثبيت الحزم

```bash
pip install -r requirements.txt
```

### 4. إعداد ملف البيئة

```bash
cp .env.example .env
```

عدّل ملف `.env` وأضف الإعدادات المطلوبة.

### 5. تشغيل النظام

```bash
python app.py
```

افتح المتصفح على: `http://localhost:5000`



## ⚙️ إعدادات البيئة (.env)

```env
# ── قواعد البيانات ──
# DATABASE_URL=sqlite:///mazad_plus.db

# ── البريد الإلكتروني (SMTP) ──
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com

# ── Google OAuth ──
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret

# ── رابط التطبيق ──
APP_URL=http://localhost:5000

# ── مفتاح التشفير ──
SECRET_KEY=your-secret-key
```

> **ملاحظة أمان:** لا تشارك ملف `.env` أبداً. تمت إضافته إلى `.gitignore`.

---

## 📁 هيكل المشروع

```
mazadplus-dashboard/
├── app.py              # تطبيق Flask الرئيسي + المسارات
├── api_routes.py       # واجهة API (REST)
├── models.py           # نماذج قاعدة البيانات
├── config.py           # إعدادات التطبيق
├── email_utils.py      # إرسال الإيميلات
├── seed.py             # بيانات تجريبية
├── requirements.txt    # الحزم المطلوبة
├── .env.example        # قالب إعدادات البيئة
├── templates/          # قوالب HTML
│   ├── login.html
│   ├── signup.html
│   ├── dashboard.html
│   └── ...
├── static/             # ملفات ثابتة
│   ├── assets/images/  # صور (لوجو، إلخ)
│   ├── style.css
│   └── app.js
└── mazad_plus.db       # قاعدة البيانات (يتم إنشاؤها تلقائياً)
```

---

## 📄 الترخيص

هذا المشروع **غير مرخص** — جميع الحقوق محفوظة لصاحب المشروع.

لا يُسمح لأي شخص أو جهة باستخدام، نسخ، تعديل، توزيع، أو إعادة نشر أي جزء من ملفات هذا المشروع دون الحصول على إذن كتابي صريح من المالك.

للحصول على ترخيص أو استفسار: [m78893024@gmail.com](mailto:m78893024@gmail.com)

---

<div align="center">
  <p>تم التطوير بواسطة <strong>Mazad Plus Team</strong></p>
  <p>© 2026 Mazad Plus — جميع الحقوق محفوظة</p>
</div>
