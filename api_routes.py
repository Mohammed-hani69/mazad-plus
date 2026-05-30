import json as json_module
from datetime import datetime, date, timedelta
from functools import wraps

from flask import Blueprint, redirect, request, jsonify, current_app, url_for
from flask_login import current_user, login_user
from itsdangerous import URLSafeTimedSerializer as Serializer
from sqlalchemy import desc

from models import db, User, Branch, Store, Category, Item
from models import Customer, Supplier, Purchase, PurchaseItem
from models import Sale, SaleItem, Return, ReturnItem
from models import Expense, Bond, StoreSetting, Plan, UserSubscription, Employee, ActivityLog, PasswordResetToken, Notification, UserSetting

from email_utils import send_verification_email, send_password_reset_email
import secrets

api = Blueprint('api', __name__, url_prefix='/api')


class _SafeData:
    def __init__(self, data):
        self._data = data
    def get(self, key, default=None, type=None):
        val = self._data.get(key, default)
        if val is None and default is not None:
            return default
        if type is not None and val is not None and val != default:
            try:
                return type(val)
            except (TypeError, ValueError):
                return default
        return val


# ─────────────────────────── Auth Helpers ───────────────────────────

def generate_token(user_id):
    s = Serializer(current_app.config['SECRET_KEY'])
    return s.dumps({'user_id': user_id})

def verify_token(token):
    s = Serializer(current_app.config['SECRET_KEY'])
    try:
        data = s.loads(token)
        return db.session.get(User, data['user_id'])
    except Exception:
        return None

def api_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            user = verify_token(auth[7:])
            if user:
                login_user(user)
                return f(*args, **kwargs)
        if current_user.is_authenticated:
            return f(*args, **kwargs)
        return jsonify({'error': 'Unauthorized'}), 401
    return decorated

def json_success(data=None, message=None):
    res = {'success': True}
    if data is not None: res['data'] = data
    if message: res['message'] = message
    return jsonify(res)

def json_error(message, status=400):
    return jsonify({'success': False, 'error': message}), status

def safe_commit():
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

def log_activity(action, entity_type, entity_id, details):
    if current_user.is_authenticated and not current_user.is_super_admin:
        log = ActivityLog(
            user_id=current_user.id, action=action,
            entity_type=entity_type, entity_id=entity_id, details=str(details)
        )
        db.session.add(log)

def paginate(query, page=1, per_page=20):
    p = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        'items': [item.to_dict() if hasattr(item, 'to_dict') else {c.name: getattr(item, c.name) for c in item.__table__.columns} for item in p.items],
        'page': p.page, 'per_page': p.per_page, 'total': p.total, 'pages': p.pages,
    }

def check_plan_limit(resource_type):
    if current_user.is_super_admin: return True
    sub = current_user.subscription
    if not sub or not sub.is_active: return False
    plan = sub.plan
    if not plan: return False
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    counts = {
        'items': Item.query.filter_by(is_active=True, user_id=current_user.id).count(),
        'customers': Customer.query.filter_by(is_active=True, user_id=current_user.id).count(),
        'suppliers': Supplier.query.filter_by(is_active=True, user_id=current_user.id).count(),
        'sales': Sale.query.filter(Sale.created_at >= month_start, Sale.user_id == current_user.id).count(),
        'purchases': Purchase.query.filter(Purchase.created_at >= month_start, Purchase.user_id == current_user.id).count(),
        'branches': Branch.query.filter_by(is_active=True, user_id=current_user.id).count(),
        'stores': Store.query.filter_by(is_active=True, user_id=current_user.id).count(),
    }
    limits = {
        'items': plan.max_items, 'customers': plan.max_customers,
        'suppliers': plan.max_suppliers, 'sales': plan.max_invoices_monthly,
        'purchases': plan.max_invoices_monthly, 'branches': plan.max_branches,
        'stores': plan.max_stores,
    }
    if resource_type in counts:
        return counts[resource_type] < limits.get(resource_type, 99999)
    return True

def generate_invoice(prefix):
    today = date.today().strftime('%Y%m%d')
    count = 1
    while True:
        inv = f'{prefix}-{today}-{count:04d}'
        if prefix == 'SALE':
            if not Sale.query.filter_by(invoice_number=inv).first(): return inv
        elif prefix == 'PUR':
            if not Purchase.query.filter_by(invoice_number=inv).first(): return inv
        elif prefix == 'RET':
            if not Return.query.filter_by(return_number=inv).first(): return inv
        elif prefix == 'BND':
            if not Bond.query.filter_by(bond_number=inv).first(): return inv
        count += 1

def get_store_settings():
    if current_user.is_authenticated:
        settings = StoreSetting.query.filter_by(user_id=current_user.id).first()
        if settings: return settings
    settings = StoreSetting(store_name='Mazad Plus')
    if current_user.is_authenticated:
        settings.user_id = current_user.id
        db.session.add(settings)
        db.session.flush()
    return settings

# ─────────────────────── Helpers: model_to_dict ───────────────────────

def branch_to_dict(b):
    return {'id': b.id, 'name': b.name, 'address': b.address, 'phone': b.phone, 'manager': b.manager, 'is_active': b.is_active, 'created_at': b.created_at.isoformat() if b.created_at else None}

def store_to_dict(s):
    return {'id': s.id, 'name': s.name, 'branch_id': s.branch_id, 'branch_name': s.branch.name if s.branch else None, 'address': s.address, 'manager': s.manager, 'is_active': s.is_active, 'created_at': s.created_at.isoformat() if s.created_at else None}

def category_to_dict(c):
    return {'id': c.id, 'name': c.name, 'description': c.description, 'is_active': c.is_active, 'created_at': c.created_at.isoformat() if c.created_at else None}

def item_to_dict(i):
    return {'id': i.id, 'name': i.name, 'barcode': i.barcode, 'category_id': i.category_id, 'category_name': i.category.name if i.category else None, 'store_id': i.store_id, 'store_name': i.store.name if i.store else None, 'buy_price': i.buy_price, 'sell_price': i.sell_price, 'quantity': i.quantity, 'min_quantity': i.min_quantity, 'description': i.description, 'is_active': i.is_active, 'stock_status': i.stock_status, 'created_at': i.created_at.isoformat() if i.created_at else None}

def customer_to_dict(c):
    return {'id': c.id, 'name': c.name, 'phone': c.phone, 'email': c.email, 'address': c.address, 'note': c.note, 'is_active': c.is_active, 'total_purchases': c.total_purchases, 'total_paid': c.total_paid, 'balance': c.balance, 'created_at': c.created_at.isoformat() if c.created_at else None}

def supplier_to_dict(s):
    return {'id': s.id, 'name': s.name, 'phone': s.phone, 'email': s.email, 'address': s.address, 'note': s.note, 'is_active': s.is_active, 'created_at': s.created_at.isoformat() if s.created_at else None}

def purchase_to_dict(p):
    items = [{'id': pi.id, 'purchase_id': pi.purchase_id, 'item_id': pi.item_id, 'item_name': pi.item.name if pi.item else '', 'quantity': pi.quantity, 'price': pi.price, 'total': pi.total} for pi in p.items]
    return {'id': p.id, 'invoice_number': p.invoice_number, 'barcode': p.barcode, 'supplier_id': p.supplier_id, 'supplier_name': p.supplier.name if p.supplier else None, 'store_id': p.store_id, 'store_name': p.store.name if p.store else None, 'user_id': p.user_id, 'user_name': p.user.full_name if p.user else None, 'total': p.total, 'paid': p.paid, 'remaining': p.remaining, 'status': p.status, 'note': p.note, 'items': items, 'created_at': p.created_at.isoformat() if p.created_at else None}

def sale_to_dict(s):
    items = [{'id': si.id, 'sale_id': si.sale_id, 'item_id': si.item_id, 'item_name': si.item.name if si.item else '', 'quantity': si.quantity, 'price': si.price, 'total': si.total} for si in s.items]
    return {'id': s.id, 'invoice_number': s.invoice_number, 'barcode': s.barcode, 'customer_id': s.customer_id, 'customer_name': s.customer.name if s.customer else None, 'store_id': s.store_id, 'store_name': s.store.name if s.store else None, 'user_id': s.user_id, 'user_name': s.user.full_name if s.user else None, 'total': s.total, 'paid': s.paid, 'discount': s.discount, 'remaining': s.remaining, 'status': s.status, 'note': s.note, 'items': items, 'created_at': s.created_at.isoformat() if s.created_at else None}

def return_to_dict(r):
    items = [{'id': ri.id, 'return_id': ri.return_id, 'item_id': ri.item_id, 'item_name': ri.item.name if ri.item else '', 'quantity': ri.quantity, 'price': ri.price, 'total': ri.total} for ri in r.items]
    return {'id': r.id, 'return_number': r.return_number, 'sale_id': r.sale_id, 'sale_invoice_number': r.sale.invoice_number if r.sale else None, 'customer_id': r.customer_id, 'customer_name': r.customer.name if r.customer else None, 'user_id': r.user_id, 'user_name': r.user.full_name if r.user else None, 'total': r.total, 'reason': r.reason, 'items': items, 'created_at': r.created_at.isoformat() if r.created_at else None}

def expense_to_dict(e):
    return {'id': e.id, 'description': e.description, 'amount': e.amount, 'category': e.category, 'branch_id': e.branch_id, 'branch_name': e.branch.name if e.branch else None, 'user_id': e.user_id, 'user_name': e.user.full_name if e.user else None, 'note': e.note, 'created_at': e.created_at.isoformat() if e.created_at else None}

