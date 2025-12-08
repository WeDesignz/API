from django.core.management.base import BaseCommand
from freezegun import freeze_time
from datetime import datetime, date, timedelta
import pytz
from common.tasks import process_monthly_settlements
from Wallet.models import SettlementRequest


class Command(BaseCommand):
    help = 'Simulate Day 1 - Create settlement requests'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Date to simulate (YYYY-MM-DD). Must be day 1 of a month'
        )

    def handle(self, *args, **options):
        kolkata_tz = pytz.timezone('Asia/Kolkata')
        
        if options['date']:
            try:
                target_date = datetime.strptime(options['date'], '%Y-%m-%d')
                if target_date.day != 1:
                    self.stdout.write(self.style.ERROR('Date must be the 1st of a month!'))
                    return
                target_datetime = kolkata_tz.localize(
                    datetime(target_date.year, target_date.month, 1, 3, 0, 0)
                )
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD'))
                return
        else:
            # Default to 1st of current month
            now = datetime.now(kolkata_tz)
            target_datetime = kolkata_tz.localize(
                datetime(now.year, now.month, 1, 3, 0, 0)
            )
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('SIMULATING DAY 1 - SETTLEMENT CREATION'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(f'\nSimulating: {target_datetime.strftime("%Y-%m-%d %H:%M")} IST')
        
        with freeze_time(target_datetime):
            result = process_monthly_settlements()
            self.stdout.write(self.style.SUCCESS(f'\n✓ {result}'))
        
        # Calculate period that was used
        if target_datetime.month == 1:
            period_start = date(target_datetime.year - 1, 12, 1)
        else:
            period_start = date(target_datetime.year, target_datetime.month - 1, 1)
        
        settlements = SettlementRequest.objects.filter(
            settlement_period_start=period_start
        )
        
        self.stdout.write(f'\nCreated {settlements.count()} settlement requests')
        if settlements.exists():
            self.stdout.write('\nSettlements:')
            for settlement in settlements:
                designer_name = settlement.designer.username if settlement.designer else f"ID {settlement.designer_id}"
                self.stdout.write(f'  - Designer {designer_name}: ₹{settlement.settlement_amount} ({settlement.status})')
                self.stdout.write(f'    Period: {settlement.settlement_period_start} to {settlement.settlement_period_end}')
        else:
            self.stdout.write(self.style.WARNING('\n⚠️  No settlements created. Make sure:'))
            self.stdout.write(self.style.WARNING('  1. Designers are active (is_active=True)'))
            self.stdout.write(self.style.WARNING('  2. Designers have DesignerProfile.status = "verified"'))
            self.stdout.write(self.style.WARNING('  3. Designers have wallets linked via relation system'))
            self.stdout.write(self.style.WARNING('  4. Designers have wallet balance > 0'))
        
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))

