"""
Management command to generate invoice PDFs for orders.
Usage:
    python manage.py generate_invoice <order_id> [options]
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from Orders.models import Order, Invoice
from Orders.invoice_service import create_customer_invoice, create_designer_invoice, calculate_order_breakdown
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Generate invoice PDF for an order. Can regenerate existing invoices.'

    def add_arguments(self, parser):
        parser.add_argument(
            'order_id',
            type=int,
            help='Order ID to generate invoice for'
        )
        parser.add_argument(
            '--type',
            type=str,
            choices=['customer', 'designer', 'all'],
            default='all',
            help='Type of invoice to generate (customer, designer, or all)'
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
        parser.add_argument(
            '--designer-id',
            type=int,
            help='Designer ID (required if type is designer)'
        )

    def handle(self, *args, **options):
        order_id = options['order_id']
        invoice_type = options['type']
        regenerate = options['regenerate']
        output_dir = options.get('output_dir')
        designer_id = options.get('designer_id')

        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Order {order_id} not found'))
            return

        self.stdout.write(self.style.SUCCESS(f'Processing order: {order.order_number or order.id}'))
        self.stdout.write(f'Status: {order.status}')
        self.stdout.write(f'Total Amount: ₹{order.total_amount}')

        # Check if invoices already exist
        existing_invoices = Invoice.objects.filter(order=order)
        if existing_invoices.exists() and not regenerate:
            self.stdout.write(self.style.WARNING(
                f'Invoices already exist for this order. Use --regenerate to recreate them.'
            ))
            for inv in existing_invoices:
                self.stdout.write(f'  - {inv.invoice_number} ({inv.invoice_type})')
                if inv.pdf_file_path and os.path.exists(inv.pdf_file_path):
                    self.stdout.write(f'    PDF: {inv.pdf_file_path}')
            return

        # Set custom output directory if provided
        original_media_root = None
        if output_dir:
            original_media_root = settings.MEDIA_ROOT
            settings.MEDIA_ROOT = output_dir
            self.stdout.write(self.style.SUCCESS(f'Using custom output directory: {output_dir}'))
            # Ensure directory exists
            os.makedirs(output_dir, exist_ok=True)

        try:
            if invoice_type in ['customer', 'all']:
                self.stdout.write(self.style.SUCCESS('\nGenerating customer invoice...'))
                
                # Delete existing customer invoice if regenerating
                if regenerate:
                    customer_invoices = Invoice.objects.filter(order=order, invoice_type='customer')
                    deleted_count = customer_invoices.count()
                    customer_invoices.delete()
                    if deleted_count > 0:
                        self.stdout.write(f'  Deleted {deleted_count} existing customer invoice(s)')
                
                customer_invoice = create_customer_invoice(order)
                self.stdout.write(self.style.SUCCESS(
                    f'✓ Customer invoice created: {customer_invoice.invoice_number}'
                ))
                if customer_invoice.pdf_file_path:
                    self.stdout.write(f'  PDF: {customer_invoice.pdf_file_path}')
                    if os.path.exists(customer_invoice.pdf_file_path):
                        file_size = os.path.getsize(customer_invoice.pdf_file_path)
                        self.stdout.write(f'  Size: {file_size / 1024:.2f} KB')

            if invoice_type in ['designer', 'all']:
                self.stdout.write(self.style.SUCCESS('\nGenerating designer invoice(s)...'))
                
                breakdown = calculate_order_breakdown(order)
                
                if not breakdown.get('designer_breakdown'):
                    self.stdout.write(self.style.WARNING(
                        'No designers found in order breakdown. Order may not have products.'
                    ))
                    return
                
                if designer_id:
                    # Generate for specific designer
                    if designer_id not in breakdown['designer_breakdown']:
                        self.stdout.write(self.style.ERROR(
                            f'Designer {designer_id} not found in order breakdown'
                        ))
                        self.stdout.write('Available designers:')
                        for did, dbreakdown in breakdown['designer_breakdown'].items():
                            self.stdout.write(f'  - Designer ID {did}: {dbreakdown["designer"].username}')
                        return
                    
                    designer_breakdown = breakdown['designer_breakdown'][designer_id]
                    designer = designer_breakdown['designer']
                    
                    if regenerate:
                        designer_invoices = Invoice.objects.filter(
                            order=order,
                            invoice_type='designer',
                            user=designer
                        )
                        deleted_count = designer_invoices.count()
                        designer_invoices.delete()
                        if deleted_count > 0:
                            self.stdout.write(f'  Deleted {deleted_count} existing designer invoice(s)')
                    
                    designer_invoice = create_designer_invoice(order, designer, designer_breakdown)
                    self.stdout.write(self.style.SUCCESS(
                        f'✓ Designer invoice created: {designer_invoice.invoice_number}'
                    ))
                    self.stdout.write(f'  Designer: {designer.username} (ID: {designer.id})')
                    if designer_invoice.pdf_file_path:
                        self.stdout.write(f'  PDF: {designer_invoice.pdf_file_path}')
                        if os.path.exists(designer_invoice.pdf_file_path):
                            file_size = os.path.getsize(designer_invoice.pdf_file_path)
                            self.stdout.write(f'  Size: {file_size / 1024:.2f} KB')
                else:
                    # Generate for all designers
                    if regenerate:
                        designer_invoices = Invoice.objects.filter(order=order, invoice_type='designer')
                        deleted_count = designer_invoices.count()
                        designer_invoices.delete()
                        if deleted_count > 0:
                            self.stdout.write(f'  Deleted {deleted_count} existing designer invoice(s)')
                    
                    designer_count = len(breakdown['designer_breakdown'])
                    self.stdout.write(f'  Found {designer_count} designer(s) in order')
                    
                    for designer_id_key, designer_breakdown in breakdown['designer_breakdown'].items():
                        designer = designer_breakdown['designer']
                        designer_invoice = create_designer_invoice(order, designer, designer_breakdown)
                        self.stdout.write(self.style.SUCCESS(
                            f'✓ Designer invoice created: {designer_invoice.invoice_number}'
                        ))
                        self.stdout.write(f'  Designer: {designer.username} (ID: {designer.id})')
                        if designer_invoice.pdf_file_path:
                            self.stdout.write(f'  PDF: {designer_invoice.pdf_file_path}')
                            if os.path.exists(designer_invoice.pdf_file_path):
                                file_size = os.path.getsize(designer_invoice.pdf_file_path)
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

