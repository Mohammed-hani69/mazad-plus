import secrets
from datetime import datetime, timedelta

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# ─────────────────────────── Users ───────────────────────────

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='admin')
    is_active = db.Column(db.Boolean, default=True)
    is_super_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    store_name = db.Column(db.String(200), nullable=True)
    email_verified = db.Column(db.Boolean, default=False)
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    verification_token = db.Column(db.String(100), unique=True, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def subscription(self):
        return UserSubscription.query.filter_by(user_id=self.id).order_by(UserSubscription.created_at.desc()).first()

    @property
    def is_subscription_active(self):
        if self.is_super_admin:
            return True
        if self.role == 'employee':
            emp = Employee.query.filter_by(user_id=self.id, is_active=True).first()
            if emp and emp.added_by:
                admin = db.session.get(User, emp.added_by)
                if admin:
                    return admin.is_subscription_active
        sub = self.subscription
        if not sub or not sub.is_active:
            return False
        return sub.end_date >= datetime.utcnow()

    def __repr__(self):
        return f'<User {self.email}>'


# ─────────────────────────── Branches ───────────────────────────

class Branch(db.Model):
    __tablename__ = 'branches'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    manager = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    user = db.relationship('User', backref='branches')

    def __repr__(self):
        return f'<Branch {self.name}>'


# ─────────────────────────── Stores / Warehouses ───────────────────────────

class Store(db.Model):
    __tablename__ = 'stores'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    manager = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    branch = db.relationship('Branch', backref='stores')
    user = db.relationship('User', backref='stores')

    def __repr__(self):
        return f'<Store {self.name}>'


# ─────────────────────────── Categories ───────────────────────────

class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    user = db.relationship('User', backref='categories')

    def __repr__(self):
        return f'<Category {self.name}>'


# ─────────────────────────── Items ───────────────────────────

class Item(db.Model):
    __tablename__ = 'items'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    barcode = db.Column(db.String(50), unique=True, nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=True)
    buy_price = db.Column(db.Float, default=0)
    sell_price = db.Column(db.Float, default=0)
    quantity = db.Column(db.Integer, default=0)
    min_quantity = db.Column(db.Integer, default=0)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    category = db.relationship('Category', backref='items')
    store = db.relationship('Store', backref='items')
    user = db.relationship('User', backref='items')

    @property
    def stock_status(self):
        if self.quantity <= 0:
            return 'out'
        if self.quantity <= self.min_quantity:
            return 'low'
        return 'ok'

    def __repr__(self):
        return f'<Item {self.name}>'


# ─────────────────────────── Customers ───────────────────────────

class Customer(db.Model):
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    note = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    user = db.relationship('User', backref='customers')

    @property
    def total_purchases(self):
        return sum(s.total for s in self.sales)

    @property
    def total_paid(self):
        return sum(s.paid for s in self.sales)

    @property
    def balance(self):
        return self.total_purchases - self.total_paid

    def __repr__(self):
        return f'<Customer {self.name}>'


# ─────────────────────────── Suppliers ───────────────────────────

class Supplier(db.Model):
    __tablename__ = 'suppliers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    note = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    user = db.relationship('User', backref='suppliers')

    def __repr__(self):
        return f'<Supplier {self.name}>'


# ─────────────────────────── Purchases ───────────────────────────

class Purchase(db.Model):
    __tablename__ = 'purchases'

    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    barcode = db.Column(db.String(50), unique=True, nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    total = db.Column(db.Float, default=0)
    paid = db.Column(db.Float, default=0)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    supplier = db.relationship('Supplier', backref='purchases')
    store = db.relationship('Store', backref='purchases')
    user = db.relationship('User', backref='purchases')
    items = db.relationship('PurchaseItem', backref='purchase', cascade='all, delete-orphan')

    @property
    def remaining(self):
        return self.total - self.paid

    @property
    def status(self):
        if self.paid >= self.total:
            return 'paid'
        if self.paid > 0:
            return 'partial'
        return 'unpaid'


class PurchaseItem(db.Model):
    __tablename__ = 'purchase_items'

    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchases.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=True)
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)

    item = db.relationship('Item', backref='purchase_items')


# ─────────────────────────── Sales ───────────────────────────

class Sale(db.Model):
    __tablename__ = 'sales'

    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    barcode = db.Column(db.String(50), unique=True, nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    total = db.Column(db.Float, default=0)
    paid = db.Column(db.Float, default=0)
    discount = db.Column(db.Float, default=0)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship('Customer', backref='sales')
    store = db.relationship('Store', backref='sales')
    user = db.relationship('User', backref='sales')
    items = db.relationship('SaleItem', backref='sale', cascade='all, delete-orphan')

    @property
    def remaining(self):
        return self.total - self.paid

    @property
    def status(self):
        if self.paid >= self.total:
            return 'paid'
        if self.paid > 0:
            return 'partial'
        return 'unpaid'


class SaleItem(db.Model):
    __tablename__ = 'sale_items'

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=True)
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)

    item = db.relationship('Item', backref='sale_items')


# ─────────────────────────── Returns ───────────────────────────

class Return(db.Model):
    __tablename__ = 'returns'

    id = db.Column(db.Integer, primary_key=True)
    return_number = db.Column(db.String(50), unique=True, nullable=False)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    total = db.Column(db.Float, default=0)
    reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sale = db.relationship('Sale', backref='returns')
    customer = db.relationship('Customer', backref='returns')
    user = db.relationship('User', backref='returns')
    items = db.relationship('ReturnItem', backref='return_ref', cascade='all, delete-orphan')


