from django.core.management.base import BaseCommand
from freezegun import freeze_time
from datetime import datetime, date
import pytz
from django.utils import timezone
from common.tasks import (
    process_monthly_settlements, 
    process_settlement_payouts,
    generate_and_send_designer_bill_async
)
from Wallet.models import SettlementRequest


class Command(BaseCommand):
    help = 'Quick settlement test: Create, opt-in, generate bill, and optionally process payout'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Date to simulate Day 1 (YYYY-MM-DD). Must be day 1 of a month. Default: 1st of current month'
        )
        parser.add_argument(
            '--skip-payout',
            action='store_true',
            help='Skip Day 6 payout processing (only create, opt-in, and send bills)'
        )
        parser.add_argument(
            '--skip-bill',
            action='store_true',
            help='Skip bill generation and email sending'
        )

    def handle(self, *args, **options):
        kolkata_tz = pytz.timezone('Asia/Kolkata')
        
        # Determine target date
        if options['date']:
            try:
                target_date = datetime.strptime(options['date'], '%Y-%m-%d')
                if target_date.day != 1:
                    self.stdout.write(self.style.ERROR('Date must be the 1st of a month!'))
                    return
                target_month = target_date.month
                target_year = target_date.year
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD'))
                return
        else:
            # Default to 1st of current month
            now = datetime.now(kolkata_tz)
            target_month = now.month
            target_year = now.year
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('QUICK SETTLEMENT TEST - FULL FLOW'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(f'\nTarget month: {target_year}-{target_month:02d}')
        self.stdout.write('\nSteps:')
        self.stdout.write('  1. Day 1: Create settlement requests')
        self.stdout.write('  2. Auto opt-in all settlements')
        if not options['skip_bill']:
            self.stdout.write('  3. Generate and send bill emails')
        if not options['skip_payout']:
            self.stdout.write('  4. Day 6: Process payouts')
        self.stdout.write('\n' + '=' * 70 + '\n')
        
        # Step 1: Day 1 - Create settlements
        day1 = kolkata_tz.localize(datetime(target_year, target_month, 1, 3, 0, 0))
        self.stdout.write(f'\n[Step 1] Day 1 - Creating settlement requests...')
        
        with freeze_time(day1):
            result = process_monthly_settlements()
            self.stdout.write(self.style.SUCCESS(f'✓ {result}'))
        
        # Calculate period
        if target_month == 1:
            period_start = date(target_year - 1, 12, 1)
        else:
            period_start = date(target_year, target_month - 1, 1)
        
        settlements = SettlementRequest.objects.filter(
            settlement_period_start=period_start,
            status='pending'
        )
        
        if settlements.count() == 0:
            self.stdout.write(self.style.WARNING('\n⚠️  No settlements created. Make sure:'))
            self.stdout.write(self.style.WARNING('  1. Designers are active'))
            self.stdout.write(self.style.WARNING('  2. Designers have DesignerProfile.status = "verified"'))
            self.stdout.write(self.style.WARNING('  3. Designers have wallets linked via relation system'))
            self.stdout.write(self.style.WARNING('  4. Designers have wallet balance > 0'))
            return
        
        self.stdout.write(f'\n✓ Created {settlements.count()} settlement requests')
        for settlement in settlements:
            designer_name = settlement.designer.username if settlement.designer else f"ID {settlement.designer_id}"
            self.stdout.write(f'  - Designer {designer_name}: ₹{settlement.settlement_amount}')
        
        # Step 2: Auto opt-in
        self.stdout.write(f'\n[Step 2] Auto opting-in all settlements...')
        opted_in_count = 0
        for settlement in settlements:
            try:
                settlement.opted_in = True
                settlement.opted_in_at = timezone.now()
                settlement.status = 'opted_in'
                settlement.save()
                opted_in_count += 1
                designer_name = settlement.designer.username if settlement.designer else f"ID {settlement.designer_id}"
                self.stdout.write(f'  ✓ Opted in: Designer {designer_name}')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Failed to opt-in settlement {settlement.id}: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Opted in {opted_in_count} settlements'))
        
        # Step 3: Generate and send bills
        if not options['skip_bill']:
            self.stdout.write(f'\n[Step 3] Generating and sending bill emails...')
            bills_sent = 0
            bills_failed = 0
            
            for settlement in settlements:
                try:
                    # Call the task directly (synchronously for testing)
                    result = generate_and_send_designer_bill_async(
                        designer_id=settlement.designer_id,
                        settlement_period_start=settlement.settlement_period_start.isoformat(),
                        settlement_period_end=settlement.settlement_period_end.isoformat(),
                        settlement_request_id=settlement.id
                    )
                    bills_sent += 1
                    designer_name = settlement.designer.username if settlement.designer else f"ID {settlement.designer_id}"
                    self.stdout.write(f'  ✓ Bill sent: Designer {designer_name} - {result}')
                except Exception as e:
                    bills_failed += 1
                    designer_name = settlement.designer.username if settlement.designer else f"ID {settlement.designer_id}"
                    self.stdout.write(self.style.ERROR(f'  ✗ Failed to send bill for Designer {designer_name}: {str(e)}'))
            
            self.stdout.write(self.style.SUCCESS(f'\n✓ Bills sent: {bills_sent}, Failed: {bills_failed}'))
        else:
            self.stdout.write(self.style.WARNING('\n[Step 3] Skipped bill generation'))
        
        # Step 4: Day 6 - Process payouts
        if not options['skip_payout']:
            day6 = kolkata_tz.localize(datetime(target_year, target_month, 6, 3, 0, 0))
            self.stdout.write(f'\n[Step 4] Day 6 - Processing payouts...')
            
            with freeze_time(day6):
                result = process_settlement_payouts()
                self.stdout.write(self.style.SUCCESS(f'✓ {result}'))
            
            # Show processed settlements - refetch to get updated status
            processed = SettlementRequest.objects.filter(
                settlement_period_start=period_start,
                status__in=['processing', 'completed']
            )
            self.stdout.write(f'\n✓ Processed {processed.count()} settlements')
            for settlement in processed:
                designer_name = settlement.designer.username if settlement.designer else f"ID {settlement.designer_id}"
                self.stdout.write(f'  - Designer {designer_name}: ₹{settlement.settlement_amount} ({settlement.status})')
        else:
            self.stdout.write(self.style.WARNING('\n[Step 4] Skipped payout processing'))
        
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('✓ Quick settlement test complete!'))
        if not options['skip_payout']:
            self.stdout.write(self.style.SUCCESS('Check admin panel at /settlements to download sheet'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

