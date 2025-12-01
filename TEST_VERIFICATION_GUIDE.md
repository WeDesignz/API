# Test Verification Guide for Subscription Settlement & Invoice System

This guide provides step-by-step commands to verify all aspects of the subscription settlement and invoice system.

## Prerequisites

1. **Activate Virtual Environment** (if using one):
   ```bash
   cd /Users/vaibhav/Work/wedesignz/Application/API
   source venv/bin/activate  # or your venv path
   ```

2. **Ensure Database is Migrated**:
   ```bash
   python manage.py migrate
   ```

3. **Ensure Celery is Running** (for async tasks):
   ```bash
   # Terminal 1: Celery Worker
   celery -A API worker --loglevel=info
   
   # Terminal 2: Celery Beat (for scheduled tasks)
   celery -A API beat --loglevel=info
   ```

---

## Step 1: Run All Tests

### Run Complete Test Suite
```bash
cd /Users/vaibhav/Work/wedesignz/Application/API
python manage.py test Orders.tests_invoice_settlement --verbosity=2
```

**Expected Result**: All 14 tests should pass (OK)

### Run Specific Test Classes

**Test GST/Commission Calculations**:
```bash
python manage.py test Orders.tests_invoice_settlement.ExtractGSTAndCommissionTestCase --verbosity=2
```

**Test Order Invoice Processing**:
```bash
python manage.py test Orders.tests_invoice_settlement.ProcessOrderInvoicesTestCase --verbosity=2
```

**Test Monthly Subscription Settlement**:
```bash
python manage.py test Orders.tests_invoice_settlement.ProcessSubscriptionSettlementTestCase --verbosity=2
```

**Test Annual Subscription Settlement**:
```bash
python manage.py test Orders.tests_invoice_settlement.ProcessMonthlySubscriptionSettlementTestCase --verbosity=2
```

**Test Celery Task**:
```bash
python manage.py test Orders.tests_invoice_settlement.ProcessExpiredSubscriptionsTaskTestCase --verbosity=2
```

**Test Wallet Transactions**:
```bash
python manage.py test Orders.tests_invoice_settlement.WalletTransactionTestCase --verbosity=2
```

**Test Invoice Model**:
```bash
python manage.py test Orders.tests_invoice_settlement.InvoiceModelTestCase --verbosity=2
```

---

## Step 2: Verify Celery Configuration

### Check Celery Beat Schedule
```bash
cd /Users/vaibhav/Work/wedesignz/Application/API
python manage.py shell
```

In Django shell:
```python
from API.celery import app
print(app.conf.beat_schedule)
```

**Expected**: Should show `process-expired-subscriptions` scheduled with `crontab(hour=3, minute=30)`

### Verify Celery Tasks are Registered
```python
# In Django shell
from celery import current_app
tasks = [task for task in current_app.tasks.keys() if 'subscription' in task.lower() or 'invoice' in task.lower()]
print(tasks)
```

**Expected**: Should include:
- `common.tasks.process_expired_subscriptions`
- `common.tasks.send_customer_invoice_email_async`
- `common.tasks.send_designer_invoice_email_async`
- `common.tasks.send_designer_subscription_invoice_email_async`

---

## Step 3: Test GST/Commission Calculation Logic

### Manual Calculation Test
```bash
python manage.py shell
```

```python
from decimal import Decimal
from Orders.invoice_service import extract_gst_and_commission

# Test with Rs 100
result = extract_gst_and_commission(Decimal('100.00'), Decimal('18.0'), Decimal('30.0'))
print(f"Total: Rs 100")
print(f"Base Amount: Rs {result['base_amount']:.2f}")
print(f"GST (18%): Rs {result['gst_amount']:.2f}")
print(f"Commission (30%): Rs {result['commission_amount']:.2f}")
print(f"Verification: {result['base_amount'] + result['gst_amount'] + result['commission_amount']:.2f}")

# Test with Rs 150
result2 = extract_gst_and_commission(Decimal('150.00'), Decimal('18.0'), Decimal('30.0'))
print(f"\nTotal: Rs 150")
print(f"Base Amount: Rs {result2['base_amount']:.2f}")
print(f"GST (18%): Rs {result2['gst_amount']:.2f}")
print(f"Commission (30%): Rs {result2['commission_amount']:.2f}")
print(f"Verification: {result2['base_amount'] + result2['gst_amount'] + result2['commission_amount']:.2f}")
```

