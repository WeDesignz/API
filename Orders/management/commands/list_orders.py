"""
Management command to list orders for invoice generation.
Usage:
    python manage.py list_orders [--limit N]
"""

from django.core.management.base import BaseCommand
from Orders.models import Order
from django.db.models import Q


class Command(BaseCommand):
    help = 'List orders that can be used for invoice generation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=20,
            help='Maximum number of orders to display (default: 20)'
        )
        parser.add_argument(
            '--status',
            type=str,
            help='Filter by order status (e.g., success, pending)'
        )
        parser.add_argument(
            '--has-invoice',
            action='store_true',
            help='Show only orders that already have invoices'
        )
        parser.add_argument(
            '--no-invoice',
            action='store_true',
            help='Show only orders without invoices'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        status_filter = options.get('status')
        has_invoice = options.get('has_invoice')
        no_invoice = options.get('no_invoice')

        queryset = Order.objects.all()

        # Apply status filter
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Apply invoice filter
        if has_invoice:
            from Orders.models import Invoice
            order_ids_with_invoices = Invoice.objects.values_list('order_id', flat=True).distinct()
            queryset = queryset.filter(id__in=order_ids_with_invoices)
        elif no_invoice:
            from Orders.models import Invoice
            order_ids_with_invoices = Invoice.objects.values_list('order_id', flat=True).distinct()
            queryset = queryset.exclude(id__in=order_ids_with_invoices)

        # Order by most recent
        orders = queryset.order_by('-created_at')[:limit]

        if not orders.exists():
            self.stdout.write(self.style.WARNING('No orders found matching the criteria.'))
            return

        self.stdout.write(self.style.SUCCESS(f'\nFound {orders.count()} order(s):\n'))
        self.stdout.write('ID  | Order Number    | Status    | Amount      | Date')
        self.stdout.write('-' * 70)

        for order in orders:
            from Orders.models import Invoice
            invoice_count = Invoice.objects.filter(order=order).count()
            invoice_info = f'({invoice_count} invoice(s))' if invoice_count > 0 else '(no invoice)'
            
            order_number = order.order_number or f'ORD-{order.id}'
            date_str = order.created_at.strftime('%Y-%m-%d') if order.created_at else 'N/A'
            
            self.stdout.write(
                f'{str(order.id).ljust(4)} | {order_number.ljust(15)} | '
                f'{order.status.ljust(9)} | ₹{str(order.total_amount).ljust(10)} | '
                f'{date_str} {invoice_info}'
            )

        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(f'\nTo generate invoice for an order, use:')
        self.stdout.write(f'  python manage.py generate_invoice <order_id>')
        self.stdout.write(f'\nExample:')
        self.stdout.write(f'  python manage.py generate_invoice {orders.first().id}')

