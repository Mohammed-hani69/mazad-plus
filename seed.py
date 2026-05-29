"""
Mazad Plus - Seed Data Generator
Generates realistic demo data for all database tables.
Run: python seed.py
"""
import os
import sys
from datetime import datetime, timedelta
from random import randint, choice, uniform, seed as random_seed

random_seed(42)

# Ensure we can import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import User, Branch, Store, Category, Item
from models import Customer, Supplier, Purchase, PurchaseItem
from models import Sale, SaleItem, Return, ReturnItem
from models import Expense, Bond, StoreSetting, Plan, UserSubscription


def seed_database():
    with app.app_context():
        # Drop and recreate all tables
        db.drop_all()
        db.create_all()
        print('✓ Tables recreated')

        # ── Admin User (Super Admin) ──
        admin = User(
            full_name='مدير النظام',
            email='admin@mazadplus.com',
            phone='01000000000',
            role='admin',
            is_super_admin=True,
        )
        admin.set_password('admin123')
        db.session.add(admin)

        user2 = User(
            full_name='أحمد محمد',
            email='ahmed@mazadplus.com',
            phone='01111111111',
            role='admin',
        )
        user2.set_password('ahmed123')
        db.session.add(user2)
        db.session.flush()

        # ── Default Plans ──
        plans_data = [
            ('الخطة الأساسية', 'مناسبة للمتاجر الصغيرة', 0, 30, 1, 1, 50, 50, 20, 100, 1,
             'مخزن واحد\n50 صنف\n100 فاتورة شهرياً'),
            ('الخطة المهنية', 'للمتاجر المتوسطة', 299, 30, 3, 3, 500, 200, 100, 500, 3,
             '3 مخازن\n500 صنف\n500 فاتورة شهرياً\n3 مستخدمين\nتقارير'),
            ('الخطة المتقدمة', 'للمتاجر الكبيرة', 799, 30, 10, 10, 2000, 1000, 500, 2000, 10,
             '10 مخازن\n2000 صنف\n2000 فاتورة\n10 مستخدمين\nدعم VIP'),
            ('الخطة الغير محدودة', 'بدون قيود', 1599, 30, 999, 999, 99999, 99999, 99999, 99999, 50,
             'كل شيء غير محدود\n50 مستخدم\nدعم VIP 24/7'),
        ]
        plans = []
        for name, desc, price, days, branches, stores, items, cust, supp, inv, users, features in plans_data:
            p = Plan(name=name, description=desc, price=price, duration_days=days,
                     max_branches=branches, max_stores=stores, max_items=items,
                     max_customers=cust, max_suppliers=supp, max_invoices_monthly=inv,
                     max_users=users, features=features, trial_days=7)
            db.session.add(p)
            plans.append(p)
        db.session.flush()

        # Give user2 the basic plan
        basic_plan = plans[0]
        sub = UserSubscription(
            user_id=user2.id,
            plan_id=basic_plan.id,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            is_active=True,
            payment_status='paid',
            payment_method='admin',
            notes='اشتراك تجريبي',
        )
        db.session.add(sub)
        db.session.flush()

        # ── Store Settings ──
        settings = StoreSetting(
            user_id=admin.id,
            store_name='متجر مزاد بلس',
            store_phone='01000000000',
            store_address='القاهرة - مصر الجديدة',
            store_email='info@mazadplus.com',
            tax_number='123-456-789',
            currency='ج.م',
            invoice_footer='شكراً لتسوقكم مع مزاد بلس',
        )
        db.session.add(settings)
        db.session.flush()

        # ── Branches ──
        branch_data = [
            ('الفرع الرئيسي', 'القاهرة - مصر الجديدة', '0224000001', 'محمد علي'),
            ('فرع الإسكندرية', 'الإسكندرية - سموحة', '034000002', 'أحمد حسن'),
            ('فرع الدلتا', 'طنطا - شارع البحر', '0403000003', 'خالد عبدالله'),
            ('فرع الصعيد', 'أسيوط - الحي الجامعي', '0882000004', 'محمود سيد'),
        ]
        branches = []
        for name, addr, phone, mgr in branch_data:
            br = Branch(name=name, address=addr, phone=phone, manager=mgr, user_id=admin.id)
            db.session.add(br)
            branches.append(br)
        db.session.flush()

        # ── Stores ──
        store_data = [
            ('المخزن المركزي', branches[0].id, 'المنطقة الصناعية - القاهرة', 'عمر حسن'),
            ('مخزن المبيعات', branches[0].id, 'بجوار الفرع الرئيسي', 'سامي يوسف'),
            ('مخزن الإسكندرية', branches[1].id, 'المنطقة الحرة - الإسكندرية', 'كريم نبيل'),
            ('مخزن الدلتا', branches[2].id, 'طنطا - المنطقة الصناعية', 'عادل مصطفى'),
            ('مخزن الصعيد', branches[3].id, 'أسيوط - المنطقة الصناعية', 'حسام علي'),
            ('مخزن التوزيع', branches[0].id, 'مدينة نصر - القاهرة', 'إيهاب سعيد'),
        ]
        stores = []
        for name, bid, addr, mgr in store_data:
            st = Store(name=name, branch_id=bid, address=addr, manager=mgr, user_id=admin.id)
            db.session.add(st)
            stores.append(st)
        db.session.flush()

        # ── Categories ──
        cat_data = [
            ('إلكترونيات', 'الأجهزة الكهربائية والإلكترونية'),
            ('ملابس', 'الملابس والأزياء'),
            ('مواد غذائية', 'المواد الغذائية والمشروبات'),
            ('أدوات منزلية', 'الأدوات المنزلية والمطبخ'),
            ('عطور ومستحضرات', 'العطور ومستحضرات التجميل'),
            ('ألعاب', 'ألعاب الأطفال'),
            ('قرطاسية', 'الأدوات المكتبية والقرطاسية'),
            ('رياضة', 'المعدات والملابس الرياضية'),
        ]
        categories = []
        for name, desc in cat_data:
            cat = Category(name=name, description=desc, user_id=admin.id)
            db.session.add(cat)
            categories.append(cat)
        db.session.flush()

        # ── Items (3 per category) ──
        item_templates = [
            # (name, category_idx, barcode_prefix, buy_price_range, sell_price_range)
            ('تلفزيون 55 بوصة', 0, 'ELEC-001', (5000, 8000), (7000, 11000)),
            ('محمول سامسونج', 0, 'ELEC-002', (4000, 7000), (5500, 10000)),
            ('سماعة بلوتوث', 0, 'ELEC-003', (50, 200), (100, 350)),
            ('قميص رجالي', 1, 'CLTH-001', (80, 200), (150, 350)),
            ('بنطلون جينز', 1, 'CLTH-002', (150, 400), (300, 600)),
            ('فستان سهرة', 1, 'CLTH-003', (200, 600), (400, 1000)),
            ('زيت زيتون', 2, 'FOOD-001', (30, 80), (50, 120)),
            ('عسل طبيعي', 2, 'FOOD-002', (50, 150), (100, 250)),
            ('قهوة محمصة', 2, 'FOOD-003', (20, 60), (40, 100)),
            ('طقم كاسات', 3, 'HOME-001', (40, 120), (80, 200)),
            ('مفروشات سرير', 3, 'HOME-002', (200, 500), (350, 800)),
            ('أبجورة', 3, 'HOME-003', (60, 200), (120, 350)),
            ('عطر فرنسي', 4, 'BEAU-001', (100, 500), (200, 900)),
            ('كريم ترطيب', 4, 'BEAU-002', (30, 100), (60, 180)),
            ('مكياج', 4, 'BEAU-003', (40, 200), (80, 350)),
            ('لعبة سيارة', 5, 'TOYS-001', (30, 80), (60, 150)),
            ('دمية أطفال', 5, 'TOYS-002', (40, 120), (80, 200)),
            ('مكعبات بناء', 5, 'TOYS-003', (50, 150), (100, 280)),
            ('كراسات رسم', 6, 'STAT-001', (10, 30), (15, 50)),
            ('أقلام تلوين', 6, 'STAT-002', (15, 50), (25, 80)),
        ]
        items = []
        for name, cat_idx, barcode, (bp_min, bp_max), (sp_min, sp_max) in item_templates:
            buy_p = round(uniform(bp_min, bp_max), 2)
            sell_p = round(uniform(sp_min, sp_max), 2)
            qty = randint(20, 500)
            item = Item(
                name=name,
                barcode=barcode,
                category_id=categories[cat_idx].id,
                store_id=choice(stores).id,
                buy_price=buy_p,
                sell_price=sell_p,
                quantity=qty,
                min_quantity=randint(5, 30),
                user_id=admin.id,
            )
            db.session.add(item)
            items.append(item)
        db.session.flush()

        # ── Customers ──
        customer_data = [
            ('محمد إبراهيم', '01011111111', 'mohamed@mail.com', 'القاهرة', 'عميل ممتاز'),
            ('علي حسن', '01022222222', 'ali@mail.com', 'الإسكندرية', ''),
            ('فاطمة سعيد', '01033333333', 'fatma@mail.com', 'طنطا', ''),
            ('محمود عبدالله', '01044444444', 'mahmoud@mail.com', 'أسيوط', ''),
            ('نورة أحمد', '01055555555', 'noura@mail.com', 'القاهرة', 'عميل دائم'),
            ('خالد علي', '01066666666', 'khaled@mail.com', 'الإسكندرية', ''),
            ('سمر يوسف', '01077777777', 'samar@mail.com', 'المنصورة', ''),
            ('أيمن جمال', '01088888888', 'ayman@mail.com', 'القاهرة', ''),
            ('داليا شريف', '01099999999', 'dalia@mail.com', 'الإسكندرية', 'عميل VIP'),
            ('ياسر عبدالرحمن', '01211111111', 'yasser@mail.com', 'طنطا', ''),
            ('هند عادل', '01222222222', 'hend@mail.com', 'أسيوط', ''),
            ('كريم مصطفى', '01233333333', 'kareem@mail.com', 'القاهرة', ''),
        ]
        customers = []
        for name, phone, email, addr, note in customer_data:
            c = Customer(name=name, phone=phone, email=email, address=addr, note=note, user_id=admin.id)
            db.session.add(c)
            customers.append(c)
        db.session.flush()

        # ── Suppliers ──
        supplier_data = [
            ('شركة الإلكترونيات الحديثة', '0225000001', 'info@electronice.com', 'القاهرة - العبور', 'مورد إلكترونيات رئيسي'),
            ('مصنع الملابس المصري', '0226000002', 'sales@egyclothes.com', 'القاهرة - شبرا', ''),
            ('شركة الغذاء العالمي', '0227000003', 'info@globalfood.com', 'الإسكندرية', 'مورد مواد غذائية'),
            ('مستودع الأدوات المنزلية', '0228000004', 'order@hometools.com', 'طنطا', ''),
            ('معمل العطور الفاخرة', '0229000005', 'info@perfume.com', 'القاهرة', 'مورد عطور'),
            ('شركة الألعاب الترفيهية', '0230000006', 'sales@toysworld.com', 'القاهرة', ''),
        ]
        suppliers = []
        for name, phone, email, addr, note in supplier_data:
            s = Supplier(name=name, phone=phone, email=email, address=addr, note=note, user_id=admin.id)
            db.session.add(s)
            suppliers.append(s)
        db.session.flush()

        # ── Helper: Generate random date in range ──
        def random_date(start, end):
            delta = end - start
            return start + timedelta(days=randint(0, delta.days))

        now = datetime.utcnow()
        three_months_ago = now - timedelta(days=90)

        # ── Purchases (18 invoices over 3 months) ──
        purchase_items_data = []
        for _ in range(18):
            supplier = choice(suppliers)
            store = choice(stores)
            created = random_date(three_months_ago, now)
            # Pick 2-5 random items
            item_count = randint(2, 5)
            selected_items = []
            total = 0
            for _ in range(item_count):
                item = choice(items)
                qty = randint(5, 50)
                price = item.buy_price * uniform(0.9, 1.1)
                price = round(price, 2)
                line_total = round(qty * price, 2)
                total += line_total
                selected_items.append((item.id, qty, price, line_total))
            total = round(total, 2)
            paid = choice([total, total, total, round(total * uniform(0.3, 0.9), 2), 0])
            inv_num = f'PUR-{created.strftime("%Y%m%d")}-{randint(1, 99):04d}'
            # Ensure unique invoice number
            while Purchase.query.filter_by(invoice_number=inv_num).first():
                inv_num = f'PUR-{created.strftime("%Y%m%d")}-{randint(1, 99):04d}'
            p = Purchase(
                invoice_number=inv_num,
                supplier_id=supplier.id,
                store_id=store.id,
                user_id=choice([admin.id, user2.id]),
                total=total,
                paid=paid,
                note=choice(['', 'دفعة أولى', 'استلام كامل', '']),
                created_at=created,
            )
            db.session.add(p)
            db.session.flush()
            purchase_items_data.append((p.id, selected_items, created))

        db.session.flush()

        for pid, sitems, _ in purchase_items_data:
            for item_id, qty, price, line_total in sitems:
                pi = PurchaseItem(purchase_id=pid, item_id=item_id, quantity=qty, price=price, total=line_total)
                db.session.add(pi)
                # Update item quantity
                it = db.session.get(Item, item_id)
                if it:
                    it.quantity = (it.quantity or 0) + qty
        db.session.flush()

        print(f'✓ {len(purchase_items_data)} purchases created')

        # ── Sales (25 invoices over 3 months) ──
        sale_items_data = []
        for _ in range(25):
            customer = choice(customers)
            store = choice(stores)
            created = random_date(three_months_ago, now)
            item_count = randint(1, 6)
            selected_items = []
            total = 0
            for _ in range(item_count):
                item = choice(items)
                qty = randint(1, 10)
                price = item.sell_price * uniform(0.95, 1.15)
                price = round(price, 2)
                line_total = round(qty * price, 2)
                total += line_total
                selected_items.append((item.id, qty, price, line_total))
            total = round(total, 2)
            discount = choice([0, 0, 0, round(total * uniform(0.05, 0.15), 2), round(total * uniform(0.2, 0.3), 2)])
            if discount > total * 0.3:
                discount = 0
            net = round(total - discount, 2)
            paid = choice([net, net, net, round(net * uniform(0.3, 0.9), 2), 0])
            inv_num = f'SALE-{created.strftime("%Y%m%d")}-{randint(1, 99):04d}'
            while Sale.query.filter_by(invoice_number=inv_num).first():
                inv_num = f'SALE-{created.strftime("%Y%m%d")}-{randint(1, 99):04d}'
            s = Sale(
                invoice_number=inv_num,
                customer_id=customer.id,
                store_id=store.id,
                user_id=choice([admin.id, user2.id]),
                total=total,
                paid=paid,
                discount=discount,
                note=choice(['', 'شكراً للشراء', 'توصيل للمنزل', '']),
                created_at=created,
            )
            db.session.add(s)
            db.session.flush()
            sale_items_data.append((s.id, selected_items, created, customer.id))
        db.session.flush()

        for sid, sitems, _, _ in sale_items_data:
            for item_id, qty, price, line_total in sitems:
                si = SaleItem(sale_id=sid, item_id=item_id, quantity=qty, price=price, total=line_total)
                db.session.add(si)
                it = db.session.get(Item, item_id)
                if it:
                    it.quantity = max(0, (it.quantity or 0) - qty)
        db.session.flush()

        print(f'✓ {len(sale_items_data)} sales created')

        # ── Returns (6 returns, linked to sales) ──
        return_count = 0
        for sid, sitems, created, cid in sale_items_data[:8]:  # Use first 8 sales
            if randint(0, 1) == 0:
                continue
            return_count += 1
            ret_total = 0
            ret_items = []
            for item_id, qty, price, _ in sitems[:randint(1, min(3, len(sitems)))]:
                rqty = randint(1, min(qty, 3))
                ret_line = round(rqty * price, 2)
                ret_total += ret_line
                ret_items.append((item_id, rqty, price, ret_line))
            ret_total = round(ret_total, 2)
            rn = f'RET-{created.strftime("%Y%m%d")}-{return_count:04d}'
            while Return.query.filter_by(return_number=rn).first():
                rn = f'RET-{created.strftime("%Y%m%d")}-{return_count:04d}'
            ret = Return(
                return_number=rn,
                sale_id=sid,
                customer_id=cid,
                user_id=admin.id,
                total=ret_total,
                reason=choice(['تلف في المنتج', 'عدم مطابقة', 'خطأ في الطلب', '']),
                created_at=created + timedelta(days=randint(1, 5)),
            )
            db.session.add(ret)
            db.session.flush()
            for item_id, rqty, price, ret_line in ret_items:
                ri = ReturnItem(return_id=ret.id, item_id=item_id, quantity=rqty, price=price, total=ret_line)
                db.session.add(ri)
                it = db.session.get(Item, item_id)
                if it:
                    it.quantity = (it.quantity or 0) + rqty
        db.session.flush()
        print(f'✓ {return_count} returns created')

        # ── Expenses (12 expenses) ──
        expense_categories = ['إيجار', 'كهرباء', 'مياه', 'رواتب', 'صيانة', 'تسويق', 'نقل', 'تأمين']
        for _ in range(12):
            created = random_date(three_months_ago, now)
            exp = Expense(
                description=choice(['إيجار شهري', 'فاتورة كهرباء', 'فاتورة مياه', 'رواتب موظفين',
                                    'صيانة مكيفات', 'حملة تسويقية', 'مصروفات نقل', 'تأمين سنوي',
                                    'مستلزمات نظافة', 'قرطاسية مكتب']),
                amount=round(uniform(100, 15000), 2),
                category=choice(expense_categories),
                branch_id=choice(branches).id,
                user_id=admin.id,
                note='',
                created_at=created,
            )
            db.session.add(exp)
        db.session.flush()
        print('✓ 12 expenses created')

        # ── Bonds (10 bonds) ──
        for _ in range(10):
            created = random_date(three_months_ago, now)
            btype = choice(['receipt', 'receipt', 'payment'])
            bond = Bond(
                bond_number=f'BND-{created.strftime("%Y%m%d")}-{randint(1, 99):04d}',
                bond_type=btype,
                amount=round(uniform(200, 20000), 2),
                customer_id=choice(customers).id if btype == 'receipt' else None,
                supplier_id=choice(suppliers).id if btype == 'payment' else None,
                user_id=admin.id,
                note=choice(['', 'دفعة نقدية', 'شيك']),
                created_at=created,
            )
            db.session.add(bond)
        db.session.flush()
        print('✓ 10 bonds created')

        db.session.commit()
        print('\n✓ Database seeded successfully!')
        print(f'  Users: 2')
        print(f'  Branches: {len(branches)}')
        print(f'  Stores: {len(stores)}')
        print(f'  Categories: {len(categories)}')
        print(f'  Items: {len(items)}')
        print(f'  Customers: {len(customers)}')
        print(f'  Suppliers: {len(suppliers)}')
        print(f'  Purchases: {len(purchase_items_data)}')
        print(f'  Sales: {len(sale_items_data)}')
        print(f'  Returns: {return_count}')
        print(f'  Expenses: 12')
        print(f'  Bonds: 10')


if __name__ == '__main__':
    seed_database()
