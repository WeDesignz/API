"""
Management command to generate customer invoices for orders.
Usage:
    python manage.py generate_customer_invoice <order_id> [--regenerate]
"""

from django.core.management.base import BaseCommand
from Orders.models import Order, Invoice
from Orders.invoice_service import create_customer_invoice
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Generate customer invoice PDF for an order. Can regenerate existing invoices.'

    def add_arguments(self, parser):
        parser.add_argument(
            'order_id',
            type=int,
            help='Order ID to generate invoice for'
        )
        parser.add_argument(
            '--regenerate',
            action='store_true',
            help='Regenerate invoice even if it already exists'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            help='Custom output directory for PDF (default: media/invoices)'
        )

    def handle(self, *args, **options):
        order_id = options['order_id']
        regenerate = options.get('regenerate', False)
        output_dir = options.get('output_dir')

        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Order {order_id} not found'))
            return

        self.stdout.write(self.style.SUCCESS(f'Processing order: {order.order_number or order.id}'))
        self.stdout.write(f'Status: {order.status}')
        self.stdout.write(f'Total Amount: ₹{order.total_amount}')

        # Check if invoice already exists
        existing_invoices = Invoice.objects.filter(order=order, invoice_type='customer')
        if existing_invoices.exists() and not regenerate:
            self.stdout.write(self.style.WARNING(
                f'Customer invoice already exists for this order. Use --regenerate to recreate it.'
            ))
            for inv in existing_invoices:
                self.stdout.write(f'  - {inv.invoice_number}')
                if inv.pdf_file_path and os.path.exists(inv.pdf_file_path):
                    self.stdout.write(f'    PDF: {inv.pdf_file_path}')
            return

        # Set custom output directory if provided
        original_media_root = None
        if output_dir:
            original_media_root = settings.MEDIA_ROOT
            settings.MEDIA_ROOT = output_dir
            self.stdout.write(self.style.SUCCESS(f'Using custom output directory: {output_dir}'))
            os.makedirs(output_dir, exist_ok=True)

        try:
            # Delete existing customer invoice if regenerating
            if regenerate:
                deleted_count = existing_invoices.count()
                existing_invoices.delete()
                if deleted_count > 0:
                    self.stdout.write(f'Deleted {deleted_count} existing customer invoice(s)')

            self.stdout.write(self.style.SUCCESS('\nGenerating customer invoice...'))
            
            customer_invoice = create_customer_invoice(order)
            self.stdout.write(self.style.SUCCESS(
                f'✓ Customer invoice created: {customer_invoice.invoice_number}'
            ))
            if customer_invoice.pdf_file_path:
                self.stdout.write(f'  PDF: {customer_invoice.pdf_file_path}')
                if os.path.exists(customer_invoice.pdf_file_path):
                    file_size = os.path.getsize(customer_invoice.pdf_file_path)
                    self.stdout.write(f'  Size: {file_size / 1024:.2f} KB')

            self.stdout.write(self.style.SUCCESS('\n✓ Invoice generation completed!'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error generating invoice: {str(e)}'))
            import traceback
            self.stdout.write(traceback.format_exc())
        finally:
            # Restore original MEDIA_ROOT if changed
            if output_dir and original_media_root:
                settings.MEDIA_ROOT = original_media_root