def bond_to_dict(b):
    return {'id': b.id, 'bond_number': b.bond_number, 'bond_type': b.bond_type, 'amount': b.amount, 'customer_id': b.customer_id, 'customer_name': b.customer.name if b.customer else None, 'supplier_id': b.supplier_id, 'supplier_name': b.supplier.name if b.supplier else None, 'user_id': b.user_id, 'user_name': b.user.full_name if b.user else None, 'note': b.note, 'created_at': b.created_at.isoformat() if b.created_at else None}

def employee_to_dict(e):
    perms = e.get_permissions()
    return {'id': e.id, 'user_id': e.user_id, 'user_name': e.user.full_name if e.user else None, 'user_email': e.user.email if e.user else None, 'phone': e.phone, 'branch_id': e.branch_id, 'branch_name': e.branch.name if e.branch else None, 'added_by': e.added_by, 'permissions': perms, 'is_active': e.is_active, 'created_at': e.created_at.isoformat() if e.created_at else None}

def plan_to_dict(p):
    return {'id': p.id, 'name': p.name, 'description': p.description, 'price': p.price, 'duration_days': p.duration_days, 'max_branches': p.max_branches, 'max_stores': p.max_stores, 'max_items': p.max_items, 'max_customers': p.max_customers, 'max_suppliers': p.max_suppliers, 'max_invoices_monthly': p.max_invoices_monthly, 'max_users': p.max_users, 'features': p.features, 'trial_days': p.trial_days, 'is_active': p.is_active, 'created_at': p.created_at.isoformat() if p.created_at else None}

def subscription_to_dict(s):
    return {'id': s.id, 'user_id': s.user_id, 'user_name': s.subscriber.full_name if s.subscriber else None, 'plan_id': s.plan_id, 'plan_name': s.plan.name if s.plan else None, 'start_date': s.start_date.isoformat() if s.start_date else None, 'end_date': s.end_date.isoformat() if s.end_date else None, 'is_active': s.is_active, 'payment_status': s.payment_status, 'payment_method': s.payment_method, 'notes': s.notes, 'created_at': s.created_at.isoformat() if s.created_at else None}

# ─────────────────────────── AUTH ENDPOINTS ───────────────────────────

@api.route('/auth/login', methods=['POST'])
def api_login():
    data = _SafeData(request.get_json() or request.form)
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    if not email or not password:
        return json_error('البريد الإلكتروني وكلمة المرور مطلوبان')
    user = User.query.filter_by(email=email).first()
    if user and user.check_password(password):
        if not user.is_active:
            return json_error('هذا الحساب غير نشط', 401)
        token = generate_token(user.id)
        return json_success({'token': token, 'user': {
            'id': user.id, 'full_name': user.full_name, 'email': user.email,
            'phone': user.phone, 'role': user.role, 'is_active': user.is_active,
            'is_super_admin': user.is_super_admin, 'store_name': user.store_name,
        }})
    return json_error('البريد الإلكتروني أو كلمة المرور غير صحيحة', 401)

@api.route('/auth/signup', methods=['POST'])
def api_signup():
    data = _SafeData(request.get_json() or request.form)
    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip()
    password = data.get('password', '')
    store_name = data.get('store_name', '').strip()
    if not full_name or not email or not password:
        return json_error('جميع الحقول المطلوبة يجب أن تمتلئ')
    if len(password) < 6:
        return json_error('كلمة المرور يجب أن تكون 6 أحرف على الأقل')
    if User.query.filter_by(email=email).first():
        return json_error('البريد الإلكتروني مستخدم بالفعل')
    user = User(full_name=full_name, email=email, phone=phone, role='admin', store_name=store_name or None)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    trial_plan = Plan.query.filter_by(is_active=True).order_by(Plan.price).first()
    if trial_plan and trial_plan.trial_days and trial_plan.trial_days > 0:
        trial_sub = UserSubscription(
            user_id=user.id, plan_id=trial_plan.id,
            start_date=datetime.utcnow(), end_date=datetime.utcnow() + timedelta(days=trial_plan.trial_days),
            is_active=True, payment_status='trial', payment_method='auto',
            notes=f'اشتراك تجريبي لمدة {trial_plan.trial_days} يوم',
        )
        db.session.add(trial_sub)
    default_branch = Branch(name='الفرع الرئيسي', address='', phone='', manager='', user_id=user.id)
    db.session.add(default_branch)
    db.session.flush()
    default_store = Store(name='المخزن الرئيسي', branch_id=default_branch.id, address='', manager='', user_id=user.id)
    db.session.add(default_store)
    default_category = Category(name='عام', description='تصنيف عام', user_id=user.id)
    db.session.add(default_category)
    settings = StoreSetting(user_id=user.id, store_name=store_name, store_phone=phone, store_address='', store_email=email, currency='ج.م', invoice_footer='شكراً لتسوقكم')
    db.session.add(settings)
    safe_commit()
    # Send verification email
    vtoken = secrets.token_urlsafe(32)
    user.verification_token = vtoken
    safe_commit()
    send_verification_email(user, vtoken)
    token = generate_token(user.id)
    return json_success({'token': token, 'user': {
        'id': user.id, 'full_name': user.full_name, 'email': user.email,
        'phone': user.phone, 'role': user.role, 'is_active': user.is_active,
        'is_super_admin': user.is_super_admin, 'store_name': user.store_name,
    }})

@api.route('/auth/forgot-password', methods=['POST'])
def api_forgot_password():
    data = _SafeData(request.get_json() or request.form)
    email = data.get('email', '').strip().lower()
    user = User.query.filter_by(email=email).first()
    if user:
        token = PasswordResetToken(user_id=user.id)
        db.session.add(token)
        safe_commit()
        send_password_reset_email(user, token.token)
    return json_success(message='إذا كان البريد الإلكتروني مسجلاً، ستتلقى رابط إعادة التعيين')

@api.route('/auth/reset-password', methods=['POST'])
def api_reset_password():
    data = _SafeData(request.get_json() or request.form)
    token_str = data.get('token', '')
    password = data.get('password', '')
    confirm = data.get('confirm_password', '')
    if not password or len(password) < 6:
        return json_error('كلمة المرور يجب أن تكون 6 أحرف على الأقل')
    if password != confirm:
        return json_error('كلمة المرور غير متطابقة')
    reset_token = PasswordResetToken.query.filter_by(token=token_str).first()
    if not reset_token or not reset_token.is_valid():
        return json_error('رابط إعادة تعيين كلمة المرور غير صالح أو منتهي الصلاحية')
    user = reset_token.user
    user.set_password(password)
    reset_token.used = True
    safe_commit()
    return json_success(message='تم تغيير كلمة المرور بنجاح')

@api.route('/auth/change-password', methods=['POST'])
@api_login_required
def api_change_password():
    data = _SafeData(request.get_json() or request.form)
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    confirm = data.get('confirm_password', '')
    if not old_password or not new_password:
        return json_error('جميع الحقول مطلوبة')
    if len(new_password) < 6:
        return json_error('كلمة المرور الجديدة يجب أن تكون 6 أحرف على الأقل')
    if new_password != confirm:
        return json_error('كلمة المرور الجديدة غير متطابقة')
    if not current_user.check_password(old_password):
        return json_error('كلمة المرور الحالية غير صحيحة')
    current_user.set_password(new_password)
    safe_commit()
    return json_success(message='تم تغيير كلمة المرور بنجاح')

@api.route('/check-auth')
def api_check_auth():
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        user = verify_token(auth[7:])
        if user:
            return jsonify({
                'authenticated': True,
                'user': {'id': user.id, 'full_name': user.full_name, 'email': user.email, 'phone': user.phone, 'role': user.role, 'is_super_admin': user.is_super_admin, 'store_name': user.store_name}
            })
    elif current_user.is_authenticated:
        u = current_user
        return jsonify({
            'authenticated': True,
            'user': {'id': u.id, 'full_name': u.full_name, 'email': u.email, 'phone': u.phone, 'role': u.role, 'is_super_admin': u.is_super_admin, 'store_name': u.store_name}
        })
    return jsonify({'authenticated': False}), 401

# ─────────────────────────── DASHBOARD ───────────────────────────

