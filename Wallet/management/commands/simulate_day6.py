from django.core.management.base import BaseCommand
from freezegun import freeze_time
from datetime import datetime
import pytz
from common.tasks import process_settlement_payouts
from Wallet.models import SettlementRequest


class Command(BaseCommand):
    help = 'Simulate Day 6 - Process settlement payouts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Date to simulate (YYYY-MM-DD). Must be day 6 of a month'
        )

    def handle(self, *args, **options):
        kolkata_tz = pytz.timezone('Asia/Kolkata')
        
        if options['date']:
            try:
                target_date = datetime.strptime(options['date'], '%Y-%m-%d')
                if target_date.day != 6:
                    self.stdout.write(self.style.ERROR('Date must be the 6th of a month!'))
                    return
                target_datetime = kolkata_tz.localize(
                    datetime(target_date.year, target_date.month, 6, 3, 0, 0)
                )
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD'))
                return
        else:
            # Default to 6th of current month
            now = datetime.now(kolkata_tz)
            target_datetime = kolkata_tz.localize(
                datetime(now.year, now.month, 6, 3, 0, 0)
            )
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('SIMULATING DAY 6 - SETTLEMENT PROCESSING'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(f'\nSimulating: {target_datetime.strftime("%Y-%m-%d %H:%M")} IST')
        
        # Check for opted-in settlements
        opted_in_settlements = SettlementRequest.objects.filter(
            status='opted_in',
            settlement_date__isnull=True
        )
        
        if opted_in_settlements.count() == 0:
            self.stdout.write(self.style.WARNING('\n⚠️  No opted-in settlements found!'))
            self.stdout.write(self.style.WARNING('Make sure designers have opted in via platform first.'))
            return
        
        self.stdout.write(f'\nFound {opted_in_settlements.count()} opted-in settlements to process')
        for settlement in opted_in_settlements:
            designer_name = settlement.designer.username if settlement.designer else f"ID {settlement.designer_id}"
            self.stdout.write(f'  - Designer {designer_name}: ₹{settlement.settlement_amount}')
        
        self.stdout.write('\nProcessing settlements...')
        
        with freeze_time(target_datetime):
            result = process_settlement_payouts()
            self.stdout.write(self.style.SUCCESS(f'\n✓ {result}'))
        
        # Show processed settlements
        opted_in_settlements.refresh_from_db()
        processed = opted_in_settlements.filter(status__in=['processing', 'completed'])
        self.stdout.write(f'\nProcessed {processed.count()} settlements')
        for settlement in processed:
            designer_name = settlement.designer.username if settlement.designer else f"ID {settlement.designer_id}"
            self.stdout.write(f'  - Designer {designer_name}: ₹{settlement.settlement_amount} ({settlement.status})')
            if settlement.settlement_date:
                self.stdout.write(f'    Settlement date: {settlement.settlement_date}')
        
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('✓ Check admin panel at /settlements to download sheet'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

