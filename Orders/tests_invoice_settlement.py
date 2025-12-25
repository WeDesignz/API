"""
Comprehensive tests for Invoice and Subscription Settlement functionality
Tests invoice generation, subscription settlements, GST/commission calculations, and Celery tasks
"""

from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
from unittest.mock import patch, MagicMock
import os

from Orders.models import Order, Invoice
from Orders.invoice_service import (
    extract_gst_and_commission,
    process_order_invoices,
    process_subscription_settlement,
    process_monthly_subscription_settlement,
    calculate_order_breakdown
)
from Plans.models import Plan, Subscription
from Catalog.models import Product, Category
from Wallet.models import Wallet, WalletTransaction
from common.tasks import process_subscription_billing
from common.business_config import BusinessConfig


class ExtractGSTAndCommissionTestCase(TestCase):
    """Test cases for extract_gst_and_commission function"""
    
    def setUp(self):
        """Set up test data"""
        pass
    
    def test_extract_gst_and_commission_100_rs(self):
        """Test extraction with Rs 100, 18% GST, 30% commission"""
        total_price = Decimal('100.00')
        gst_percentage = Decimal('18.0')
        commission_rate = Decimal('30.0')
        
        result = extract_gst_and_commission(total_price, gst_percentage, commission_rate)
        
        # PRINT CALCULATED VALUES
        print("\n" + "="*70)
        print("GST/COMMISSION CALCULATION TEST - Rs 100")
        print("="*70)
        print(f"Input Values:")
        print(f"  Total Price:        Rs {total_price:.2f}")
        print(f"  GST Percentage:     {gst_percentage}%")
        print(f"  Commission Rate:    {commission_rate}%")
        print(f"\nCalculated Results:")
        print(f"  Base Amount:       Rs {result['base_amount']:.2f}")
        print(f"  GST Amount:         Rs {result['gst_amount']:.2f}")
        print(f"  Commission Amount:  Rs {result['commission_amount']:.2f}")
        print(f"  Amount After GST:   Rs {result['amount_after_gst']:.2f}")
        print(f"\nVerification:")
        total_calculated = result['base_amount'] + result['commission_amount'] + result['gst_amount']
        print(f"  Base + GST + Commission = Rs {total_calculated:.2f}")
        print(f"  Original Total          = Rs {total_price:.2f}")
        print(f"  Match: {'✓ PASS' if abs(float(total_calculated) - float(total_price)) < 0.01 else '✗ FAIL'}")
        print("="*70)
        
        # Expected calculations:
        # Step 1: Extract GST
        # x = 100 / 1.18 = 84.7457...
        # gst = 100 - 84.7457 = 15.2542...
        
        # Step 2: Extract Commission
        # y = 84.7457 / 1.3 = 65.1889...
        # commission = 84.7457 - 65.1889 = 19.5568...
        
        self.assertIn('base_amount', result)
        self.assertIn('gst_amount', result)
        self.assertIn('commission_amount', result)
        self.assertIn('amount_after_gst', result)
        
        # Verify calculations are approximately correct (within 0.01)
        expected_amount_after_gst = Decimal('84.75')  # Approximate
        expected_gst = Decimal('15.25')  # Approximate
        expected_base = Decimal('65.19')  # Approximate
        expected_commission = Decimal('19.56')  # Approximate
        
        self.assertAlmostEqual(float(result['amount_after_gst']), float(expected_amount_after_gst), places=1)
        self.assertAlmostEqual(float(result['gst_amount']), float(expected_gst), places=1)
        self.assertAlmostEqual(float(result['base_amount']), float(expected_base), places=1)
        self.assertAlmostEqual(float(result['commission_amount']), float(expected_commission), places=1)
        
        # Verify: base + commission + gst should approximately equal total
        self.assertAlmostEqual(float(total_calculated), float(total_price), places=1)
    
    def test_extract_gst_and_commission_150_rs(self):
        """Test extraction with Rs 150, 18% GST, 30% commission"""
        total_price = Decimal('150.00')
        gst_percentage = Decimal('18.0')
        commission_rate = Decimal('30.0')
        
        result = extract_gst_and_commission(total_price, gst_percentage, commission_rate)
        
        # PRINT CALCULATED VALUES
        print("\n" + "="*70)
        print("GST/COMMISSION CALCULATION TEST - Rs 150")
        print("="*70)
        print(f"Input Values:")
        print(f"  Total Price:        Rs {total_price:.2f}")
        print(f"  GST Percentage:     {gst_percentage}%")
        print(f"  Commission Rate:    {commission_rate}%")
        print(f"\nCalculated Results:")
        print(f"  Base Amount:       Rs {result['base_amount']:.2f}")
        print(f"  GST Amount:         Rs {result['gst_amount']:.2f}")
        print(f"  Commission Amount:  Rs {result['commission_amount']:.2f}")
        print(f"  Amount After GST:   Rs {result['amount_after_gst']:.2f}")
        print(f"\nVerification:")
        total_calculated = result['base_amount'] + result['commission_amount'] + result['gst_amount']
        print(f"  Base + GST + Commission = Rs {total_calculated:.2f}")
        print(f"  Original Total          = Rs {total_price:.2f}")
        print(f"  Match: {'✓ PASS' if abs(float(total_calculated) - float(total_price)) < 0.01 else '✗ FAIL'}")
        print("="*70)
        
        # Verify all keys exist
        self.assertIn('base_amount', result)
        self.assertIn('gst_amount', result)
        self.assertIn('commission_amount', result)
        self.assertIn('amount_after_gst', result)
        
        # Verify: base + commission + gst should approximately equal total
        self.assertAlmostEqual(float(total_calculated), float(total_price), places=1)
    
    def test_extract_gst_and_commission_zero_total(self):
        """Test extraction with zero total price"""
        total_price = Decimal('0.00')
        gst_percentage = Decimal('18.0')
        commission_rate = Decimal('30.0')
        
        result = extract_gst_and_commission(total_price, gst_percentage, commission_rate)
        
        # PRINT CALCULATED VALUES
        print("\n" + "="*70)
        print("GST/COMMISSION CALCULATION TEST - Rs 0 (Edge Case)")
        print("="*70)
        print(f"Input Values:")
        print(f"  Total Price:        Rs {total_price:.2f}")
        print(f"\nCalculated Results:")
        print(f"  Base Amount:       Rs {result['base_amount']:.2f}")
        print(f"  GST Amount:         Rs {result['gst_amount']:.2f}")
        print(f"  Commission Amount:  Rs {result['commission_amount']:.2f}")
        print(f"  Amount After GST:   Rs {result['amount_after_gst']:.2f}")
        print(f"  Result: All values should be Rs 0.00 ✓")
        print("="*70)
        
        self.assertEqual(result['base_amount'], Decimal('0.00'))
        self.assertEqual(result['gst_amount'], Decimal('0.00'))
        self.assertEqual(result['commission_amount'], Decimal('0.00'))
        self.assertEqual(result['amount_after_gst'], Decimal('0.00'))