@api.route('/dashboard')
@api_login_required
def api_dashboard():
    uid = current_user.id if not current_user.is_super_admin else None
    base_filter = {} if uid is None else {'user_id': uid}
    total_sales = db.session.query(db.func.sum(Sale.total)).filter_by(**base_filter).scalar() or 0
    total_purchases = db.session.query(db.func.sum(Purchase.total)).filter_by(**base_filter).scalar() or 0
    total_expenses = db.session.query(db.func.sum(Expense.amount)).filter_by(**base_filter).scalar() or 0
    total_returns = db.session.query(db.func.sum(Return.total)).filter_by(**base_filter).scalar() or 0
    sale_ids_subq = db.session.query(Sale.id).filter_by(**base_filter) if uid else None
    cogs_query = db.session.query(db.func.sum(SaleItem.quantity * db.func.coalesce(Item.buy_price, 0))).join(Item, SaleItem.item_id == Item.id, isouter=True)
    if sale_ids_subq is not None:
        cogs_query = cogs_query.filter(SaleItem.sale_id.in_(sale_ids_subq))
    cogs = cogs_query.scalar() or 0
    summary = {
        'customers_count': Customer.query.filter_by(is_active=True, **base_filter).count(),
        'suppliers_count': Supplier.query.filter_by(is_active=True, **base_filter).count(),
        'branches_count': Branch.query.filter_by(is_active=True, **base_filter).count(),
        'stores_count': Store.query.filter_by(is_active=True, **base_filter).count(),
        'items_count': Item.query.filter_by(is_active=True, **base_filter).count(),
        'total_sales': round(total_sales, 2), 'total_purchases': round(total_purchases, 2),
        'total_expenses': round(total_expenses, 2), 'total_returns': round(total_returns, 2),
        'sales_count': Sale.query.filter_by(**base_filter).count(), 'purchases_count': Purchase.query.filter_by(**base_filter).count(),
        'returns_count': Return.query.filter_by(**base_filter).count(), 'expenses_count': Expense.query.filter_by(**base_filter).count(),
        'bonds_count': Bond.query.filter_by(**base_filter).count(),
        'cogs': round(cogs, 2), 'gross_profit': round(total_sales - cogs, 2),
        'net_profit': round(total_sales - cogs - total_expenses, 2),
    }
    monthly = []
    now = datetime.utcnow()
    for i in range(5, -1, -1):
        total_months = now.year * 12 + (now.month - 1) - i
        y = total_months // 12; m = (total_months % 12) + 1
        ms = datetime(y, m, 1)
        me = datetime((total_months + 1) // 12, ((total_months + 1) % 12) + 1, 1) if i > 0 else now
        label = ms.strftime('%b')
        ms_sales = db.session.query(db.func.sum(Sale.total)).filter(Sale.created_at >= ms, Sale.created_at < me, Sale.user_id == uid if uid else True).scalar() or 0
        ms_purchases = db.session.query(db.func.sum(Purchase.total)).filter(Purchase.created_at >= ms, Purchase.created_at < me, Purchase.user_id == uid if uid else True).scalar() or 0
        ms_expenses = db.session.query(db.func.sum(Expense.amount)).filter(Expense.created_at >= ms, Expense.created_at < me, Expense.user_id == uid if uid else True).scalar() or 0
        month_sale_ids = db.session.query(Sale.id).filter(Sale.created_at >= ms, Sale.created_at < me)
        if uid:
            month_sale_ids = month_sale_ids.filter(Sale.user_id == uid)
        ms_cogs = db.session.query(db.func.sum(SaleItem.quantity * db.func.coalesce(Item.buy_price, 0))).join(Item, SaleItem.item_id == Item.id, isouter=True).filter(SaleItem.sale_id.in_(month_sale_ids)).scalar() or 0
        monthly.append({'label': label, 'sales': round(ms_sales, 2), 'purchases': round(ms_purchases, 2), 'expenses': round(ms_expenses, 2), 'profit': round(ms_sales - ms_cogs - ms_expenses, 2)})
    daily_sales = []
    for i in range(14, -1, -1):
        day = (now - timedelta(days=i)).date()
        ds = datetime.combine(day, datetime.min.time())
        de = datetime.combine(day, datetime.max.time())
        daily_query = db.session.query(db.func.sum(Sale.total)).filter(Sale.created_at >= ds, Sale.created_at <= de)
        if uid:
            daily_query = daily_query.filter(Sale.user_id == uid)
        dt = daily_query.scalar() or 0
        daily_sales.append({'label': day.strftime('%d %b'), 'value': round(dt, 2)})
    top_items = []
    sale_ids_subq_top = db.session.query(Sale.id)
    if uid:
        sale_ids_subq_top = sale_ids_subq_top.filter(Sale.user_id == uid)
    results = db.session.query(Item.id, Item.name, db.func.sum(SaleItem.quantity), db.func.sum(SaleItem.total)).join(SaleItem, SaleItem.item_id == Item.id).filter(SaleItem.sale_id.in_(sale_ids_subq_top)).group_by(Item.id, Item.name).order_by(desc(db.func.sum(SaleItem.quantity))).limit(5).all()
    for r in results:
        top_items.append({'id': r[0], 'name': r[1], 'total_quantity': float(r[2] or 0), 'total_amount': round(float(r[3] or 0), 2)})
    top_customers = []
    cresults = db.session.query(Customer.id, Customer.name, db.func.sum(Sale.total)).join(Sale, Sale.customer_id == Customer.id)
    if uid:
        cresults = cresults.filter(Sale.user_id == uid)
    cresults = cresults.group_by(Customer.id, Customer.name).order_by(desc(db.func.sum(Sale.total))).limit(5).all()
    for r in cresults:
        top_customers.append({'id': r[0], 'name': r[1], 'total_amount': round(float(r[2] or 0), 2)})
    stock_alerts = []
    stock_query = Item.query.filter(Item.is_active == True, Item.quantity <= Item.min_quantity)
    if uid:
        stock_query = stock_query.filter(Item.user_id == uid)
    for item in stock_query.order_by(Item.quantity).limit(10).all():
        stock_alerts.append({'id': item.id, 'name': item.name, 'quantity': item.quantity, 'min_quantity': item.min_quantity, 'status': item.stock_status})
    recent_sales = [sale_to_dict(s) for s in Sale.query.filter_by(**base_filter).order_by(Sale.created_at.desc()).limit(5).all()]
    recent_purchases = [purchase_to_dict(p) for p in Purchase.query.filter_by(**base_filter).order_by(Purchase.created_at.desc()).limit(5).all()]
    recent_returns = [return_to_dict(r) for r in Return.query.filter_by(**base_filter).order_by(Return.created_at.desc()).limit(5).all()]
    return json_success({
        'summary': summary, 'monthly_sales': [{'label': m['label'], 'value': m['sales']} for m in monthly],
        'monthly_purchases': [{'label': m['label'], 'value': m['purchases']} for m in monthly],
        'monthly_expenses': [{'label': m['label'], 'value': m['expenses']} for m in monthly],
        'monthly_profit': [{'label': m['label'], 'value': m['profit']} for m in monthly],
        'daily_sales': daily_sales, 'top_items': top_items, 'top_customers': top_customers,
        'stock_alerts': stock_alerts, 'recent_sales': recent_sales,
        'recent_purchases': recent_purchases, 'recent_returns': recent_returns,
    })

# ─────────────────────────── GENERIC CRUD HELPERS ───────────────────────────

def crud_list(model, to_dict_fn, search_field=None):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    q = request.args.get('q', '').strip()
    query = model.query
    if hasattr(model, 'user_id') and not current_user.is_super_admin:
        query = query.filter_by(user_id=current_user.id)
    if q and search_field:
        query = query.filter(search_field.ilike(f'%{q}%'))
    query = query.order_by(desc(model.created_at)) if hasattr(model, 'created_at') else query.order_by(model.id.desc())
    p = query.paginate(page=page, per_page=per_page, error_out=False)
    return json_success({
        'data': [to_dict_fn(item) for item in p.items],
        'page': p.page, 'per_page': p.per_page, 'total': p.total, 'pages': p.pages,
    })

def crud_create(model, data, to_dict_fn, log_type=None):
    if hasattr(model, 'user_id') and 'user_id' not in data and not current_user.is_super_admin:
        data['user_id'] = current_user.id
    item = model(**data)
    db.session.add(item)
    db.session.flush()
    if log_type:
        log_activity('create', log_type, item.id, str(data.get('name', data.get('description', ''))))
    safe_commit()
    return json_success(to_dict_fn(item))

def crud_update(model, id, data, to_dict_fn, log_type=None):
    item = model.query.get_or_404(id)
    if hasattr(item, 'user_id') and item.user_id and item.user_id != current_user.id and not current_user.is_super_admin:
        return json_error('غير مصرح لك بتعديل هذا العنصر', 403)
    for key, val in data.items():
        setattr(item, key, val)
    if log_type:
        log_activity('update', log_type, item.id, str(data.get('name', '')))
    safe_commit()
    return json_success(to_dict_fn(item))

def crud_delete(model, id, log_type=None):
    item = model.query.get_or_404(id)
    if hasattr(item, 'user_id') and item.user_id and item.user_id != current_user.id and not current_user.is_super_admin:
        return json_error('غير مصرح لك بحذف هذا العنصر', 403)
    if hasattr(item, 'is_active'):
        item.is_active = False
        if log_type:
            log_activity('delete', log_type, item.id, getattr(item, 'name', ''))
        safe_commit()
        return json_success(message='تم الحذف بنجاح')
    db.session.delete(item)
    safe_commit()
    return json_success(message='تم الحذف بنجاح')

# ─────────────────────────── BRANCHES ───────────────────────────

@api.route('/branches', methods=['GET'])
@api_login_required
def api_branches_list():
    return crud_list(Branch, branch_to_dict, Branch.name)

@api.route('/branches', methods=['POST'])
@api_login_required
def api_branches_create():
    if not check_plan_limit('branches'):
        return json_error('لقد تجاوزت الحد المسموح به من الفروع في باقتك')
    data = _SafeData(request.get_json() or request.form)
    name = data.get('name', '').strip()
    if not name: return json_error('اسم الفرع مطلوب')
    return crud_create(Branch, {'name': name, 'address': data.get('address', '').strip(), 'phone': data.get('phone', '').strip(), 'manager': data.get('manager', '').strip()}, branch_to_dict, 'فرع')

@api.route('/branches/<int:id>', methods=['PUT'])
@api_login_required
def api_branches_update(id):
    data = _SafeData(request.get_json() or request.form)
    name = data.get('name', '').strip()
    if not name: return json_error('اسم الفرع مطلوب')
    return crud_update(Branch, id, {'name': name, 'address': data.get('address', '').strip(), 'phone': data.get('phone', '').strip(), 'manager': data.get('manager', '').strip(), 'is_active': data.get('is_active', True) in (True, 'true', '1', 1)}, branch_to_dict, 'فرع')

@api.route('/branches/<int:id>', methods=['DELETE'])
@api_login_required
def api_branches_delete(id):
    return crud_delete(Branch, id, 'فرع')

# ─────────────────────────── STORES ───────────────────────────

@api.route('/stores', methods=['GET'])
@api_login_required
def api_stores_list():
    return crud_list(Store, store_to_dict, Store.name)

@api.route('/stores', methods=['POST'])
@api_login_required
def api_stores_create():
    if not check_plan_limit('stores'):
        return json_error('لقد تجاوزت الحد المسموح به من المخازن في باقتك')
    data = _SafeData(request.get_json() or request.form)
    name = data.get('name', '').strip()
    if not name: return json_error('اسم المخزن مطلوب')
    branch_id = data.get('branch_id', type=int)
    return crud_create(Store, {'name': name, 'branch_id': branch_id, 'address': data.get('address', '').strip(), 'manager': data.get('manager', '').strip()}, store_to_dict, 'مخزن')

@api.route('/stores/<int:id>', methods=['PUT'])
@api_login_required
def api_stores_update(id):
    data = _SafeData(request.get_json() or request.form)
    name = data.get('name', '').strip()
    if not name: return json_error('اسم المخزن مطلوب')
    return crud_update(Store, id, {'name': name, 'branch_id': data.get('branch_id', type=int), 'address': data.get('address', '').strip(), 'manager': data.get('manager', '').strip(), 'is_active': data.get('is_active', True) in (True, 'true', '1', 1)}, store_to_dict, 'مخزن')

@api.route('/stores/<int:id>', methods=['DELETE'])
@api_login_required
def api_stores_delete(id):
    return crud_delete(Store, id, 'مخزن')

# ─────────────────────────── CATEGORIES ───────────────────────────

@api.route('/categories', methods=['GET'])
@api_login_required
def api_categories_list():
    return crud_list(Category, category_to_dict, Category.name)

@api.route('/categories', methods=['POST'])
@api_login_required
def api_categories_create():
    data = _SafeData(request.get_json() or request.form)
    name = data.get('name', '').strip()
    if not name: return json_error('اسم التصنيف مطلوب')
    return crud_create(Category, {'name': name, 'description': data.get('description', '').strip()}, category_to_dict, 'تصنيف')

@api.route('/categories/<int:id>', methods=['PUT'])
@api_login_required
def api_categories_update(id):
    data = _SafeData(request.get_json() or request.form)
    name = data.get('name', '').strip()
    if not name: return json_error('اسم التصنيف مطلوب')
    return crud_update(Category, id, {'name': name, 'description': data.get('description', '').strip(), 'is_active': data.get('is_active', True) in (True, 'true', '1', 1)}, category_to_dict, 'تصنيف')

@api.route('/categories/<int:id>', methods=['DELETE'])
@api_login_required
def api_categories_delete(id):
    return crud_delete(Category, id, 'تصنيف')

# ─────────────────────────── ITEMS ───────────────────────────

@api.route('/items', methods=['GET'])
@api_login_required
def api_items_list():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    q = request.args.get('q', '').strip()
    category_id = request.args.get('category_id', type=int)
    store_id = request.args.get('store_id', type=int)
    query = Item.query
    if not current_user.is_super_admin:
        query = query.filter_by(user_id=current_user.id)
    if q:
        query = query.filter(Item.name.ilike(f'%{q}%') | Item.barcode.ilike(f'%{q}%'))
    if category_id:
        query = query.filter_by(category_id=category_id)
    if store_id:
        query = query.filter_by(store_id=store_id)
    query = query.order_by(Item.name)
    p = query.paginate(page=page, per_page=per_page, error_out=False)
    return json_success({
        'data': [item_to_dict(i) for i in p.items],
        'page': p.page, 'per_page': p.per_page, 'total': p.total, 'pages': p.pages,
    })

@api.route('/items', methods=['POST'])
@api_login_required
def api_items_create():
    if not check_plan_limit('items'):
        return json_error('لقد تجاوزت الحد المسموح به من الأصناف في باقتك')
    data = _SafeData(request.get_json() or request.form)
    name = data.get('name', '').strip()
    if not name: return json_error('اسم الصنف مطلوب')
    def _int_or_none(v):
        if v is None or v == '': return None
        try: return int(v)
        except: return None

    return crud_create(Item, {
        'name': name, 'barcode': data.get('barcode', '').strip() or None,
        'category_id': _int_or_none(data.get('category_id')),
        'store_id': _int_or_none(data.get('store_id')),
        'buy_price': float(data.get('buy_price', 0) or 0),
        'sell_price': float(data.get('sell_price', 0) or 0),
        'quantity': int(data.get('quantity', 0) or 0),
        'min_quantity': int(data.get('min_quantity', 0) or 0),
        'description': data.get('description', '').strip(),
    }, item_to_dict, 'صنف')

@api.route('/items/<int:id>', methods=['PUT'])
@api_login_required
def api_items_update(id):
    data = _SafeData(request.get_json() or request.form)
    name = data.get('name', '').strip()
    if not name: return json_error('اسم الصنف مطلوب')
    def _int_or_none(v):
        if v is None or v == '': return None
        try: return int(v)
        except: return None

    return crud_update(Item, id, {
        'name': name, 'barcode': data.get('barcode', '').strip() or None,
        'category_id': _int_or_none(data.get('category_id')),
        'store_id': _int_or_none(data.get('store_id')),
        'buy_price': float(data.get('buy_price', 0) or 0),
        'sell_price': float(data.get('sell_price', 0) or 0),
        'quantity': int(data.get('quantity', 0) or 0),
        'min_quantity': int(data.get('min_quantity', 0) or 0),
        'description': data.get('description', '').strip(),
        'is_active': data.get('is_active', True) in (True, 'true', '1', 1),
    }, item_to_dict, 'صنف')

@api.route('/items/<int:id>', methods=['DELETE'])
@api_login_required
def api_items_delete(id):
    return crud_delete(Item, id, 'صنف')

# ─────────────────────────── CUSTOMERS ───────────────────────────

@api.route('/customers', methods=['GET'])
@api_login_required
def api_customers_list():
    return crud_list(Customer, customer_to_dict, Customer.name)

@api.route('/customers', methods=['POST'])
@api_login_required
def api_customers_create():
    if not check_plan_limit('customers'):
        return json_error('لقد تجاوزت الحد المسموح به من العملاء في باقتك')
    data = _SafeData(request.get_json() or request.form)
    name = data.get('name', '').strip()
    if not name: return json_error('اسم العميل مطلوب')
    return crud_create(Customer, {
        'name': name, 'phone': data.get('phone', '').strip(),
        'email': data.get('email', '').strip(), 'address': data.get('address', '').strip(),
        'note': data.get('note', '').strip(),
    }, customer_to_dict, 'عميل')

@api.route('/customers/<int:id>', methods=['PUT'])
@api_login_required
def api_customers_update(id):
    data = _SafeData(request.get_json() or request.form)
    name = data.get('name', '').strip()
    if not name: return json_error('اسم العميل مطلوب')
    return crud_update(Customer, id, {
        'name': name, 'phone': data.get('phone', '').strip(),
        'email': data.get('email', '').strip(), 'address': data.get('address', '').strip(),
        'note': data.get('note', '').strip(),
        'is_active': data.get('is_active', True) in (True, 'true', '1', 1),
    }, customer_to_dict, 'عميل')

@api.route('/customers/<int:id>', methods=['DELETE'])
@api_login_required
def api_customers_delete(id):
    return crud_delete(Customer, id, 'عميل')

# ─────────────────────────── SUPPLIERS ───────────────────────────

@api.route('/suppliers', methods=['GET'])
@api_login_required
def api_suppliers_list():
    return crud_list(Supplier, supplier_to_dict, Supplier.name)

@api.route('/suppliers', methods=['POST'])
@api_login_required
def api_suppliers_create():
    if not check_plan_limit('suppliers'):
        return json_error('لقد تجاوزت الحد المسموح به من الموردين في باقتك')
    data = _SafeData(request.get_json() or request.form)
    name = data.get('name', '').strip()
    if not name: return json_error('اسم المورد مطلوب')
    return crud_create(Supplier, {
        'name': name, 'phone': data.get('phone', '').strip(),
        'email': data.get('email', '').strip(), 'address': data.get('address', '').strip(),
        'note': data.get('note', '').strip(),
    }, supplier_to_dict, 'مورد')

@api.route('/suppliers/<int:id>', methods=['PUT'])
@api_login_required
def api_suppliers_update(id):
    data = _SafeData(request.get_json() or request.form)
    name = data.get('name', '').strip()
    if not name: return json_error('اسم المورد مطلوب')
    return crud_update(Supplier, id, {
        'name': name, 'phone': data.get('phone', '').strip(),
        'email': data.get('email', '').strip(), 'address': data.get('address', '').strip(),
        'note': data.get('note', '').strip(),
        'is_active': data.get('is_active', True) in (True, 'true', '1', 1),
    }, supplier_to_dict, 'مورد')

@api.route('/suppliers/<int:id>', methods=['DELETE'])
@api_login_required
def api_suppliers_delete(id):
    return crud_delete(Supplier, id, 'مورد')

# ─────────────────────────── PURCHASES ───────────────────────────

@api.route('/purchases', methods=['GET'])
@api_login_required
def api_purchases_list():
    return crud_list(Purchase, purchase_to_dict, Purchase.invoice_number)

@api.route('/purchases', methods=['POST'])
@api_login_required
def api_purchases_create():
    if not check_plan_limit('purchases'):
        return json_error('لقد تجاوزت الحد المسموح به من الفواتير الشهرية في باقتك')
    data = _SafeData(request.get_json() or request.form)
    items_data = data.get('items', [])
    if isinstance(items_data, str):
        items_data = json_module.loads(items_data)
    if not items_data:
        return json_error('يجب إضافة صنف واحد على الأقل')
    invoice = generate_invoice('PUR')
    barcode = f'2{str(Purchase.query.filter_by(user_id=current_user.id).count() + 1).zfill(10)}'
    total = sum(float(it.get('total', 0) or float(it.get('price', 0) * it.get('quantity', 0))) for it in items_data)
    purchase = Purchase(
        invoice_number=invoice, barcode=barcode,
        supplier_id=data.get('supplier_id', type=int),
        store_id=data.get('store_id', type=int),
        user_id=current_user.id,
        total=round(total, 2),
        paid=float(data.get('paid', 0) or 0),
        note=data.get('note', '').strip(),
    )
    db.session.add(purchase)
    db.session.flush()
    for it in items_data:
        qty = float(it.get('quantity', 0))
        price = float(it.get('price', 0))
        item_total = round(qty * price, 2)
        pi = PurchaseItem(purchase_id=purchase.id, item_id=int(it['item_id']), quantity=qty, price=price, total=item_total)
        db.session.add(pi)
        item = db.session.get(Item, int(it['item_id']))
        if item:
            item.quantity = (item.quantity or 0) + int(qty)
    log_activity('create', 'مشتريات', purchase.id, invoice)
    safe_commit()
    return json_success(purchase_to_dict(purchase))

@api.route('/purchases/<int:id>', methods=['PUT'])
@api_login_required
def api_purchases_update(id):
    purchase = Purchase.query.get_or_404(id)
    if purchase.user_id and purchase.user_id != current_user.id and not current_user.is_super_admin:
        return json_error('غير مصرح لك', 403)
    data = _SafeData(request.get_json() or request.form)
    purchase.supplier_id = data.get('supplier_id', type=int) or purchase.supplier_id
    purchase.store_id = data.get('store_id', type=int) or purchase.store_id
    purchase.paid = float(data.get('paid', purchase.paid) or 0)
    purchase.note = data.get('note', '').strip() or purchase.note
    items_data = data.get('items')
    if items_data:
        if isinstance(items_data, str):
            items_data = json_module.loads(items_data)
        old_total = purchase.total
        PurchaseItem.query.filter_by(purchase_id=purchase.id).delete()
        total = 0
        for it in items_data:
            qty = float(it.get('quantity', 0))
            price = float(it.get('price', 0))
            item_total = round(qty * price, 2)
            pi = PurchaseItem(purchase_id=purchase.id, item_id=int(it['item_id']), quantity=qty, price=price, total=item_total)
            db.session.add(pi)
            total += item_total
            item = db.session.get(Item, int(it['item_id']))
            if item:
                item.quantity = (item.quantity or 0) + int(qty) - int(it.get('old_quantity', 0))
        purchase.total = round(total, 2)
    log_activity('update', 'مشتريات', purchase.id, purchase.invoice_number)
    safe_commit()
    return json_success(purchase_to_dict(purchase))

@api.route('/purchases/<int:id>', methods=['DELETE'])
@api_login_required
def api_purchases_delete(id):
    purchase = Purchase.query.get_or_404(id)
    if purchase.user_id and purchase.user_id != current_user.id and not current_user.is_super_admin:
        return json_error('غير مصرح لك', 403)
    for pi in purchase.items:
        item = db.session.get(Item, pi.item_id)
        if item:
            item.quantity = max(0, (item.quantity or 0) - int(pi.quantity))
    db.session.delete(purchase)
    log_activity('delete', 'مشتريات', purchase.id, purchase.invoice_number)
    safe_commit()
    return json_success(message='تم حذف فاتورة المشتريات بنجاح')

# ─────────────────────────── SALES ───────────────────────────

@api.route('/sales', methods=['GET'])
@api_login_required
def api_sales_list():
    return crud_list(Sale, sale_to_dict, Sale.invoice_number)

@api.route('/sales', methods=['POST'])
@api_login_required
def api_sales_create():
    if not check_plan_limit('sales'):
        return json_error('لقد تجاوزت الحد المسموح به من الفواتير الشهرية في باقتك')
    data = _SafeData(request.get_json() or request.form)
    items_data = data.get('items', [])
    if isinstance(items_data, str):
        items_data = json_module.loads(items_data)
    if not items_data:
        return json_error('يجب إضافة صنف واحد على الأقل')
    invoice = generate_invoice('SALE')
    barcode = f'1{str(Sale.query.filter_by(user_id=current_user.id).count() + 1).zfill(10)}'
    total = sum(float(it.get('total', 0) or float(it.get('price', 0) * it.get('quantity', 0))) for it in items_data)
    discount = float(data.get('discount', 0) or 0)
    sale = Sale(
        invoice_number=invoice, barcode=barcode,
        customer_id=data.get('customer_id', type=int),
        store_id=data.get('store_id', type=int),
        user_id=current_user.id,
        total=round(total - discount, 2),
        paid=float(data.get('paid', 0) or 0),
        discount=discount,
        note=data.get('note', '').strip(),
    )
    db.session.add(sale)
    db.session.flush()
    for it in items_data:
        qty = float(it.get('quantity', 0))
        price = float(it.get('price', 0))
        item_total = round(qty * price, 2)
        si = SaleItem(sale_id=sale.id, item_id=int(it['item_id']), quantity=qty, price=price, total=item_total)
        db.session.add(si)
        item = db.session.get(Item, int(it['item_id']))
        if item:
            item.quantity = max(0, (item.quantity or 0) - int(qty))
    log_activity('create', 'مبيعات', sale.id, invoice)
    safe_commit()
    return json_success(sale_to_dict(sale))

@api.route('/sales/<int:id>', methods=['PUT'])
@api_login_required
def api_sales_update(id):
    sale = Sale.query.get_or_404(id)
    if sale.user_id and sale.user_id != current_user.id and not current_user.is_super_admin:
        return json_error('غير مصرح لك', 403)
    data = _SafeData(request.get_json() or request.form)
    sale.customer_id = data.get('customer_id', type=int) or sale.customer_id
    sale.store_id = data.get('store_id', type=int) or sale.store_id
    sale.paid = float(data.get('paid', sale.paid) or 0)
    sale.discount = float(data.get('discount', sale.discount) or 0)
    sale.note = data.get('note', '').strip() or sale.note
    items_data = data.get('items')
    if items_data:
        if isinstance(items_data, str):
            items_data = json_module.loads(items_data)
        SaleItem.query.filter_by(sale_id=sale.id).delete()
        total = 0
        for it in items_data:
            qty = float(it.get('quantity', 0))
            price = float(it.get('price', 0))
            item_total = round(qty * price, 2)
            si = SaleItem(sale_id=sale.id, item_id=int(it['item_id']), quantity=qty, price=price, total=item_total)
            db.session.add(si)
            total += item_total
        sale.total = round(total - sale.discount, 2)
    log_activity('update', 'مبيعات', sale.id, sale.invoice_number)
    safe_commit()
    return json_success(sale_to_dict(sale))

@api.route('/sales/<int:id>', methods=['DELETE'])
@api_login_required
def api_sales_delete(id):
    sale = Sale.query.get_or_404(id)
    if sale.user_id and sale.user_id != current_user.id and not current_user.is_super_admin:
        return json_error('غير مصرح لك', 403)
    for si in sale.items:
        item = db.session.get(Item, si.item_id)
        if item:
            item.quantity = (item.quantity or 0) + int(si.quantity)
    db.session.delete(sale)
    log_activity('delete', 'مبيعات', sale.id, sale.invoice_number)
    safe_commit()
    return json_success(message='تم حذف فاتورة المبيعات بنجاح')

# ─────────────────────────── RETURNS ───────────────────────────

@api.route('/returns', methods=['GET'])
@api_login_required
def api_returns_list():
    return crud_list(Return, return_to_dict, Return.return_number)

@api.route('/returns', methods=['POST'])
@api_login_required
def api_returns_create():
    data = _SafeData(request.get_json() or request.form)
    items_data = data.get('items', [])
    if isinstance(items_data, str):
        items_data = json_module.loads(items_data)
    if not items_data:
        return json_error('يجب إضافة صنف واحد على الأقل')
    return_num = generate_invoice('RET')
    total = sum(float(it.get('total', 0) or float(it.get('price', 0) * it.get('quantity', 0))) for it in items_data)
    ret = Return(
        return_number=return_num, sale_id=data.get('sale_id', type=int),
        customer_id=data.get('customer_id', type=int), user_id=current_user.id,
        total=round(total, 2), reason=data.get('reason', '').strip(),
    )
    db.session.add(ret)
    db.session.flush()
    for it in items_data:
        qty = float(it.get('quantity', 0))
        price = float(it.get('price', 0))
        ri = ReturnItem(return_id=ret.id, item_id=int(it['item_id']), quantity=qty, price=price, total=round(qty * price, 2))
        db.session.add(ri)
        item = db.session.get(Item, int(it['item_id']))
        if item:
            item.quantity = (item.quantity or 0) + int(qty)
    log_activity('create', 'مرتجع', ret.id, return_num)
    safe_commit()
    return json_success(return_to_dict(ret))

@api.route('/returns/<int:id>', methods=['PUT'])
@api_login_required
def api_returns_update(id):
    ret = Return.query.get_or_404(id)
    if ret.user_id and ret.user_id != current_user.id and not current_user.is_super_admin:
        return json_error('غير مصرح لك', 403)
    data = _SafeData(request.get_json() or request.form)
    ret.reason = data.get('reason', '').strip() or ret.reason
    items_data = data.get('items')
    if items_data:
        if isinstance(items_data, str):
            items_data = json_module.loads(items_data)
        ReturnItem.query.filter_by(return_id=ret.id).delete()
        total = 0
        for it in items_data:
            qty = float(it.get('quantity', 0))
            price = float(it.get('price', 0))
            ri = ReturnItem(return_id=ret.id, item_id=int(it['item_id']), quantity=qty, price=price, total=round(qty * price, 2))
            db.session.add(ri)
            total += qty * price
        ret.total = round(total, 2)
    log_activity('update', 'مرتجع', ret.id, ret.return_number)
    safe_commit()
    return json_success(return_to_dict(ret))

@api.route('/returns/<int:id>', methods=['DELETE'])
@api_login_required
def api_returns_delete(id):
    ret = Return.query.get_or_404(id)
    if ret.user_id and ret.user_id != current_user.id and not current_user.is_super_admin:
        return json_error('غير مصرح لك', 403)
    for ri in ret.items:
        item = db.session.get(Item, ri.item_id)
        if item:
            item.quantity = max(0, (item.quantity or 0) - int(ri.quantity))
    db.session.delete(ret)
    log_activity('delete', 'مرتجع', ret.id, ret.return_number)
    safe_commit()
    return json_success(message='تم حذف المرتجع بنجاح')

# ─────────────────────────── EXPENSES ───────────────────────────

@api.route('/expenses', methods=['GET'])
@api_login_required
def api_expenses_list():
    return crud_list(Expense, expense_to_dict, Expense.description)

@api.route('/expenses', methods=['POST'])
@api_login_required
def api_expenses_create():
    data = _SafeData(request.get_json() or request.form)
    description = data.get('description', '').strip()
    amount = float(data.get('amount', 0) or 0)
    if not description or amount <= 0:
        return json_error('الوصف والمبلغ المطلوبين')
    return crud_create(Expense, {
        'description': description, 'amount': amount,
        'category': data.get('category', '').strip(),
        'branch_id': data.get('branch_id', type=int),
        'user_id': current_user.id,
        'note': data.get('note', '').strip(),
    }, expense_to_dict, 'مصروف')

@api.route('/expenses/<int:id>', methods=['PUT'])
@api_login_required
def api_expenses_update(id):
    data = _SafeData(request.get_json() or request.form)
    description = data.get('description', '').strip()
    if not description: return json_error('الوصف مطلوب')
    return crud_update(Expense, id, {
        'description': description, 'amount': float(data.get('amount', 0) or 0),
        'category': data.get('category', '').strip(),
        'branch_id': data.get('branch_id', type=int),
        'note': data.get('note', '').strip(),
    }, expense_to_dict, 'مصروف')

@api.route('/expenses/<int:id>', methods=['DELETE'])
@api_login_required
def api_expenses_delete(id):
    return crud_delete(Expense, id, 'مصروف')

# ─────────────────────────── BONDS ───────────────────────────

@api.route('/bonds', methods=['GET'])
@api_login_required
def api_bonds_list():
    return crud_list(Bond, bond_to_dict, Bond.bond_number)

@api.route('/bonds', methods=['POST'])
@api_login_required
def api_bonds_create():
    data = _SafeData(request.get_json() or request.form)
    bond_type = data.get('bond_type', 'receipt')
    amount = float(data.get('amount', 0) or 0)
    if amount <= 0:
        return json_error('المبلغ يجب أن يكون أكبر من صفر')
    bond_num = generate_invoice('BND')
    return crud_create(Bond, {
        'bond_number': bond_num, 'bond_type': bond_type, 'amount': amount,
        'customer_id': data.get('customer_id', type=int) if bond_type == 'receipt' else None,
        'supplier_id': data.get('supplier_id', type=int) if bond_type == 'payment' else None,
        'user_id': current_user.id, 'note': data.get('note', '').strip(),
    }, bond_to_dict, 'سند')

@api.route('/bonds/<int:id>', methods=['PUT'])
@api_login_required
def api_bonds_update(id):
    data = _SafeData(request.get_json() or request.form)
    bond_type = data.get('bond_type', 'receipt')
    return crud_update(Bond, id, {
        'bond_type': bond_type, 'amount': float(data.get('amount', 0) or 0),
        'customer_id': data.get('customer_id', type=int) if bond_type == 'receipt' else None,
        'supplier_id': data.get('supplier_id', type=int) if bond_type == 'payment' else None,
        'note': data.get('note', '').strip(),
    }, bond_to_dict, 'سند')

@api.route('/bonds/<int:id>', methods=['DELETE'])
@api_login_required
def api_bonds_delete(id):
    return crud_delete(Bond, id, 'سند')

# ─────────────────────────── EMPLOYEES ───────────────────────────

@api.route('/employees', methods=['GET'])
@api_login_required
def api_employees_list():
    employees = Employee.query.filter_by(added_by=current_user.id).order_by(Employee.created_at.desc()).all()
    return json_success({'data': [employee_to_dict(e) for e in employees]})

@api.route('/employees', methods=['POST'])
@api_login_required
def api_employees_create():
    data = _SafeData(request.get_json() or request.form)
    email = data.get('email', '').strip()
    password = data.get('password', '')
    full_name = data.get('full_name', '').strip()
    phone = data.get('phone', '').strip()
    branch_id = data.get('branch_id', type=int)
    permissions = data.get('permissions', {})
    if isinstance(permissions, str):
        permissions = json_module.loads(permissions)
    if not full_name or not email or not password:
        return json_error('الاسم والبريد الإلكتروني وكلمة المرور مطلوبة')
    emp_user = User(full_name=full_name, email=email, phone=phone, role='employee')
    emp_user.set_password(password)
    db.session.add(emp_user)
    db.session.flush()
    employee = Employee(
        user_id=emp_user.id, added_by=current_user.id,
        branch_id=branch_id, phone=phone,
        permissions=json_module.dumps(permissions, ensure_ascii=False),
    )
    db.session.add(employee)
    db.session.flush()
    log_activity('create', 'موظف', employee.id, full_name)
    safe_commit()
    return json_success(employee_to_dict(employee))

@api.route('/employees/<int:id>', methods=['PUT'])
@api_login_required
def api_employees_update(id):
    employee = Employee.query.get_or_404(id)
    if employee.added_by != current_user.id and not current_user.is_super_admin:
        return json_error('غير مصرح لك بتعديل هذا الموظف', 403)
    data = _SafeData(request.get_json() or request.form)
    emp_user = employee.user
    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    phone = data.get('phone', '').strip()
    branch_id = data.get('branch_id', type=int)
    permissions = data.get('permissions')
    if isinstance(permissions, str):
        permissions = json_module.loads(permissions)
    if full_name: emp_user.full_name = full_name
    if email: emp_user.email = email
    if phone: emp_user.phone = phone
    if password: emp_user.set_password(password)
    employee.phone = phone or employee.phone
    employee.branch_id = branch_id or employee.branch_id
    if permissions is not None:
        employee.permissions = json_module.dumps(permissions, ensure_ascii=False)
    log_activity('update', 'موظف', employee.id, full_name or emp_user.full_name)
    safe_commit()
    return json_success(employee_to_dict(employee))

@api.route('/employees/<int:id>', methods=['DELETE'])
@api_login_required
def api_employees_delete(id):
    employee = Employee.query.get_or_404(id)
    if employee.added_by != current_user.id and not current_user.is_super_admin:
        return json_error('غير مصرح لك بحذف هذا الموظف', 403)
    emp_user = employee.user
    if emp_user:
        emp_user.is_active = False
    employee.is_active = False
    log_activity('delete', 'موظف', employee.id, employee.user.full_name if employee.user else '')
    safe_commit()
    return json_success(message='تم تعطيل حساب الموظف')

@api.route('/employees/toggle/<int:id>', methods=['POST'])
@api_login_required
def api_employees_toggle(id):
    employee = Employee.query.get_or_404(id)
    if employee.added_by != current_user.id and not current_user.is_super_admin:
        return json_error('غير مصرح لك بتعديل هذا الموظف', 403)
    employee.is_active = not employee.is_active
    if employee.user:
        employee.user.is_active = employee.is_active
    log_activity('update', 'موظف', employee.id, employee.user.full_name if employee.user else '')
    safe_commit()
    return json_success(employee_to_dict(employee))

# ─────────────────────────── ACTIVITY LOGS ───────────────────────────

@api.route('/activity-logs')
@api_login_required
def api_activity_logs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    q = ActivityLog.query
    if not current_user.is_super_admin:
        q = q.filter_by(user_id=current_user.id)
    p = q.order_by(ActivityLog.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return json_success({
        'data': [{
            'id': log.id, 'user_id': log.user_id,
            'user_name': log.user.full_name if log.user else None,
            'action': log.action, 'entity_type': log.entity_type,
            'entity_id': log.entity_id, 'details': log.details,
            'created_at': log.created_at.isoformat() if log.created_at else None,
        } for log in p.items],
        'page': p.page, 'per_page': p.per_page, 'total': p.total, 'pages': p.pages,
    })

# ─────────────────────────── INVOICE SETTINGS ───────────────────────────

@api.route('/invoice-settings', methods=['GET'])
@api_login_required
def api_invoice_settings_get():
    settings = get_store_settings()
    return json_success({
        'store_name': settings.store_name, 'store_phone': settings.store_phone,
        'store_address': settings.store_address, 'store_email': settings.store_email,
        'tax_number': settings.tax_number, 'invoice_template': settings.invoice_template,
        'invoice_footer': settings.invoice_footer, 'currency': settings.currency,
        'store_logo': settings.store_logo,
    })

@api.route('/invoice-settings', methods=['POST'])
@api_login_required
def api_invoice_settings_save():
    data = _SafeData(request.get_json() or request.form)
    settings = get_store_settings()
    settings.store_name = data.get('store_name', 'Mazad Plus').strip()
    settings.store_phone = data.get('store_phone', '').strip()
    settings.store_address = data.get('store_address', '').strip()
    settings.store_email = data.get('store_email', '').strip()
    settings.tax_number = data.get('tax_number', '').strip()
    settings.invoice_template = int(data.get('invoice_template', 1))
    settings.invoice_footer = data.get('invoice_footer', '').strip()
    settings.currency = data.get('currency', 'ج.م').strip()
    settings.store_logo = data.get('store_logo', settings.store_logo)
    log_activity('update', 'إعدادات الفاتورة', settings.id, settings.store_name)
    safe_commit()
    return json_success({'store_name': settings.store_name, 'store_phone': settings.store_phone,
        'store_address': settings.store_address, 'store_email': settings.store_email,
        'tax_number': settings.tax_number, 'invoice_template': settings.invoice_template,
        'invoice_footer': settings.invoice_footer, 'currency': settings.currency,
        'store_logo': settings.store_logo,
    })

@api.route('/invoice-settings/logo', methods=['POST'])
@api_login_required
def api_invoice_settings_logo():
    import os
    from flask import current_app
    file = request.files.get('logo')
    if not file:
        return json_error('لم يتم إرسال ملف الشعار')
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or 'logo.png')[1] or '.png'
    filename = f'logo_{current_user.id}_{int(datetime.utcnow().timestamp())}{ext}'
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)
    logo_url = f'{request.host_url.rstrip("/")}/static/uploads/{filename}'
    settings = get_store_settings()
    settings.store_logo = logo_url
    safe_commit()
    return json_success({'logo_url': logo_url})