class ReturnItem(db.Model):
    __tablename__ = 'return_items'

    id = db.Column(db.Integer, primary_key=True)
    return_id = db.Column(db.Integer, db.ForeignKey('returns.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=True)
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)

    item = db.relationship('Item', backref='return_items')


# ─────────────────────────── Expenses ───────────────────────────

class Expense(db.Model):
    __tablename__ = 'expenses'

    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, default=0)
    category = db.Column(db.String(50), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    branch = db.relationship('Branch', backref='expenses')
    user = db.relationship('User', backref='expenses')

    def __repr__(self):
        return f'<Expense {self.description}>'


# ─────────────────────────── Bonds ───────────────────────────

class Bond(db.Model):
    __tablename__ = 'bonds'

    id = db.Column(db.Integer, primary_key=True)
    bond_number = db.Column(db.String(50), unique=True, nullable=False)
    bond_type = db.Column(db.String(20), nullable=False)  # 'receipt' or 'payment'
    amount = db.Column(db.Float, default=0)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship('Customer', backref='bonds')
    supplier = db.relationship('Supplier', backref='bonds')
    user = db.relationship('User', backref='bonds')

    def __repr__(self):
        return f'<Bond {self.bond_number}>'


# ─────────────────────────── Store Settings ───────────────────────────

class StoreSetting(db.Model):
    __tablename__ = 'store_settings'

    id = db.Column(db.Integer, primary_key=True)
    store_name = db.Column(db.String(200), default='Mazad Plus')
    store_phone = db.Column(db.String(50), default='')
    store_address = db.Column(db.String(300), default='')
    store_email = db.Column(db.String(120), default='')
    tax_number = db.Column(db.String(50), default='')
    invoice_template = db.Column(db.Integer, default=1)
    invoice_footer = db.Column(db.Text, default='شكراً لتسوقكم معنا')
    currency = db.Column(db.String(20), default='ج.م')
    store_logo = db.Column(db.String(500), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    user = db.relationship('User', backref='store_settings')

    def __repr__(self):
        return f'<StoreSetting {self.store_name}>'


class UserSetting(db.Model):
    __tablename__ = 'user_settings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    language = db.Column(db.String(10), default='ar')
    currency = db.Column(db.String(20), default='ج.م')
    print_copies = db.Column(db.Integer, default=1)
    page_size = db.Column(db.Integer, default=20)
    default_payment_status = db.Column(db.String(20), default='unpaid')
    notifications_enabled = db.Column(db.Boolean, default=True)
    dark_mode = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='user_settings', uselist=False)


# ─────────────────────────── Subscription Plans ───────────────────────────

class Plan(db.Model):
    __tablename__ = 'plans'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, default=0)
    duration_days = db.Column(db.Integer, default=30)
    max_branches = db.Column(db.Integer, default=1)
    max_stores = db.Column(db.Integer, default=1)
    max_items = db.Column(db.Integer, default=50)
    max_customers = db.Column(db.Integer, default=50)
    max_suppliers = db.Column(db.Integer, default=20)
    max_invoices_monthly = db.Column(db.Integer, default=100)
    max_users = db.Column(db.Integer, default=1)
    features = db.Column(db.Text, nullable=True)
    trial_days = db.Column(db.Integer, default=7)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subscriptions = db.relationship('UserSubscription', backref='plan', lazy='dynamic')

    def __repr__(self):
        return f'<Plan {self.name}>'


class UserSubscription(db.Model):
    __tablename__ = 'user_subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=False)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    payment_status = db.Column(db.String(20), default='pending')
    payment_method = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subscriber = db.relationship('User', backref='subscriptions', foreign_keys=[user_id])

    def __repr__(self):
        return f'<UserSubscription user={self.user_id} plan={self.plan_id}>'


# ─────────────────────────── Employees ───────────────────────────

class Employee(db.Model):
    __tablename__ = 'employees'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    added_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    permissions = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='employee_profile', foreign_keys=[user_id])
    owner = db.relationship('User', backref='added_employees', foreign_keys=[added_by])
    branch = db.relationship('Branch', backref='employees')

    def get_permissions(self):
        if not self.permissions:
            return {}
        import json
        try:
            return json.loads(self.permissions)
        except:
            return {}

    def has_perm(self, endpoint):
        perms = self.get_permissions()
        # 1. Exact match
        if perms.get(endpoint, False):
            return True
        # 2. Prefix fallback: `branches_list` => `branches` / `branch_add` => `branch` => `branches`
        parts = endpoint.rsplit('_', 1)
        if len(parts) > 1:
            base = parts[0]
            if perms.get(base, False):
                return True
            # جرب صيغة الجمع (للتوافق مع الصلاحيات القديمة: `branches`)
            if not base.endswith('s') and perms.get(base + 's', False):
                return True
        return False

    def __repr__(self):
        return f'<Employee user={self.user_id} by={self.added_by}>'


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(50), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='activity_logs')

    def __repr__(self):
        return f'<ActivityLog {self.action} by user={self.user_id}>'


class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(32))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(hours=1))
    used = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref='reset_tokens')

    def is_valid(self):
        return not self.used and datetime.utcnow() < self.expires_at


# ─────────────────────────── Notifications ───────────────────────────

class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=True)
    type = db.Column(db.String(20), default='info')
    link = db.Column(db.String(500), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', backref='sent_notifications', foreign_keys=[sender_id])
    recipient = db.relationship('User', backref='notifications', foreign_keys=[recipient_id])

    def __repr__(self):
        return f'<Notification #{self.id} to={self.recipient_id}>'