class ProcessOrderInvoicesTestCase(TestCase):
    """Test cases for process_order_invoices function"""
    
    def setUp(self):
        """Set up test data"""
        self.customer = User.objects.create_user(
            username='test_customer',
            email='customer@test.com',
            password='test123'
        )
        
        self.designer1 = User.objects.create_user(
            username='designer1',
            email='designer1@test.com',
            password='test123'
        )
        
        self.designer2 = User.objects.create_user(
            username='designer2',
            email='designer2@test.com',
            password='test123'
        )
        
        # Create category
        self.category = Category.objects.create(
            name='Test Category',
            created_by=self.customer
        )
        
        # Create products with prices
        self.product1 = Product.objects.create(
            title='Design 1',
            description='Test design 1',
            category=self.category,
            product_plan_type='free',
            status='active',
            price=Decimal('50.00'),
            created_by=self.designer1
        )
        
        self.product2 = Product.objects.create(
            title='Design 2',
            description='Test design 2',
            category=self.category,
            product_plan_type='free',
            status='active',
            price=Decimal('50.00'),
            created_by=self.designer1
        )
        
        self.product3 = Product.objects.create(
            title='Design 3',
            description='Test design 3',
            category=self.category,
            product_plan_type='free',
            status='active',
            price=Decimal('50.00'),
            created_by=self.designer2
        )
        
        # Create order with products from multiple designers
        self.order = Order.objects.create(
            order_type='cart',
            status='success',
            total_amount=Decimal('150.00'),
            product_ids=f'{self.product1.id},{self.product2.id},{self.product3.id}',  # 2 from designer1, 1 from designer2
            created_by=self.customer
        )
    
    @patch('common.tasks.send_customer_invoice_email_async')
    @patch('common.tasks.send_designer_invoice_email_async')
    def test_process_order_invoices_success(self, mock_designer_email, mock_customer_email):
        """Test successful invoice processing for an order"""
        print("\n" + "="*70)
        print("ORDER INVOICE PROCESSING TEST")
        print("="*70)
        print(f"Order Details:")
        print(f"  Order ID:          {self.order.id}")
        print(f"  Order Type:        {self.order.order_type}")
        print(f"  Total Amount:      Rs {self.order.total_amount:.2f}")
        print(f"  Products:          3 designs (2 from Designer1, 1 from Designer2)")
        print(f"  Customer:          {self.customer.username}")
        
        result = process_order_invoices(self.order)
        
        # PRINT ORDER BREAKDOWN
        breakdown = calculate_order_breakdown(self.order)
        print(f"\nOrder Breakdown:")
        print(f"  Total Amount:      Rs {breakdown['total_amount']:.2f}")
        print(f"  Number of Designers: {len(breakdown['designer_breakdown'])}")
        
        for designer_id, db in breakdown['designer_breakdown'].items():
            designer = User.objects.get(id=designer_id)
            print(f"\n  Designer: {designer.username} (ID: {designer_id})")
            print(f"    Product Total:     Rs {db['product_total']:.2f}")
            print(f"    GST (18%):          Rs {db['gst_amount']:.2f}")
            print(f"    Commission (30%):   Rs {db['commission_amount']:.2f}")
            print(f"    Wallet Amount:      Rs {db['wallet_amount']:.2f}")
            print(f"    Bill Total:         Rs {db['gst_amount'] + db['commission_amount']:.2f}")
        
        # Verify result structure
        self.assertIn('customer_invoice', result)
        self.assertIn('designer_invoices', result)
        self.assertIn('wallet_transactions', result)
        
        # Verify customer invoice was created
        customer_invoice = Invoice.objects.filter(
            order=self.order,
            invoice_type='customer',
            user=self.customer
        ).first()
        self.assertIsNotNone(customer_invoice)
        self.assertEqual(customer_invoice.total_amount, Decimal('150.00'))
        
        print(f"\nCustomer Invoice:")
        print(f"  Invoice Number:    {customer_invoice.invoice_number}")
        print(f"  Total Amount:      Rs {customer_invoice.total_amount:.2f}")
        print(f"  Subtotal:          Rs {customer_invoice.subtotal:.2f}")
        print(f"  GST:               Rs {customer_invoice.gst_amount:.2f}")
        
        # Verify designer invoices were created
        designer_invoices = Invoice.objects.filter(
            order=self.order,
            invoice_type='designer'
        )
        self.assertEqual(designer_invoices.count(), 2)  # One for each designer
        
        print(f"\nDesigner Invoices Created: {designer_invoices.count()}")
        for inv in designer_invoices:
            designer = inv.user
            print(f"\n  Designer: {designer.username}")
            print(f"    Invoice Number:    {inv.invoice_number}")
            print(f"    Subtotal:           Rs {inv.subtotal:.2f}")
            print(f"    GST:                Rs {inv.gst_amount:.2f}")
            print(f"    Commission:         Rs {inv.commission_amount:.2f}")
            print(f"    Bill Total:         Rs {inv.total_amount:.2f}")
        
        # Verify wallets were credited
        wallet1 = Wallet.objects.get(created_by=self.designer1)
        wallet2 = Wallet.objects.get(created_by=self.designer2)
        self.assertGreater(wallet1.balance, Decimal('0'))
        self.assertGreater(wallet2.balance, Decimal('0'))
        
        print(f"\nWallet Credits:")
        print(f"  Designer1 Wallet:   Rs {wallet1.balance:.2f}")
        print(f"  Designer2 Wallet:   Rs {wallet2.balance:.2f}")
        
        # Verify wallet transactions were created
        transactions1 = WalletTransaction.objects.filter(created_by=self.designer1)
        transactions2 = WalletTransaction.objects.filter(created_by=self.designer2)
        self.assertGreater(transactions1.count(), 0)
        self.assertGreater(transactions2.count(), 0)
        
        print(f"\nWallet Transactions:")
        print(f"  Designer1: {transactions1.count()} transaction(s)")
        for txn in transactions1:
            print(f"    - {txn.description}: Rs {txn.amount:.2f}")
        print(f"  Designer2: {transactions2.count()} transaction(s)")
        for txn in transactions2:
            print(f"    - {txn.description}: Rs {txn.amount:.2f}")
        
        print("="*70)