# ─────────────────────────── SUBSCRIPTION ───────────────────────────

@api.route('/subscription')
@api_login_required
def api_subscription():
    sub = current_user.subscription
    if sub:
        return json_success(subscription_to_dict(sub))
    return json_error('لا يوجد اشتراك نشط', 404)

@api.route('/employee/permissions', methods=['GET'])
@api_login_required
def api_employee_permissions():
    if current_user.role != 'employee':
        return json_error('هذا المستخدم ليس موظفاً', 403)
    employee = Employee.query.filter_by(user_id=current_user.id).first()
    if not employee:
        return json_error('لم يتم العثور على سجل الموظف', 404)
    return json_success({'permissions': employee.get_permissions(), 'employee_id': employee.id, 'branch_id': employee.branch_id, 'branch_name': employee.branch.name if employee.branch else None})

# ─────────────────────────── ADMIN ENDPOINTS ───────────────────────────

def admin_required_api(f):
    @wraps(f)
    @api_login_required
    def decorated(*args, **kwargs):
        if not current_user.is_super_admin:
            return json_error('غير مصرح', 403)
        return f(*args, **kwargs)
    return decorated

@api.route('/admin/dashboard')
@admin_required_api
def api_admin_dashboard():
    users_count = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    subs_count = UserSubscription.query.count()
    active_subs = UserSubscription.query.filter_by(is_active=True).count()
    plans_count = Plan.query.count()
    total_revenue = db.session.query(db.func.sum(UserSubscription.id)).scalar() or 0
    return json_success({
        'users_count': users_count, 'active_users': active_users,
        'subscriptions_count': subs_count, 'active_subscriptions': active_subs,
        'plans_count': plans_count, 'total_revenue': total_revenue,
    })