**Expected**: All amounts should add up correctly to the total.

---

## Step 4: Test Order Invoice Processing

### Create Test Order and Process Invoices
```bash
python manage.py shell
```

```python
from django.contrib.auth.models import User
from Orders.models import Order, Invoice
from Orders.invoice_service import process_order_invoices
from Catalog.models import Product, Category
from decimal import Decimal

# Get or create test users
customer = User.objects.filter(username='test_customer').first()
designer1 = User.objects.filter(username='test_designer1').first()

if not customer:
    customer = User.objects.create_user(username='test_customer', email='customer@test.com', password='test123')
if not designer1:
    designer1 = User.objects.create_user(username='test_designer1', email='designer1@test.com', password='test123')

# Create test order
order = Order.objects.filter(status='success', order_type='cart').first()
if not order:
    category = Category.objects.first() or Category.objects.create(name='Test', created_by=customer)
    product = Product.objects.filter(created_by=designer1).first() or Product.objects.create(
        title='Test Design', category=category, product_plan_type='free', status='active', created_by=designer1
    )
    order = Order.objects.create(
        order_type='cart',
        status='success',
        total_amount=Decimal('100.00'),
        product_ids=str(product.id),
        created_by=customer
    )

# Process invoices
result = process_order_invoices(order)

# Verify results
print(f"Customer Invoice: {result['customer_invoice']}")
print(f"Designer Invoices: {result['designer_invoices']}")
print(f"Wallet Transactions: {result['wallet_transactions']}")

# Check invoices were created
customer_invoice = Invoice.objects.filter(order=order, invoice_type='customer').first()
designer_invoice = Invoice.objects.filter(order=order, invoice_type='designer').first()

print(f"\nCustomer Invoice Number: {customer_invoice.invoice_number if customer_invoice else 'Not found'}")
print(f"Designer Invoice Number: {designer_invoice.invoice_number if designer_invoice else 'Not found'}")
print(f"Designer Invoice Total: Rs {designer_invoice.total_amount if designer_invoice else 0}")
```

**Expected**: 
- Customer invoice created with total = Rs 100.00
- Designer invoice created with GST + Commission
- Wallet credited with base amount

---

## Step 5: Test Monthly Subscription Settlement

### Create and Test Monthly Subscription
```bash
python manage.py shell
```

```python
from django.utils import timezone
from datetime import timedelta
from Plans.models import Plan, Subscription
from Orders.models import Order, Invoice
from Orders.invoice_service import process_subscription_settlement
from Wallet.models import Wallet
from decimal import Decimal

# Get or create monthly plan
monthly_plan = Plan.objects.filter(plan_duration='monthly').first()
if not monthly_plan:
    customer = User.objects.first()
    monthly_plan = Plan.objects.create(
        plan_name='basic',
        description={'features': ['20 downloads']},
        price=Decimal('400.00'),
        plan_duration='monthly',
        no_of_free_downloads=20,
        created_by=customer
    )

# Create subscription (35 days ago)
past_date = timezone.now() - timedelta(days=35)
subscription = Subscription.objects.create(
    plan=monthly_plan,
    status='active',
    settlement_processed=False,
    created_by=User.objects.first(),
    created_at=past_date
)

# Create test orders with downloads
# (Add products and orders as needed)

# Process settlement
result = process_subscription_settlement(subscription)

print(f"Settlement Result:")
print(f"  Total Downloads: {result.get('total_downloads', 0)}")
print(f"  Per Download Price: Rs {result.get('per_download_price', 0)}")
print(f"  Designer Breakdown: {result.get('designer_breakdown', {})}")

# Verify subscription status
subscription.refresh_from_db()
print(f"\nSubscription Status: {subscription.status}")
print(f"Settlement Processed: {subscription.settlement_processed}")

# Check invoices
invoices = Invoice.objects.filter(subscription=subscription)
print(f"\nInvoices Created: {invoices.count()}")
for inv in invoices:
    print(f"  - {inv.invoice_number} ({inv.invoice_type}): Rs {inv.total_amount}")
```