class ProcessSubscriptionSettlementTestCase(TestCase):
    """Test cases for process_subscription_settlement (monthly subscriptions)"""
    
    def setUp(self):
        """Set up test data"""
        self.customer = User.objects.create_user(
            username='test_customer',
            email='customer@test.com',
            password='test123'
        )
        
        self.designer1 = User.objects.create_user(
            username='designer1',
            email='designer1@test.com',
            password='test123'
        )
        
        self.designer2 = User.objects.create_user(
            username='designer2',
            email='designer2@test.com',
            password='test123'
        )
        
        # Create category
        self.category = Category.objects.create(
            name='Test Category',
            created_by=self.customer
        )
        
        # Create products
        self.product1 = Product.objects.create(
            title='Design 1',
            description='Test design 1',
            category=self.category,
            product_plan_type='free',
            status='active',
            created_by=self.designer1
        )
        
        self.product2 = Product.objects.create(
            title='Design 2',
            description='Test design 2',
            category=self.category,
            product_plan_type='free',
            status='active',
            created_by=self.designer2
        )
        
        # Create monthly plan
        self.monthly_plan = Plan.objects.create(
            plan_name='basic',
            description={'features': ['20 downloads']},
            price=Decimal('400.00'),
            plan_duration='monthly',
            no_of_free_downloads=20,
            created_by=self.customer
        )
        
        # Create subscription (created 35 days ago)
        past_date = timezone.now() - timedelta(days=35)
        self.subscription = Subscription.objects.create(
            plan=self.monthly_plan,
            status='active',
            settlement_processed=False,
            created_by=self.customer,
            created_at=past_date
        )
        
        # Create subscription orders with downloads
        Order.objects.create(
            subscription=self.subscription,
            order_type='subscription',
            status='success',
            product_ids=f'{self.product1.id},{self.product1.id},{self.product1.id},{self.product1.id},{self.product1.id},{self.product1.id}',  # 6 downloads from designer1
            total_amount=Decimal('0'),
            created_by=self.customer,
            created_at=past_date + timedelta(days=5)
        )
        
        Order.objects.create(
            subscription=self.subscription,
            order_type='subscription',
            status='success',
            product_ids=f'{self.product2.id},{self.product2.id},{self.product2.id},{self.product2.id}',  # 4 downloads from designer2
            total_amount=Decimal('0'),
            created_by=self.customer,
            created_at=past_date + timedelta(days=10)
        )
    
    @patch('common.tasks.send_designer_subscription_invoice_email_async')
    def test_process_subscription_settlement_success(self, mock_email):
        """Test successful monthly subscription settlement"""
        print("\n" + "="*70)
        print("MONTHLY SUBSCRIPTION SETTLEMENT TEST")
        print("="*70)
        print(f"Subscription Details:")
        print(f"  Subscription ID:   {self.subscription.id}")
        print(f"  Plan:               {self.subscription.plan.plan_name}")
        print(f"  Plan Price:        Rs {self.subscription.plan.price:.2f}")
        print(f"  Total Downloads:   20 (allowed)")
        print(f"  Status:            {self.subscription.status}")
        
        result = process_subscription_settlement(self.subscription)
        
        print(f"\nSettlement Results:")
        print(f"  Total Downloads Used: {result['total_downloads']}")
        print(f"  Per Download Price:   Rs {result['per_download_price']:.2f}")
        print(f"  Calculation:         Rs {self.subscription.plan.price:.2f} / {result['total_downloads']} = Rs {result['per_download_price']:.2f}")
        
        print(f"\nDesigner Breakdown:")
        for designer_id, db in result['designer_breakdown'].items():
            designer = User.objects.get(id=designer_id)
            print(f"\n  Designer: {designer.username} (ID: {designer_id})")
            print(f"    Downloads Used:     {db.get('download_count', 0)}")
            print(f"    Product Total:     Rs {db['product_total']:.2f}")
            print(f"    GST (18%):          Rs {db['gst_amount']:.2f}")
            print(f"    Commission (30%):   Rs {db['commission_amount']:.2f}")
            print(f"    Wallet Amount:      Rs {db['wallet_amount']:.2f}")
            print(f"    Bill Total:         Rs {db['gst_amount'] + db['commission_amount']:.2f}")
        
        # Verify result structure
        self.assertIn('subscription_id', result)
        self.assertIn('total_downloads', result)
        self.assertIn('per_download_price', result)
        self.assertIn('designer_breakdown', result)
        
        # Verify subscription was marked as expired and processed
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, 'expired')
        self.assertTrue(self.subscription.settlement_processed)
        
        print(f"\nSubscription Status After Settlement:")
        print(f"  Status:              {self.subscription.status}")
        print(f"  Settlement Processed: {self.subscription.settlement_processed}")
        
        # Verify designer invoices were created
        designer_invoices = Invoice.objects.filter(
            subscription=self.subscription,
            invoice_type='designer'
        )
        self.assertEqual(designer_invoices.count(), 2)  # One for each designer
        
        print(f"\nDesigner Invoices Created: {designer_invoices.count()}")
        for inv in designer_invoices:
            designer = inv.user
            print(f"\n  Designer: {designer.username}")
            print(f"    Invoice Number:    {inv.invoice_number}")
            print(f"    Subtotal:           Rs {inv.subtotal:.2f}")
            print(f"    GST:                Rs {inv.gst_amount:.2f}")
            print(f"    Commission:         Rs {inv.commission_amount:.2f}")
            print(f"    Bill Total:         Rs {inv.total_amount:.2f}")
        
        # Verify wallets were credited
        wallet1 = Wallet.objects.get(created_by=self.designer1)
        wallet2 = Wallet.objects.get(created_by=self.designer2)
        self.assertGreater(wallet1.balance, Decimal('0'))
        self.assertGreater(wallet2.balance, Decimal('0'))
        
        print(f"\nWallet Credits:")
        print(f"  Designer1 Wallet:   Rs {wallet1.balance:.2f}")
        print(f"  Designer2 Wallet:   Rs {wallet2.balance:.2f}")
        
        # Verify calculations
        # Total downloads: 10
        # Per download price: 400 / 10 = 40
        # Designer1: 6 * 40 = 240
        # Designer2: 4 * 40 = 160
        self.assertEqual(result['total_downloads'], 10)
        self.assertEqual(result['per_download_price'], Decimal('40.00'))
        
        print("="*70)
    
    def test_process_subscription_settlement_no_downloads(self):
        """Test subscription settlement with no downloads"""
        print("\n" + "="*70)
        print("MONTHLY SUBSCRIPTION SETTLEMENT TEST - NO DOWNLOADS")
        print("="*70)
        
        # Create subscription with no orders
        subscription_no_downloads = Subscription.objects.create(
            plan=self.monthly_plan,
            status='active',
            settlement_processed=False,
            created_by=self.customer,
            created_at=timezone.now() - timedelta(days=35)
        )
        
        print(f"Subscription Details:")
        print(f"  Subscription ID:   {subscription_no_downloads.id}")
        print(f"  Plan Price:        Rs {subscription_no_downloads.plan.price:.2f}")
        print(f"  Downloads Used:     0")
        
        result = process_subscription_settlement(subscription_no_downloads)
        
        print(f"\nSettlement Results:")
        print(f"  Message:            {result.get('message', 'N/A')}")
        print(f"  Total Downloads:    {result['total_downloads']}")
        print(f"  Result:             No financial settlement (no downloads used)")
        
        # Should return message about no downloads
        self.assertIn('message', result)
        self.assertEqual(result['total_downloads'], 0)
        
        # Subscription should still be marked as expired and processed
        subscription_no_downloads.refresh_from_db()
        self.assertEqual(subscription_no_downloads.status, 'expired')
        self.assertTrue(subscription_no_downloads.settlement_processed)
        
        print(f"\nSubscription Status After Settlement:")
        print(f"  Status:              {subscription_no_downloads.status}")
        print(f"  Settlement Processed: {subscription_no_downloads.settlement_processed}")
        print("="*70)