@api.route('/admin/users')
@admin_required_api
def api_admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return json_success({'data': [{
        'id': u.id, 'full_name': u.full_name, 'email': u.email,
        'phone': u.phone, 'role': u.role, 'is_active': u.is_active,
        'is_super_admin': u.is_super_admin, 'store_name': u.store_name,
        'created_at': u.created_at.isoformat() if u.created_at else None,
        'subscription': subscription_to_dict(u.subscription) if u.subscription else None,
    } for u in users]})

@api.route('/admin/users/toggle/<int:id>', methods=['POST'])
@admin_required_api
def api_admin_users_toggle(id):
    user = User.query.get_or_404(id)
    user.is_active = not user.is_active
    safe_commit()
    return json_success(message='تم التفعيل' if user.is_active else 'تم الإيقاف')

@api.route('/admin/users/<int:id>', methods=['DELETE'])
@admin_required_api
def api_admin_users_delete(id):
    user = User.query.get_or_404(id)
    StoreSetting.query.filter_by(user_id=user.id).delete()
    UserSubscription.query.filter_by(user_id=user.id).delete()
    Employee.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    safe_commit()
    return json_success(message='تم حذف المستخدم')

@api.route('/admin/users/<int:id>/subscribe', methods=['POST'])
@admin_required_api
def api_admin_users_subscribe(id):
    data = _SafeData(request.get_json() or request.form)
    user = User.query.get_or_404(id)
    plan_id = int(data.get('plan_id', 0))
    plan = Plan.query.get_or_404(plan_id)
    sub = UserSubscription(
        user_id=user.id, plan_id=plan.id,
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=plan.duration_days),
        is_active=True, payment_status=data.get('payment_status', 'paid'),
        payment_method=data.get('payment_method', 'manual'),
        notes=data.get('notes', 'تم الاشتراك عن طريق المشرف'),
    )
    db.session.add(sub)
    safe_commit()
    return json_success(subscription_to_dict(sub))

