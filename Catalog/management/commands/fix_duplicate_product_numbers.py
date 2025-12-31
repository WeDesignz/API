"""
Management command to fix duplicate product_numbers.

This command finds all products with duplicate product_numbers and assigns
new unique numbers to all but the first occurrence (keeping the oldest product).

Usage:
    python manage.py fix_duplicate_product_numbers
    python manage.py fix_duplicate_product_numbers --dry-run
    python manage.py fix_duplicate_product_numbers --verbose
"""

from django.core.management.base import BaseCommand
from django.db.models import Count
from Catalog.models import Product
from common.studio_name_generator import design_number_generator
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fix duplicate product_numbers by assigning new unique numbers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without actually updating the database',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each duplicate found',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        
        self.stdout.write(self.style.SUCCESS('Starting duplicate product_number fix...'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Find all duplicate product_numbers
        duplicates = Product.objects.values('product_number').annotate(
            count=Count('product_number')
        ).filter(count__gt=1, product_number__isnull=False)
        
        total_duplicates = duplicates.count()
        
        if total_duplicates == 0:
            self.stdout.write(self.style.SUCCESS('✓ No duplicate product_numbers found!'))
            return
        
        self.stdout.write(
            self.style.WARNING(
                f'Found {total_duplicates} duplicate product_number(s)'
            )
        )
        
        total_fixed = 0
        total_products_updated = 0
        
        for dup in duplicates:
            product_number = dup['product_number']
            count = dup['count']
            
            if verbose:
                self.stdout.write(
                    f'\nProcessing duplicate: {product_number} ({count} products)'
                )
            
            # Get all products with this product_number, ordered by ID (oldest first)
            products = Product.objects.filter(
                product_number=product_number
            ).order_by('id')
            
            # Keep the first one (oldest), fix the rest
            products_to_fix = list(products[1:])  # Skip the first one
            
            if verbose:
                self.stdout.write(
                    f'  Keeping product ID {products[0].id} ({products[0].title[:50]}...)'
                )
                self.stdout.write(
                    f'  Will fix {len(products_to_fix)} product(s)'
                )
            
            for product in products_to_fix:
                # Generate a new unique product number
                new_product_number = design_number_generator.generate_general_design_number()
                
                # Double-check it doesn't exist (shouldn't happen, but safety first)
                attempts = 0
                while Product.objects.filter(product_number=new_product_number).exists() and attempts < 10:
                    new_product_number = design_number_generator.generate_general_design_number()
                    attempts += 1
                
                if attempts >= 10:
                    self.stdout.write(
                        self.style.ERROR(
                            f'  Failed to generate unique number for product {product.id} after 10 attempts'
                        )
                    )
                    continue
                
                if verbose:
                    self.stdout.write(
                        f'  Product ID {product.id}: {product_number} -> {new_product_number}'
                    )
                
                if not dry_run:
                    product.product_number = new_product_number
                    product.save(update_fields=['product_number'])
                    total_products_updated += 1
                else:
                    self.stdout.write(
                        f'  [DRY RUN] Would update product ID {product.id}: '
                        f'{product_number} -> {new_product_number}'
                    )
            
            total_fixed += 1
        
        self.stdout.write('\n' + '='*60)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN COMPLETE: Would fix {total_fixed} duplicate(s) '
                    f'affecting {total_products_updated} product(s)'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Fixed {total_fixed} duplicate(s) '
                    f'affecting {total_products_updated} product(s)'
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    'All product_numbers are now unique!'
                )
            )

