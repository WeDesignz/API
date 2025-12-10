"""
Management command to generate monthly bills for designers.
Usage:
    python manage.py generate_monthly_designer_bills [--month YYYY-MM] [--regenerate]
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from Orders.models import Order, Invoice
from Orders.invoice_service import create_designer_invoice, calculate_order_breakdown
from django.conf import settings
from django.utils import timezone
from datetime import datetime, date, timedelta
from collections import defaultdict
from decimal import Decimal
import os


class Command(BaseCommand):
    help = 'Generate monthly bills for all designers based on orders in the current month (or specified month).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--month',
            type=str,
            help='Month in YYYY-MM format (default: current month)',
            default=None
        )
        parser.add_argument(
            '--regenerate',
            action='store_true',
            help='Regenerate bills even if they already exist'
        )
        parser.add_argument(
            '--designer-id',
            type=int,
            help='Generate bill for specific designer only'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            help='Custom output directory for PDF (default: media/invoices)'
        )

    def handle(self, *args, **options):
        month_str = options.get('month')
        regenerate = options.get('regenerate', False)
        designer_id = options.get('designer_id')
        output_dir = options.get('output_dir')

        # Parse month or use current month
        if month_str:
            try:
                year, month = map(int, month_str.split('-'))
                period_start = date(year, month, 1)
                # Calculate last day of month
                if month == 12:
                    period_end = date(year + 1, 1, 1) - timedelta(days=1)
                else:
                    period_end = date(year, month + 1, 1) - timedelta(days=1)
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid month format. Use YYYY-MM (e.g., 2024-12)'))
                return
        else:
            # Use current month
            today = timezone.now().date()
            period_start = date(today.year, today.month, 1)
            if today.month == 12:
                period_end = date(today.year + 1, 1, 1) - timedelta(days=1)
            else:
                period_end = date(today.year, today.month + 1, 1) - timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(
            f'Generating monthly bills for period: {period_start} to {period_end}'
        ))

        # Set custom output directory if provided
        original_media_root = None
        if output_dir:
            original_media_root = settings.MEDIA_ROOT
            settings.MEDIA_ROOT = output_dir
            self.stdout.write(self.style.SUCCESS(f'Using custom output directory: {output_dir}'))
            os.makedirs(output_dir, exist_ok=True)

        try:
            # Get all successful orders in the period
            orders = Order.objects.filter(
                status='success',
                created_at__date__gte=period_start,
                created_at__date__lte=period_end
            ).exclude(product_ids__isnull=True).exclude(product_ids='')

            if not orders.exists():
                self.stdout.write(self.style.WARNING('No successful orders found in this period.'))
                return

            self.stdout.write(f'Found {orders.count()} successful order(s) in period')

            # Aggregate orders by designer
            designer_orders = defaultdict(list)
            
            for order in orders:
                breakdown = calculate_order_breakdown(order)
                if breakdown.get('designer_breakdown'):
                    for did, dbreakdown in breakdown['designer_breakdown'].items():
                        if designer_id and did != designer_id:
                            continue
                        designer_orders[did].append({
                            'order': order,
                            'breakdown': dbreakdown
                        })

            if not designer_orders:
                self.stdout.write(self.style.WARNING('No designers found in orders for this period.'))
                return

            self.stdout.write(f'Found {len(designer_orders)} designer(s) with orders')

            # Generate bills for each designer
            bills_created = 0
            bills_skipped = 0

            for designer_id_key, order_list in designer_orders.items():
                designer = order_list[0]['breakdown']['designer']
                
                if designer_id and designer_id_key != designer_id:
                    continue

                self.stdout.write(f'\nProcessing Designer: {designer.username} (ID: {designer_id_key})')
                self.stdout.write(f'  Orders: {len(order_list)}')

                # Check if bill already exists for this period
                existing_bills = Invoice.objects.filter(
                    invoice_type='designer',
                    user=designer,
                    invoice_date__year=period_start.year,
                    invoice_date__month=period_start.month
                )

                if existing_bills.exists() and not regenerate:
                    self.stdout.write(self.style.WARNING(
                        f'  Bill already exists for this period. Use --regenerate to recreate.'
                    ))
                    for bill in existing_bills:
                        self.stdout.write(f'    - {bill.invoice_number}')
                    bills_skipped += 1
                    continue

                # Delete existing bills if regenerating
                if regenerate and existing_bills.exists():
                    deleted_count = existing_bills.count()
                    existing_bills.delete()
                    self.stdout.write(f'  Deleted {deleted_count} existing bill(s)')

                # Group orders by purchase type
                purchase_type_breakdowns = {
                    'individual': {
                        'gst_amount': Decimal('0'),
                        'commission_amount': Decimal('0'),
                        'product_total': Decimal('0'),
                        'design_count': 0,
                        'orders': []
                    },
                    'basic': {
                        'gst_amount': Decimal('0'),
                        'commission_amount': Decimal('0'),
                        'product_total': Decimal('0'),
                        'design_count': 0,
                        'orders': []
                    },
                    'prime': {
                        'gst_amount': Decimal('0'),
                        'commission_amount': Decimal('0'),
                        'product_total': Decimal('0'),
                        'design_count': 0,
                        'orders': []
                    },
                    'premium': {
                        'gst_amount': Decimal('0'),
                        'commission_amount': Decimal('0'),
                        'product_total': Decimal('0'),
                        'design_count': 0,
                        'orders': []
                    }
                }
                
                # Categorize each order by purchase type
                for order_data in order_list:
                    order = order_data['order']
                    dbreakdown = order_data['breakdown']
                    
                    # Determine purchase type
                    purchase_type = 'individual'
                    if order.subscription and order.subscription.plan:
                        plan_name = order.subscription.plan.plan_name
                        if plan_name in ['basic', 'prime', 'premium']:
                            purchase_type = plan_name
                    
                    # Count designs/products for this purchase type
                    design_count = len(dbreakdown.get('products', []))
                    
                    # Add to appropriate category
                    purchase_type_breakdowns[purchase_type]['gst_amount'] += Decimal(str(dbreakdown['gst_amount']))
                    purchase_type_breakdowns[purchase_type]['commission_amount'] += Decimal(str(dbreakdown['commission_amount']))
                    purchase_type_breakdowns[purchase_type]['product_total'] += Decimal(str(dbreakdown['product_total']))
                    purchase_type_breakdowns[purchase_type]['design_count'] += design_count
                    purchase_type_breakdowns[purchase_type]['orders'].append(order)
                
                # Remove empty categories
                purchase_type_breakdowns = {
                    k: v for k, v in purchase_type_breakdowns.items() 
                    if v['gst_amount'] > 0 or v['commission_amount'] > 0
                }
                
                if not purchase_type_breakdowns:
                    self.stdout.write(self.style.WARNING('  No valid breakdown data found'))
                    continue
                
                # Create monthly bill with all purchase types
                from Orders.invoice_service import create_monthly_designer_bill
                designer_bill = create_monthly_designer_bill(designer, purchase_type_breakdowns, period_start, period_end)
                
                self.stdout.write(self.style.SUCCESS(
                    f'  ✓ Bill created: {designer_bill.invoice_number}'
                ))
                
                # Show breakdown by purchase type
                for purchase_type, breakdown in purchase_type_breakdowns.items():
                    type_display = purchase_type.capitalize() if purchase_type != 'individual' else 'Individual Design'
                    self.stdout.write(f'    {type_display}:')
                    self.stdout.write(f'      GST: ₹{float(breakdown["gst_amount"]):.2f}')
                    self.stdout.write(f'      Commission: ₹{float(breakdown["commission_amount"]):.2f}')
                
                total_gst = sum(float(b['gst_amount']) for b in purchase_type_breakdowns.values())
                total_commission = sum(float(b['commission_amount']) for b in purchase_type_breakdowns.values())
                self.stdout.write(f'    Total GST: ₹{total_gst:.2f}')
                self.stdout.write(f'    Total Commission: ₹{total_commission:.2f}')
                self.stdout.write(f'    Grand Total: ₹{total_gst + total_commission:.2f}')
                
                if designer_bill.pdf_file_path:
                    self.stdout.write(f'    PDF: {designer_bill.pdf_file_path}')
                    if os.path.exists(designer_bill.pdf_file_path):
                        file_size = os.path.getsize(designer_bill.pdf_file_path)
                        self.stdout.write(f'    Size: {file_size / 1024:.2f} KB')
                
                bills_created += 1

            self.stdout.write(self.style.SUCCESS(
                f'\n✓ Monthly bill generation completed!'
            ))
            self.stdout.write(f'  Bills created: {bills_created}')
            self.stdout.write(f'  Bills skipped: {bills_skipped}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error generating bills: {str(e)}'))
            import traceback
            self.stdout.write(traceback.format_exc())
        finally:
            # Restore original MEDIA_ROOT if changed
            if output_dir and original_media_root:
                settings.MEDIA_ROOT = original_media_root