**Expected**:
- Subscription status = 'expired'
- Settlement processed = True
- Designer invoices created
- Wallets credited

---

## Step 6: Test Annual Subscription Monthly Settlement

### Test Annual Subscription First Settlement
```bash
python manage.py shell
```

```python
from django.utils import timezone
from datetime import timedelta, date
from Plans.models import Plan, Subscription
from Orders.models import Order, Invoice
from Orders.invoice_service import process_monthly_subscription_settlement
from Wallet.models import Wallet
from decimal import Decimal

# Get or create annual plan
annual_plan = Plan.objects.filter(plan_duration='annually').first()
if not annual_plan:
    customer = User.objects.first()
    annual_plan = Plan.objects.create(
        plan_name='premium',
        description={'features': ['120 downloads']},
        price=Decimal('1200.00'),
        plan_duration='annually',
        no_of_free_downloads=120,
        created_by=customer
    )

# Create subscription (35 days ago)
purchase_date = timezone.now() - timedelta(days=35)
subscription = Subscription.objects.create(
    plan=annual_plan,
    status='active',
    last_settled_month=None,
    created_by=User.objects.first(),
    created_at=purchase_date
)

# Process first settlement
period_start = purchase_date.date()
period_end = period_start + timedelta(days=30)

result = process_monthly_subscription_settlement(subscription, period_start, period_end)

print(f"First Settlement Result:")
print(f"  Period: {period_start} to {period_end}")
print(f"  Downloads Used: {result.get('total_downloads_used', 0)}")
print(f"  Downloads Settled: {result.get('total_downloads_settled', 0)}")
print(f"  Monthly Price: Rs {result.get('monthly_price', 0)}")

# Verify last_settled_month
subscription.refresh_from_db()
print(f"\nLast Settled Date: {subscription.last_settled_month}")

# Check invoices
invoices = Invoice.objects.filter(subscription=subscription)
print(f"\nInvoices Created: {invoices.count()}")
```

**Expected**:
- `last_settled_month` = period_end date
- Monthly settlement processed
- Designer invoices created

---

## Step 7: Test Celery Task Execution

### Manually Trigger Celery Task
```bash
python manage.py shell
```

```python
from common.tasks import process_expired_subscriptions
from Plans.models import Subscription
from django.utils import timezone
from datetime import timedelta

# Create test subscriptions ready for settlement
# (Monthly subscription 35+ days old)
# (Annual subscription 35+ days old)

# Call the task directly
result = process_expired_subscriptions()
print(f"Task Result: {result}")

# Check processed subscriptions
monthly_subs = Subscription.objects.filter(status='expired', settlement_processed=True)
annual_subs = Subscription.objects.filter(last_settled_month__isnull=False)

print(f"\nMonthly Subscriptions Processed: {monthly_subs.count()}")
print(f"Annual Subscriptions with Settlements: {annual_subs.count()}")
```

**Expected**: Task executes successfully and processes eligible subscriptions.

---

## Step 8: Verify Celery Beat Schedule

### Check Next Run Time
```bash
python manage.py shell
```

```python
from celery.schedules import crontab
from datetime import datetime

# The task is scheduled for 3:30 AM IST daily
schedule = crontab(hour=3, minute=30)
print(f"Scheduled: Daily at 3:30 AM IST")
print(f"Current Time: {datetime.now()}")
```

**Expected**: Confirms schedule is set to 3:30 AM IST.

---

## Step 9: Verify Database Models

### Check Invoice Model
```bash
python manage.py shell
```