class ProcessMonthlySubscriptionSettlementTestCase(TestCase):
    """Test cases for process_monthly_subscription_settlement (annual subscriptions)"""
    
    def setUp(self):
        """Set up test data"""
        self.customer = User.objects.create_user(
            username='test_customer',
            email='customer@test.com',
            password='test123'
        )
        
        self.designer1 = User.objects.create_user(
            username='designer1',
            email='designer1@test.com',
            password='test123'
        )
        
        self.designer2 = User.objects.create_user(
            username='designer2',
            email='designer2@test.com',
            password='test123'
        )
        
        # Create category
        self.category = Category.objects.create(
            name='Test Category',
            created_by=self.customer
        )
        
        # Create products
        self.product1 = Product.objects.create(
            title='Design 1',
            description='Test design 1',
            category=self.category,
            product_plan_type='free',
            status='active',
            created_by=self.designer1
        )
        
        self.product2 = Product.objects.create(
            title='Design 2',
            description='Test design 2',
            category=self.category,
            product_plan_type='free',
            status='active',
            created_by=self.designer2
        )
        
        # Create annual plan
        self.annual_plan = Plan.objects.create(
            plan_name='premium',
            description={'features': ['120 downloads']},
            price=Decimal('1200.00'),
            plan_duration='annually',
            no_of_free_downloads=120,
            created_by=self.customer
        )
        
        # Create subscription (purchased 35 days ago)
        purchase_date = timezone.now() - timedelta(days=35)
        self.subscription = Subscription.objects.create(
            plan=self.annual_plan,
            status='active',
            last_settled_month=None,  # Never settled
            created_by=self.customer,
            created_at=purchase_date
        )
        
        # Create orders in first 30-day period
        period_start = purchase_date
        period_end = purchase_date + timedelta(days=30)
        
        Order.objects.create(
            subscription=self.subscription,
            order_type='subscription',
            status='success',
            product_ids=f'{self.product1.id},{self.product1.id},{self.product1.id},{self.product1.id},{self.product1.id}',  # 5 downloads from designer1
            total_amount=Decimal('0'),
            created_by=self.customer,
            created_at=period_start + timedelta(days=5)
        )
        
        Order.objects.create(
            subscription=self.subscription,
            order_type='subscription',
            status='success',
            product_ids=f'{self.product2.id},{self.product2.id}',  # 2 downloads from designer2
            total_amount=Decimal('0'),
            created_by=self.customer,
            created_at=period_start + timedelta(days=15)
        )
    
    @patch('common.tasks.send_designer_subscription_invoice_email_async')
    def test_process_monthly_subscription_settlement_first_period(self, mock_email):
        """Test first monthly settlement for annual subscription"""
        period_start = self.subscription.created_at.date()
        period_end = period_start + timedelta(days=30)
        
        print("\n" + "="*70)
        print("ANNUAL SUBSCRIPTION - MONTHLY SETTLEMENT TEST (First Period)")
        print("="*70)
        print(f"Subscription Details:")
        print(f"  Subscription ID:   {self.subscription.id}")
        print(f"  Plan:               {self.subscription.plan.plan_name}")
        print(f"  Plan Price:         Rs {self.subscription.plan.price:.2f} (Annual)")
        print(f"  Total Downloads:    120 (allowed per year)")
        print(f"  Monthly Allocation: 10 downloads")
        print(f"  Monthly Price:      Rs {self.subscription.plan.price / 12:.2f}")
        print(f"\nSettlement Period:")
        print(f"  Period Start:      {period_start}")
        print(f"  Period End:         {period_end}")
        
        result = process_monthly_subscription_settlement(
            self.subscription,
            period_start,
            period_end
        )
        
        print(f"\nSettlement Results:")
        print(f"  Downloads Used:     {result['total_downloads_used']}")
        print(f"  Downloads Settled:  {result['total_downloads_settled']} (monthly allocation)")
        print(f"  Monthly Price:      Rs {result.get('monthly_price', 0):.2f}")
        
        print(f"\nDesigner Breakdown:")
        for designer_id, db in result['designer_breakdown'].items():
            designer = User.objects.get(id=designer_id)
            print(f"\n  Designer: {designer.username} (ID: {designer_id})")
            print(f"    Downloads Used:     {db.get('download_count', 0)}")
            print(f"    Product Total:      Rs {db['product_total']:.2f}")
            print(f"    GST (18%):           Rs {db['gst_amount']:.2f}")
            print(f"    Commission (30%):    Rs {db['commission_amount']:.2f}")
            print(f"    Wallet Amount:       Rs {db['wallet_amount']:.2f}")
            print(f"    Bill Total:          Rs {db['gst_amount'] + db['commission_amount']:.2f}")
        
        # Verify result structure
        self.assertIn('subscription_id', result)
        self.assertIn('period_start', result)
        self.assertIn('period_end', result)
        self.assertIn('total_downloads_used', result)
        self.assertIn('total_downloads_settled', result)
        self.assertIn('designer_breakdown', result)
        
        # Verify downloads
        self.assertEqual(result['total_downloads_used'], 7)
        self.assertEqual(result['total_downloads_settled'], 10)  # Monthly allocation
        
        # Verify subscription last_settled_month was updated
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.last_settled_month, period_end)
        
        print(f"\nSubscription Status After Settlement:")
        print(f"  Last Settled Month: {self.subscription.last_settled_month}")
        
        # Verify designer invoices were created
        designer_invoices = Invoice.objects.filter(
            subscription=self.subscription,
            invoice_type='designer'
        )
        self.assertEqual(designer_invoices.count(), 2)
        
        print(f"\nDesigner Invoices Created: {designer_invoices.count()}")
        for inv in designer_invoices:
            designer = inv.user
            print(f"\n  Designer: {designer.username}")
            print(f"    Invoice Number:    {inv.invoice_number}")
            print(f"    Subtotal:           Rs {inv.subtotal:.2f}")
            print(f"    GST:                Rs {inv.gst_amount:.2f}")
            print(f"    Commission:         Rs {inv.commission_amount:.2f}")
            print(f"    Bill Total:         Rs {inv.total_amount:.2f}")
        
        # Verify wallets were credited
        wallet1 = Wallet.objects.get(created_by=self.designer1)
        wallet2 = Wallet.objects.get(created_by=self.designer2)
        self.assertGreater(wallet1.balance, Decimal('0'))
        self.assertGreater(wallet2.balance, Decimal('0'))
        
        print(f"\nWallet Credits:")
        print(f"  Designer1 Wallet:   Rs {wallet1.balance:.2f}")
        print(f"  Designer2 Wallet:   Rs {wallet2.balance:.2f}")
        print("="*70)
    
    def test_process_monthly_subscription_settlement_no_downloads(self):
        """Test monthly settlement with no downloads in period"""
        print("\n" + "="*70)
        print("ANNUAL SUBSCRIPTION - MONTHLY SETTLEMENT TEST (No Downloads)")
        print("="*70)
        
        # Create subscription with no orders
        subscription_no_downloads = Subscription.objects.create(
            plan=self.annual_plan,
            status='active',
            last_settled_month=None,
            created_by=self.customer,
            created_at=timezone.now() - timedelta(days=35)
        )
        
        period_start = subscription_no_downloads.created_at.date()
        period_end = period_start + timedelta(days=30)
        
        print(f"Subscription Details:")
        print(f"  Subscription ID:   {subscription_no_downloads.id}")
        print(f"  Plan Price:        Rs {subscription_no_downloads.plan.price:.2f} (Annual)")
        print(f"  Monthly Price:     Rs {subscription_no_downloads.plan.price / 12:.2f}")
        print(f"  Downloads Used:     0")
        print(f"\nSettlement Period:")
        print(f"  Period Start:      {period_start}")
        print(f"  Period End:        {period_end}")
        
        result = process_monthly_subscription_settlement(
            subscription_no_downloads,
            period_start,
            period_end
        )
        
        print(f"\nSettlement Results:")
        print(f"  Message:            {result.get('message', 'N/A')}")
        print(f"  Downloads Used:     {result['total_downloads_used']}")
        print(f"  Result:             No financial settlement (0 downloads used)")
        print(f"  Note:               Amount remains with platform")
        
        # Should return message about no downloads
        self.assertIn('message', result)
        self.assertEqual(result['total_downloads_used'], 0)
        
        # last_settled_month should still be updated
        subscription_no_downloads.refresh_from_db()
        self.assertEqual(subscription_no_downloads.last_settled_month, period_end)
        
        print(f"\nSubscription Status After Settlement:")
        print(f"  Last Settled Month: {subscription_no_downloads.last_settled_month}")
        print("="*70)


