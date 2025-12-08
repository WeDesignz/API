from django.core.management.base import BaseCommand
from freezegun import freeze_time
from datetime import datetime, date, timedelta
import pytz
from common.tasks import process_monthly_settlements, process_settlement_payouts
from Wallet.models import SettlementRequest


class Command(BaseCommand):
    help = 'Test settlement flow by simulating time progression'

    def add_arguments(self, parser):
        parser.add_argument(
            '--month',
            type=int,
            default=None,
            help='Month to simulate (1-12). Default: previous month'
        )
        parser.add_argument(
            '--year',
            type=int,
            default=None,
            help='Year to simulate. Default: current year'
        )
        parser.add_argument(
            '--skip-day6',
            action='store_true',
            help='Skip Day 6 processing (only create settlements)'
        )

    def handle(self, *args, **options):
        kolkata_tz = pytz.timezone('Asia/Kolkata')
        
        # Determine which month/year to simulate
        now = datetime.now(kolkata_tz)
        if options['month']:
            target_month = options['month']
            target_year = options['year'] or now.year
        else:
            # Default to previous month
            if now.month == 1:
                target_month = 12
                target_year = now.year - 1
            else:
                target_month = now.month - 1
                target_year = now.year
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('SETTLEMENT FLOW TEST - TIME SIMULATION'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(f'\nSimulating month: {target_year}-{target_month:02d}')
        self.stdout.write('\nSteps:')
        self.stdout.write('  1. Day 1: Create settlement requests')
        self.stdout.write('  2. Day 2-5: Designer opt-in window (manual via platform)')
        self.stdout.write('  3. Day 6: Process settlements')
        self.stdout.write('\n' + '=' * 70 + '\n')

        # Day 1: Create settlements
        day1 = kolkata_tz.localize(datetime(target_year, target_month, 1, 3, 0, 0))
        self.stdout.write(f'\n[Day 1 - {day1.strftime("%Y-%m-%d %H:%M")} IST] Creating settlement requests...')
        
        with freeze_time(day1):
            result = process_monthly_settlements()
            self.stdout.write(self.style.SUCCESS(f'✓ {result}'))
        
        # Show created settlements
        # Calculate the period that was used (previous month)
        if target_month == 1:
            period_start = date(target_year - 1, 12, 1)
        else:
            period_start = date(target_year, target_month - 1, 1)
        
        settlements = SettlementRequest.objects.filter(
            settlement_period_start=period_start
        )
        
        self.stdout.write(f'\nCreated {settlements.count()} settlement requests')
        for settlement in settlements:
            designer_name = settlement.designer.username if settlement.designer else f"ID {settlement.designer_id}"
            self.stdout.write(f'  - Designer {designer_name}: ₹{settlement.settlement_amount} ({settlement.status})')
        
        if settlements.count() == 0:
            self.stdout.write(self.style.WARNING('\n⚠️  No settlements created. Make sure:'))
            self.stdout.write(self.style.WARNING('  1. Designers have wallet balance > 0'))
            self.stdout.write(self.style.WARNING('  2. Designers have verified Razorpay onboarding status'))
            return
        
        # Day 6: Process settlements
        if not options['skip_day6']:
            day6 = kolkata_tz.localize(datetime(target_year, target_month, 6, 3, 0, 0))
            self.stdout.write(f'\n[Day 6 - {day6.strftime("%Y-%m-%d %H:%M")} IST] Processing settlements...')
            self.stdout.write(self.style.WARNING('⚠️  Make sure designers have opted in via platform before Day 6!'))
            
            # Check if any settlements are opted in
            opted_in_count = settlements.filter(status='opted_in').count()
            if opted_in_count == 0:
                self.stdout.write(self.style.WARNING(f'\n⚠️  No settlements are opted in yet ({settlements.count()} pending)'))
                self.stdout.write(self.style.WARNING('You can:'))
                self.stdout.write(self.style.WARNING('  1. Opt-in via platform UI'))
                self.stdout.write(self.style.WARNING('  2. Or manually update via Django shell'))
                self.stdout.write(self.style.WARNING('  3. Then run: python manage.py simulate_day6'))
                return
            
            self.stdout.write(f'\nFound {opted_in_count} opted-in settlements. Processing...')
            
            with freeze_time(day6):
                result = process_settlement_payouts()
                self.stdout.write(self.style.SUCCESS(f'✓ {result}'))
            
            # Show processed settlements
            settlements.refresh_from_db()
            processed = settlements.filter(status__in=['processing', 'completed'])
            self.stdout.write(f'\nProcessed {processed.count()} settlements')
            for settlement in processed:
                designer_name = settlement.designer.username if settlement.designer else f"ID {settlement.designer_id}"
                self.stdout.write(f'  - Designer {designer_name}: ₹{settlement.settlement_amount} ({settlement.status})')
        
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('✓ Settlement flow test complete!'))
        self.stdout.write(self.style.SUCCESS('Check admin panel at /settlements to download sheet'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