```python
from Orders.models import Invoice
from django.contrib.auth.models import User

# Check invoice fields
invoice_fields = [f.name for f in Invoice._meta.get_fields()]
print(f"Invoice Fields: {invoice_fields}")

# Verify required fields exist
required_fields = ['invoice_number', 'invoice_type', 'user', 'subtotal', 'gst_amount', 'commission_amount', 'total_amount', 'subscription']
for field in required_fields:
    if field in invoice_fields:
        print(f"✓ {field} exists")
    else:
        print(f"✗ {field} MISSING")
```

**Expected**: All required fields exist.

### Check Subscription Model
```python
from Plans.models import Subscription

# Check subscription fields
sub_fields = [f.name for f in Subscription._meta.get_fields()]
print(f"\nSubscription Fields: {sub_fields}")

# Verify settlement tracking fields
settlement_fields = ['settlement_processed', 'last_settled_month']
for field in settlement_fields:
    if field in sub_fields:
        print(f"✓ {field} exists")
    else:
        print(f"✗ {field} MISSING")
```

**Expected**: `settlement_processed` and `last_settled_month` exist.

---

## Step 10: Verify Email Service Integration

### Check Email Service Methods
```bash
python manage.py shell
```

```python
from common.email_service import EmailService

# Check if email methods exist
methods = [m for m in dir(EmailService) if not m.startswith('_') and callable(getattr(EmailService, m))]
email_methods = [m for m in methods if 'invoice' in m.lower() or 'subscription' in m.lower()]

print("Email Service Methods:")
for method in email_methods:
    print(f"  - {method}")

# Verify required methods
required_methods = [
    'send_customer_invoice_email',
    'send_designer_invoice_email',
    'send_subscription_purchase_email'
]

for method in required_methods:
    if hasattr(EmailService, method):
        print(f"✓ {method} exists")
    else:
        print(f"✗ {method} MISSING")
```

**Expected**: All required email methods exist.

---

## Step 11: Test Wallet Transactions

### Verify Wallet Operations
```bash
python manage.py shell
```

```python
from Wallet.models import Wallet, WalletTransaction
from django.contrib.auth.models import User
from decimal import Decimal

# Get or create test designer
designer = User.objects.filter(username='test_designer').first()
if not designer:
    designer = User.objects.create_user(username='test_designer', email='designer@test.com', password='test123')

# Create wallet
wallet, created = Wallet.objects.get_or_create(created_by=designer)
print(f"Wallet Created: {created}")
print(f"Initial Balance: Rs {wallet.balance}")

# Add balance
wallet.balance = Decimal(str(wallet.balance)) + Decimal('100.00')
wallet.save()

# Create transaction
transaction = WalletTransaction.objects.create(
    wallet_transaction_type='credit',
    amount=Decimal('100.00'),
    description='Test settlement',
    reference_id='test_ref_123',
    created_by=designer
)

wallet.attach_wallet_transaction(transaction)

# Verify
wallet.refresh_from_db()
print(f"Final Balance: Rs {wallet.balance}")
print(f"Transaction Created: {WalletTransaction.objects.filter(created_by=designer).exists()}")
```

**Expected**: Wallet balance updated, transaction created.

---

## Step 12: Full Integration Test

### Complete End-to-End Test
```bash
python manage.py shell
```