class ProcessExpiredSubscriptionsTaskTestCase(TestCase):
    """Test cases for process_subscription_billing Celery task"""
    
    def setUp(self):
        """Set up test data"""
        self.customer = User.objects.create_user(
            username='test_customer',
            email='customer@test.com',
            password='test123'
        )
        
        self.designer1 = User.objects.create_user(
            username='designer1',
            email='designer1@test.com',
            password='test123'
        )
        
        # Create category
        self.category = Category.objects.create(
            name='Test Category',
            created_by=self.customer
        )
        
        # Create product
        self.product1 = Product.objects.create(
            title='Design 1',
            description='Test design 1',
            category=self.category,
            product_plan_type='free',
            status='active',
            created_by=self.designer1
        )
        
        # Create monthly plan
        self.monthly_plan = Plan.objects.create(
            plan_name='basic',
            description={'features': ['20 downloads']},
            price=Decimal('400.00'),
            plan_duration='monthly',
            no_of_free_downloads=20,
            created_by=self.customer
        )
        
        # Create annual plan
        self.annual_plan = Plan.objects.create(
            plan_name='premium',
            description={'features': ['120 downloads']},
            price=Decimal('1200.00'),
            plan_duration='annually',
            no_of_free_downloads=120,
            created_by=self.customer
        )
    
    @patch('common.tasks.send_designer_subscription_invoice_email_async')
    @patch('Orders.invoice_service.process_subscription_settlement')
    def test_process_subscription_billing_monthly(self, mock_settlement, mock_email):
        """Test Celery task processes monthly subscriptions"""
        print("\n" + "="*70)
        print("CELERY TASK TEST - MONTHLY SUBSCRIPTION SETTLEMENT")
        print("="*70)
        
        # Create monthly subscription ready for settlement
        past_date = timezone.now() - timedelta(days=35)
        monthly_sub = Subscription.objects.create(
            plan=self.monthly_plan,
            status='active',
            settlement_processed=False,
            created_by=self.customer,
            created_at=past_date
        )
        
        print(f"Subscription Details:")
        print(f"  Subscription ID:   {monthly_sub.id}")
        print(f"  Plan:               {monthly_sub.plan.plan_name}")
        print(f"  Plan Price:        Rs {monthly_sub.plan.price:.2f}")
        print(f"  Created At:        {monthly_sub.created_at.date()}")
        print(f"  Days Since Created: 35 days")
        print(f"  Status:            {monthly_sub.status}")
        print(f"  Settlement Processed: {monthly_sub.settlement_processed}")
        
        # Create order
        order = Order.objects.create(
            subscription=monthly_sub,
            order_type='subscription',
            status='success',
            product_ids=f'{self.product1.id},{self.product1.id},{self.product1.id}',
            total_amount=Decimal('0'),
            created_by=self.customer,
            created_at=past_date + timedelta(days=5)
        )
        
        print(f"\nOrder Details:")
        print(f"  Order ID:          {order.id}")
        print(f"  Downloads:          3")
        print(f"  Product IDs:        {order.product_ids}")
        
        # Mock the settlement function to return success
        mock_settlement.return_value = {
            'subscription_id': monthly_sub.id,
            'total_downloads': 3,
            'per_download_price': Decimal('133.33')
        }
        
        print(f"\nMocked Settlement Result:")
        print(f"  Total Downloads:   {mock_settlement.return_value['total_downloads']}")
        print(f"  Per Download Price: Rs {mock_settlement.return_value['per_download_price']:.2f}")
        
        # Call the task
        result = process_subscription_billing()
        
        print(f"\nTask Execution:")
        print(f"  Task Result:        {result}")
        print(f"  Settlement Called:  {mock_settlement.called}")
        
        # Verify task was called
        self.assertIsNotNone(result)
        print("="*70)
    
    @patch('common.tasks.send_designer_subscription_invoice_email_async')
    @patch('Orders.invoice_service.process_monthly_subscription_settlement')
    def test_process_subscription_billing_annual(self, mock_settlement, mock_email):
        """Test Celery task processes annual subscriptions"""
        print("\n" + "="*70)
        print("CELERY TASK TEST - ANNUAL SUBSCRIPTION SETTLEMENT")
        print("="*70)
        
        # Create annual subscription ready for first settlement
        past_date = timezone.now() - timedelta(days=35)
        annual_sub = Subscription.objects.create(
            plan=self.annual_plan,
            status='active',
            last_settled_month=None,
            created_by=self.customer,
            created_at=past_date
        )
        
        print(f"Subscription Details:")
        print(f"  Subscription ID:   {annual_sub.id}")
        print(f"  Plan:               {annual_sub.plan.plan_name}")
        print(f"  Plan Price:        Rs {annual_sub.plan.price:.2f} (Annual)")
        print(f"  Monthly Price:     Rs {annual_sub.plan.price / 12:.2f}")
        print(f"  Created At:        {annual_sub.created_at.date()}")
        print(f"  Days Since Created: 35 days")
        print(f"  Last Settled Month: {annual_sub.last_settled_month}")
        
        # Create order
        order = Order.objects.create(
            subscription=annual_sub,
            order_type='subscription',
            status='success',
            product_ids=f'{self.product1.id},{self.product1.id},{self.product1.id}',
            total_amount=Decimal('0'),
            created_by=self.customer,
            created_at=past_date + timedelta(days=5)
        )
        
        print(f"\nOrder Details:")
        print(f"  Order ID:          {order.id}")
        print(f"  Downloads:          3")
        print(f"  Product IDs:        {order.product_ids}")
        
        period_start = past_date.date()
        period_end = period_start + timedelta(days=30)
        
        # Mock the settlement function
        mock_settlement.return_value = {
            'subscription_id': annual_sub.id,
            'period_start': period_start.strftime('%Y-%m-%d'),
            'period_end': period_end.strftime('%Y-%m-%d'),
            'total_downloads_used': 3,
            'total_downloads_settled': 10
        }
        
        print(f"\nMocked Settlement Result:")
        print(f"  Period Start:       {mock_settlement.return_value['period_start']}")
        print(f"  Period End:         {mock_settlement.return_value['period_end']}")
        print(f"  Downloads Used:    {mock_settlement.return_value['total_downloads_used']}")
        print(f"  Downloads Settled:  {mock_settlement.return_value['total_downloads_settled']}")
        
        # Call the task
        result = process_subscription_billing()
        
        print(f"\nTask Execution:")
        print(f"  Task Result:        {result}")
        print(f"  Settlement Called:  {mock_settlement.called}")
        
        # Verify task was called
        self.assertIsNotNone(result)
        print("="*70)