@api.route('/admin/plans', methods=['GET'])
@admin_required_api
def api_admin_plans_list():
    plans = Plan.query.all()
    return json_success({'data': [plan_to_dict(p) for p in plans]})

@api.route('/admin/plans', methods=['POST'])
@admin_required_api
def api_admin_plans_create():
    data = _SafeData(request.get_json() or request.form)
    plan = Plan(
        name=data.get('name', '').strip(),
        description=data.get('description', '').strip(),
        price=float(data.get('price', 0) or 0),
        duration_days=int(data.get('duration_days', 30) or 30),
        max_branches=int(data.get('max_branches', 1) or 1),
        max_stores=int(data.get('max_stores', 1) or 1),
        max_items=int(data.get('max_items', 100) or 100),
        max_customers=int(data.get('max_customers', 50) or 50),
        max_suppliers=int(data.get('max_suppliers', 50) or 50),
        max_invoices_monthly=int(data.get('max_invoices_monthly', 100) or 100),
        max_users=int(data.get('max_users', 1) or 1),
        features=data.get('features', '').strip(),
        trial_days=int(data.get('trial_days', 0) or 0),
    )
    db.session.add(plan)
    safe_commit()
    return json_success(plan_to_dict(plan))

@api.route('/admin/plans/<int:id>', methods=['PUT'])
@admin_required_api
def api_admin_plans_update(id):
    plan = Plan.query.get_or_404(id)
    data = _SafeData(request.get_json() or request.form)
    for field in ['name', 'description', 'features']:
        val = data.get(field)
        if val is not None: setattr(plan, field, str(val).strip())
    for field in ['price', 'duration_days', 'max_branches', 'max_stores', 'max_items', 'max_customers', 'max_suppliers', 'max_invoices_monthly', 'max_users', 'trial_days']:
        val = data.get(field)
        if val is not None: setattr(plan, field, int(float(val)))
    safe_commit()
    return json_success(plan_to_dict(plan))