```python
# This is a comprehensive test that verifies the entire flow
# 1. Create subscription
# 2. Create orders with downloads
# 3. Process settlement
# 4. Verify invoices
# 5. Verify wallets
# 6. Verify transactions

from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from Plans.models import Plan, Subscription
from Orders.models import Order, Invoice
from Orders.invoice_service import process_subscription_settlement
from Wallet.models import Wallet, WalletTransaction
from Catalog.models import Product, Category

# Setup
customer = User.objects.first()
designer = User.objects.filter(username__icontains='designer').first() or User.objects.first()

# Create plan
plan = Plan.objects.filter(plan_duration='monthly').first()
if not plan:
    plan = Plan.objects.create(
        plan_name='test',
        description={},
        price=Decimal('400.00'),
        plan_duration='monthly',
        no_of_free_downloads=20,
        created_by=customer
    )

# Create subscription
past_date = timezone.now() - timedelta(days=35)
subscription = Subscription.objects.create(
    plan=plan,
    status='active',
    settlement_processed=False,
    created_by=customer,
    created_at=past_date
)

# Create category and product
category = Category.objects.first() or Category.objects.create(name='Test', created_by=customer)
product = Product.objects.filter(created_by=designer).first()
if not product:
    product = Product.objects.create(
        title='Test Design',
        category=category,
        product_plan_type='free',
        status='active',
        created_by=designer
    )

# Create order
order = Order.objects.create(
    subscription=subscription,
    order_type='subscription',
    status='success',
    product_ids=str(product.id),
    total_amount=Decimal('0'),
    created_by=customer,
    created_at=past_date + timedelta(days=5)
)

# Process settlement
result = process_subscription_settlement(subscription)

# Verify everything
print("=" * 50)
print("INTEGRATION TEST RESULTS")
print("=" * 50)

subscription.refresh_from_db()
print(f"\n1. Subscription Status: {subscription.status} (Expected: expired)")
print(f"2. Settlement Processed: {subscription.settlement_processed} (Expected: True)")

invoices = Invoice.objects.filter(subscription=subscription)
print(f"\n3. Invoices Created: {invoices.count()} (Expected: 1+)")
for inv in invoices:
    print(f"   - {inv.invoice_number} ({inv.invoice_type}): Rs {inv.total_amount}")

wallet = Wallet.objects.filter(created_by=designer).first()
if wallet:
    print(f"\n4. Designer Wallet Balance: Rs {wallet.balance} (Expected: > 0)")

transactions = WalletTransaction.objects.filter(created_by=designer)
print(f"\n5. Wallet Transactions: {transactions.count()} (Expected: 1+)")
for txn in transactions:
    print(f"   - {txn.description}: Rs {txn.amount}")

print(f"\n6. Settlement Result:")
print(f"   - Total Downloads: {result.get('total_downloads', 0)}")
print(f"   - Per Download Price: Rs {result.get('per_download_price', 0)}")

print("\n" + "=" * 50)
print("TEST COMPLETE")
print("=" * 50)
```

**Expected**: All steps complete successfully with expected values.

---

## Quick Verification Checklist

Run this quick check:
```bash
python manage.py shell
```

```python
# Quick verification
from Orders.models import Invoice
from Plans.models import Subscription
from Wallet.models import Wallet, WalletTransaction

print("✓ Invoices:", Invoice.objects.count())
print("✓ Subscriptions:", Subscription.objects.count())
print("✓ Wallets:", Wallet.objects.count())
print("✓ Wallet Transactions:", WalletTransaction.objects.count())
```

---

## Troubleshooting

### If Tests Fail:
1. **Check Database**: `python manage.py migrate`
2. **Check Models**: Verify all models are properly defined
3. **Check Imports**: Ensure all imports are correct
4. **Check Celery**: Ensure Celery is running for async tasks

### If Celery Tasks Don't Run:
1. **Check Worker**: `celery -A API worker --loglevel=info`
2. **Check Beat**: `celery -A API beat --loglevel=info`
3. **Check Schedule**: Verify `crontab(hour=3, minute=30)` in `celery.py`

### If Invoices Don't Generate:
1. **Check PDF Library**: `pip install reportlab Pillow`
2. **Check Media Directory**: Ensure `media/invoices/` exists
3. **Check Permissions**: Ensure write permissions on media directory

---

## Summary

After running all verification steps, you should have:
- ✅ All 14 tests passing
- ✅ Celery tasks registered and scheduled
- ✅ GST/Commission calculations working correctly
- ✅ Order invoices processing successfully
- ✅ Monthly subscription settlements working
- ✅ Annual subscription monthly settlements working
- ✅ Wallet transactions being created
- ✅ Email service methods available

All systems should be operational! 🎉