class WalletTransactionTestCase(TestCase):
    """Test cases for wallet transactions during settlement"""
    
    def setUp(self):
        """Set up test data"""
        self.designer = User.objects.create_user(
            username='designer',
            email='designer@test.com',
            password='test123'
        )
    
    def test_wallet_creation_on_settlement(self):
        """Test wallet is created when designer receives settlement"""
        print("\n" + "="*70)
        print("WALLET CREATION TEST")
        print("="*70)
        print(f"Designer: {self.designer.username}")
        
        # Wallet should not exist initially
        wallet_exists_before = Wallet.objects.filter(created_by=self.designer).exists()
        print(f"Wallet Exists Before: {wallet_exists_before}")
        self.assertFalse(wallet_exists_before)
        
        # Create wallet (simulating settlement)
        wallet, created = Wallet.objects.get_or_create(created_by=self.designer)
        print(f"Wallet Created: {created}")
        
        # Convert balance to Decimal if it's not already
        current_balance = Decimal(str(wallet.balance)) if wallet.balance else Decimal('0.00')
        credit_amount = Decimal('100.00')
        wallet.balance = current_balance + credit_amount
        wallet.save()
        
        print(f"\nWallet Transaction:")
        print(f"  Initial Balance:   Rs {current_balance:.2f}")
        print(f"  Credit Amount:     Rs {credit_amount:.2f}")
        print(f"  Final Balance:      Rs {wallet.balance:.2f}")
        
        # Verify wallet was created
        self.assertTrue(Wallet.objects.filter(created_by=self.designer).exists())
        self.assertEqual(wallet.balance, Decimal('100.00'))
        print("="*70)
    
    def test_wallet_transaction_creation(self):
        """Test wallet transaction is created during settlement"""
        print("\n" + "="*70)
        print("WALLET TRANSACTION CREATION TEST")
        print("="*70)
        print(f"Designer: {self.designer.username}")
        
        wallet, _ = Wallet.objects.get_or_create(created_by=self.designer)
        print(f"Wallet ID: {wallet.id}")
        
        # Create transaction
        transaction = WalletTransaction.objects.create(
            wallet_transaction_type='credit',
            amount=Decimal('100.00'),
            description='Test settlement',
            reference_id='test_ref_123',
            created_by=self.designer
        )
        
        wallet.attach_wallet_transaction(transaction)
        
        print(f"\nTransaction Details:")
        print(f"  Transaction ID:    {transaction.id}")
        print(f"  Type:              {transaction.wallet_transaction_type}")
        print(f"  Amount:            Rs {transaction.amount:.2f}")
        print(f"  Description:       {transaction.description}")
        print(f"  Reference ID:      {transaction.reference_id}")
        
        # Verify transaction was created
        self.assertTrue(WalletTransaction.objects.filter(created_by=self.designer).exists())
        self.assertEqual(transaction.amount, Decimal('100.00'))
        self.assertEqual(transaction.wallet_transaction_type, 'credit')
        print("="*70)