@api.route('/admin/plans/<int:id>/toggle', methods=['POST'])
@admin_required_api
def api_admin_plans_toggle(id):
    plan = Plan.query.get_or_404(id)
    plan.is_active = not plan.is_active
    safe_commit()
    return json_success(plan_to_dict(plan))

@api.route('/admin/subscriptions', methods=['GET'])
@admin_required_api
def api_admin_subscriptions_list():
    subs = UserSubscription.query.order_by(UserSubscription.created_at.desc()).all()
    return json_success({'data': [subscription_to_dict(s) for s in subs]})

@api.route('/admin/subscriptions/<int:id>/toggle', methods=['POST'])
@admin_required_api
def api_admin_subscriptions_toggle(id):
    sub = UserSubscription.query.get_or_404(id)
    sub.is_active = not sub.is_active
    safe_commit()
    return json_success(subscription_to_dict(sub))

# ─────────────────────────── EXISTING API ENDPOINTS ───────────────────────────

@api.route('/items-by-store/<int:store_id>')
@api_login_required
def api_items_by_store(store_id):
    store = Store.query.filter_by(id=store_id).first()
    if not store or (store.user_id and store.user_id != current_user.id and not current_user.is_super_admin):
        return jsonify([])
    items = Item.query.filter_by(store_id=store_id, is_active=True, user_id=current_user.id).all()
    return jsonify([{
        'id': i.id, 'name': i.name, 'barcode': i.barcode,
        'sell_price': i.sell_price, 'buy_price': i.buy_price, 'quantity': i.quantity,
    } for i in items])

@api.route('/invoice-items/<string:type>/<int:id>')
@api_login_required
def api_invoice_items(type, id):
    if type == 'purchase':
        obj = Purchase.query.get_or_404(id)
        if obj.user_id and obj.user_id != current_user.id and not current_user.is_super_admin:
            return jsonify({'error': 'غير مصرح'}), 403
        items_data = [{'item_id': pi.item_id, 'item_name': pi.item.name if pi.item else '', 'quantity': pi.quantity, 'price': pi.price, 'total': pi.total} for pi in obj.items]
        return jsonify({'items': items_data, 'total': obj.total, 'paid': obj.paid, 'note': obj.note})
    elif type == 'sale':
        obj = Sale.query.get_or_404(id)
        if obj.user_id and obj.user_id != current_user.id and not current_user.is_super_admin:
            return jsonify({'error': 'غير مصرح'}), 403
        items_data = [{'item_id': si.item_id, 'item_name': si.item.name if si.item else '', 'quantity': si.quantity, 'price': si.price, 'total': si.total} for si in obj.items]
        return jsonify({'items': items_data, 'total': obj.total, 'paid': obj.paid, 'discount': obj.discount, 'note': obj.note})
    return jsonify({'error': 'Invalid type'}), 400