class InvoiceModelTestCase(TestCase):
    """Test cases for Invoice model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='test123'
        )
    
    def test_invoice_creation(self):
        """Test invoice creation with reverse calculation values"""
        print("\n" + "="*70)
        print("INVOICE MODEL CREATION TEST")
        print("="*70)
        
        # Use reverse calculation values for Rs 100 total
        # For Rs 100 with 18% GST and 30% commission:
        # Base amount: 65.19, GST: 15.25, Commission: 19.56, Total: 100.00
        # For customer invoice: subtotal = base_amount, gst = extracted GST, total = 100
        invoice = Invoice.objects.create(
            invoice_number='INV-TEST-001',
            invoice_type='customer',
            user=self.user,
            subtotal=Decimal('65.19'),  # Base amount (what goes to designers)
            gst_amount=Decimal('15.25'),  # Extracted GST (18% reverse calculation)
            commission_amount=Decimal('0.00'),  # Customer doesn't pay commission directly
            total_amount=Decimal('100.00')  # Total amount customer paid (includes GST + commission)
        )
        
        print(f"Invoice Details:")
        print(f"  Invoice Number:    {invoice.invoice_number}")
        print(f"  Invoice Type:      {invoice.invoice_type}")
        print(f"  User:              {invoice.user.username}")
        print(f"  Subtotal:          Rs {invoice.subtotal:.2f} (base amount)")
        print(f"  GST Amount:        Rs {invoice.gst_amount:.2f} (extracted from total)")
        print(f"  Commission Amount: Rs {invoice.commission_amount:.2f}")
        print(f"  Total Amount:      Rs {invoice.total_amount:.2f} (customer paid)")
        print(f"  Invoice Date:      {invoice.invoice_date}")
        print(f"\nNote: Using reverse calculation - Total Rs 100 includes GST and commission")
        print(f"  Base (65.19) + GST (15.25) + Commission (19.56) = Rs 100.00")
        
        self.assertEqual(invoice.invoice_number, 'INV-TEST-001')
        self.assertEqual(invoice.invoice_type, 'customer')
        self.assertEqual(invoice.user, self.user)
        self.assertEqual(invoice.total_amount, Decimal('100.00'))
        print("="*70)
    
    def test_invoice_number_generation(self):
        """Test invoice number generation"""
        print("\n" + "="*70)
        print("INVOICE NUMBER GENERATION TEST")
        print("="*70)
        
        invoice = Invoice()
        invoice_number = invoice.generate_invoice_number()
        
        print(f"Generated Invoice Number: {invoice_number}")
        print(f"Format Check: Starts with 'INV-' = {invoice_number.startswith('INV-')}")
        
        self.assertIsNotNone(invoice_number)
        self.assertTrue(invoice_number.startswith('INV-'))
        print("="*70)