# ─────────────────────────── Notifications ───────────────────────────

def _time_ago(dt):
    diff = datetime.utcnow() - dt
    seconds = int(diff.total_seconds())
    if seconds < 60: return 'الآن'
    minutes = seconds // 60
    if minutes < 60: return f'منذ {minutes} دقيقة'
    hours = minutes // 60
    if hours < 24: return f'منذ {hours} ساعة'
    days = hours // 24
    if days < 30: return f'منذ {days} يوم'
    return dt.strftime('%Y-%m-%d')

@api.route('/notifications')
@api_login_required
def api_notifications_list():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    q = Notification.query.filter_by(recipient_id=current_user.id).order_by(Notification.created_at.desc())
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({
        'notifications': [{
            'id': n.id, 'title': n.title, 'message': n.message,
            'type': n.type, 'link': n.link, 'is_read': n.is_read,
            'created_at': n.created_at.isoformat(), 'time_ago': _time_ago(n.created_at),
        } for n in items],
        'total': total, 'page': page, 'pages': (total + per_page - 1) // per_page,
    })

@api.route('/notifications/count')
@api_login_required
def api_notifications_count():
    unread = Notification.query.filter_by(recipient_id=current_user.id, is_read=False).count()
    return jsonify({'unread': unread})

@api.route('/notifications/<int:nid>/read', methods=['POST'])
@api_login_required
def api_notification_mark_read(nid):
    n = Notification.query.filter_by(id=nid, recipient_id=current_user.id).first_or_404()
    n.is_read = True
    safe_commit()
    return jsonify({'ok': True})

@api.route('/notifications/read-all', methods=['POST'])
@api_login_required
def api_notification_mark_all_read():
    Notification.query.filter_by(recipient_id=current_user.id, is_read=False).update({'is_read': True})
    safe_commit()
    return jsonify({'ok': True})


@api.route('/toggle-dark-mode', methods=['POST'])
@api_login_required
def api_toggle_dark_mode():
    us = UserSetting.query.filter_by(user_id=current_user.id).first()
    if us:
        us.dark_mode = not us.dark_mode
        safe_commit()
    return jsonify({'dark_mode': us.dark_mode if us else False})


@api.route('/lookup-invoice-by-barcode/<barcode>')
@api_login_required
def api_lookup_invoice_by_barcode(barcode):
    if not barcode or len(barcode) < 2:
        return jsonify({'found': False, 'error': 'باركود غير صالح'})
    prefix = barcode[0]
    if prefix == '1':
        sale = Sale.query.filter_by(barcode=barcode, user_id=current_user.id).first()
        if sale:
            return jsonify({'found': True, 'type': 'sale', 'id': sale.id, 'url': url_for('sale_view', id=sale.id)})
    elif prefix == '2':
        purchase = Purchase.query.filter_by(barcode=barcode, user_id=current_user.id).first()
        if purchase:
            return jsonify({'found': True, 'type': 'purchase', 'id': purchase.id, 'url': url_for('purchase_view', id=purchase.id)})
    # Fallback: search both
    sale = Sale.query.filter_by(barcode=barcode, user_id=current_user.id).first()
    if sale:
        return jsonify({'found': True, 'type': 'sale', 'id': sale.id, 'url': url_for('sale_view', id=sale.id)})
    purchase = Purchase.query.filter_by(barcode=barcode, user_id=current_user.id).first()
    if purchase:
        return jsonify({'found': True, 'type': 'purchase', 'id': purchase.id, 'url': url_for('purchase_view', id=purchase.id)})
    return jsonify({'found': False, 'error': 'لم يتم العثور على فاتورة بهذا الباركود'})

# ─────────────────────────── GOOGLE OAUTH ───────────────────────────

@api.route('/auth/google/url', methods=['GET'])
def api_google_auth_url():
    from authlib.integrations.flask_client import OAuth
    google_client_id = current_app.config.get('GOOGLE_CLIENT_ID', '')
    if not google_client_id:
        return json_error('تسجيل الدخول عبر Google غير مفعل')
    redirect_uri = url_for('api.api_google_callback', _external=True)
    oauth = OAuth(current_app)
    oauth.register(
        name='google',
        client_id=google_client_id,
        client_secret=current_app.config.get('GOOGLE_CLIENT_SECRET', ''),
        access_token_url='https://accounts.google.com/o/oauth2/token',
        authorize_url='https://accounts.google.com/o/oauth2/auth',
        api_base_url='https://www.googleapis.com/oauth2/v1/',
        userinfo_endpoint='https://www.googleapis.com/oauth2/v3/userinfo',
        client_kwargs={'scope': 'openid email profile'},
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    )
    result = oauth.google.create_authorization_url(redirect_uri)
    auth_url = result[0]
    state = result[1]
    return json_success({'redirect_url': auth_url, 'state': state})


@api.route('/auth/google/callback', methods=['GET', 'POST'])
def api_google_callback():
    from authlib.integrations.flask_client import OAuth
    from urllib.parse import urlencode
    import json as json_lib
    is_get = request.method == 'GET'
    code = request.args.get('code', '') if is_get else _SafeData(request.get_json() or request.form).get('code', '')
    state = request.args.get('state', '') if is_get else _SafeData(request.get_json() or request.form).get('state', '')
    if not code:
        return json_error('رمز التفويض مطلوب')
    redirect_uri = url_for('api.api_google_callback', _external=True)
    oauth = OAuth(current_app)
    oauth.register(
        name='google',
        client_id=current_app.config.get('GOOGLE_CLIENT_ID', ''),
        client_secret=current_app.config.get('GOOGLE_CLIENT_SECRET', ''),
        access_token_url='https://accounts.google.com/o/oauth2/token',
        authorize_url='https://accounts.google.com/o/oauth2/auth',
        api_base_url='https://www.googleapis.com/oauth2/v1/',
        userinfo_endpoint='https://www.googleapis.com/oauth2/v3/userinfo',
        client_kwargs={'scope': 'openid email profile'},
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    )
    try:
        atoken = oauth.google.authorize_access_token(code=code, state=state)
        userinfo = oauth.google.get('https://www.googleapis.com/oauth2/v3/userinfo').json()
        google_id = userinfo.get('sub')
        email = userinfo.get('email', '').lower()
        name = userinfo.get('name', '')
        if not google_id or not email:
            return json_error('فشل الحصول على بيانات Google')
        user = User.query.filter_by(google_id=google_id).first()
        if not user:
            user = User.query.filter_by(email=email).first()
            if user:
                user.google_id = google_id
            else:
                user = User(
                    full_name=name or email.split('@')[0],
                    email=email, phone='', password_hash='',
                    role='admin', google_id=google_id, email_verified=True,
                )
                user.set_password(secrets.token_urlsafe(16))
                db.session.add(user)
                db.session.flush()
                default_branch = Branch(name='الفرع الرئيسي', address='', phone='', manager='', user_id=user.id)
                db.session.add(default_branch)
                db.session.flush()
                default_store = Store(name='المخزن الرئيسي', branch_id=default_branch.id, address='', manager='', user_id=user.id)
                db.session.add(default_store)
                default_category = Category(name='عام', description='تصنيف عام', user_id=user.id)
                db.session.add(default_category)
                settings = StoreSetting(user_id=user.id, store_name='متجري', store_phone='', store_address='', store_email=email, currency='ج.م', invoice_footer='شكراً لتسوقكم')
                db.session.add(settings)
                trial_plan = Plan.query.filter_by(is_active=True).order_by(Plan.price).first()
                if trial_plan and trial_plan.trial_days and trial_plan.trial_days > 0:
                    db.session.add(UserSubscription(
                        user_id=user.id, plan_id=trial_plan.id,
                        start_date=datetime.utcnow(),
                        end_date=datetime.utcnow() + timedelta(days=trial_plan.trial_days),
                        is_active=True, payment_status='trial', payment_method='auto',
                    ))
        db.session.commit()
        api_token = generate_token(user.id)
        login_user(user)
        if is_get:
            params = urlencode({'token': api_token, 'user': json_lib.dumps({'id': user.id, 'full_name': user.full_name, 'email': user.email, 'role': user.role})})
            return redirect(f'mazadplus://auth?{params}')
        return json_success({'token': api_token, 'user': {'id': user.id, 'full_name': user.full_name, 'email': user.email, 'role': user.role}})
    except Exception as e:
        current_app.logger.error(f'Google auth error: {e}')
        if is_get:
            return redirect(f'mazadplus://auth?error=فشل+تسجيل+الدخول')
        return json_error('فشل تسجيل الدخول عبر Google', 500)


@api.route('/auth/resend-verification', methods=['POST'])
def api_resend_verification():
    data = _SafeData(request.get_json() or request.form)
    email = data.get('email', '').strip().lower()
    user = User.query.filter_by(email=email).first()
    if user and not user.email_verified:
        token = secrets.token_urlsafe(32)
        user.verification_token = token
        safe_commit()
        send_verification_email(user, token)
    return json_success(message='إذا كان البريد الإلكتروني مسجلاً، ستتلقى رابط التأكيد')
