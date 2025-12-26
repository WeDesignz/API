from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, date, timedelta
from decimal import Decimal
import pytz
import random

from Wallet.models import Wallet, WalletTransaction, SettlementRequest, SettlementTDS
from Profiles.models import DesignerProfile, Studio, StudioBusinessDetails
from Authentication.user_relations import get_user_wallets
from common.relations import attach_relation


class Command(BaseCommand):
    help = 'Create comprehensive demo data for testing TDS, download sheet, and receipt functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing demo settlement data before creating new data'
        )

    def handle(self, *args, **options):
        kolkata_tz = pytz.timezone('Asia/Kolkata')
        today = datetime.now(kolkata_tz).date()
        
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('CREATING COMPREHENSIVE TDS DEMO DATA'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        
        # Clear existing demo data if requested
        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing existing demo settlement data...'))
            demo_users = User.objects.filter(email__startswith='tds_demo_')
            SettlementRequest.objects.filter(designer_id__in=demo_users.values_list('id', flat=True)).delete()
            SettlementTDS.objects.filter(settlement_request__designer_id__in=demo_users.values_list('id', flat=True)).delete()
            self.stdout.write(self.style.SUCCESS('Cleared existing demo data\n'))

        # Create settlements for previous month (ready for download - Day 6 onwards)
        # These should have status: processing, completed, or failed
        previous_month = self.get_previous_month(today)
        self.create_settlements_for_period(
            period_start=previous_month['start'],
            period_end=previous_month['end'],
            settlement_date=previous_month['day6'],  # Day 6 of current month
            is_current_month=False
        )

        # Create settlements for current month (to test disabled download button)
        # These should be pending/opted_in (before Day 6)
        current_month = self.get_current_month(today)
        if today.day < 6:
            # If today is before Day 6, create pending settlements
            self.create_settlements_for_period(
                period_start=current_month['start'],
                period_end=current_month['end'],
                settlement_date=None,
                is_current_month=True
            )

        # Create settlements for 2 months ago (for history testing)
        two_months_ago = self.get_previous_month(previous_month['start'])
        self.create_settlements_for_period(
            period_start=two_months_ago['start'],
            period_end=two_months_ago['end'],
            settlement_date=two_months_ago['day6'],
            is_current_month=False
        )

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('Demo data creation completed!'))
        self.stdout.write('=' * 80)
        self.stdout.write('\nTest Scenarios Created:')
        self.stdout.write('  1. Previous month settlements (processing/completed/failed) - Ready for download')
        self.stdout.write('  2. Current month settlements (pending/opted_in) - Download disabled')
        self.stdout.write('  3. Two months ago settlements - For history filtering')
        self.stdout.write('  4. Designers with PAN (2% TDS) and without PAN (20% TDS)')
        self.stdout.write('\nAll demo designers have password: demo123')
        self.stdout.write('=' * 80 + '\n')

    def get_previous_month(self, reference_date):
        """Get previous month period dates"""
        if reference_date.month == 1:
            start = date(reference_date.year - 1, 12, 1)
            end = date(reference_date.year - 1, 12, 31)
            day6 = date(reference_date.year, 1, 6)
        else:
            start = date(reference_date.year, reference_date.month - 1, 1)
            if reference_date.month == 2:
                end = date(reference_date.year, reference_date.month - 1, 28)
            else:
                next_month = date(reference_date.year, reference_date.month, 1)
                end = next_month - timedelta(days=1)
            day6 = date(reference_date.year, reference_date.month, 6)
        return {'start': start, 'end': end, 'day6': day6}

    def get_current_month(self, today):
        """Get current month period dates"""
        start = date(today.year, today.month, 1)
        if today.month == 12:
            end = date(today.year, 12, 31)
        else:
            next_month = date(today.year, today.month + 1, 1)
            end = next_month - timedelta(days=1)
        day6 = date(today.year, today.month, 6)
        return {'start': start, 'end': end, 'day6': day6}

    def create_settlements_for_period(self, period_start, period_end, settlement_date, is_current_month):
        """Create settlements for a given period"""
        kolkata_tz = pytz.timezone('Asia/Kolkata')
        
        if is_current_month:
            # Current month: pending/opted_in statuses (before Day 6)
            statuses = ['pending', 'opted_in']
            self.stdout.write(f'\nCreating CURRENT MONTH settlements ({period_start} to {period_end})...')
        else:
            # Previous months: processing/completed/failed (Day 6 onwards)
            statuses = ['processing', 'completed', 'failed']
            self.stdout.write(f'\nCreating PREVIOUS MONTH settlements ({period_start} to {period_end})...')

        # Create designers with different scenarios
        scenarios = [
            # With PAN (2% TDS)
            {'has_pan': True, 'pan_number': 'ABCDE1234F', 'status': statuses[0] if statuses else 'pending', 'amount': Decimal('10000.00')},
            {'has_pan': True, 'pan_number': 'FGHIJ5678K', 'status': statuses[1] if len(statuses) > 1 else statuses[0], 'amount': Decimal('15000.00')},
            {'has_pan': True, 'pan_number': 'LMNOP9012Q', 'status': statuses[2] if len(statuses) > 2 else statuses[0], 'amount': Decimal('20000.00')},
            
            # Without PAN (20% TDS)
            {'has_pan': False, 'pan_number': None, 'status': statuses[0] if statuses else 'pending', 'amount': Decimal('8000.00')},
            {'has_pan': False, 'pan_number': None, 'status': statuses[1] if len(statuses) > 1 else statuses[0], 'amount': Decimal('12000.00')},
            {'has_pan': False, 'pan_number': None, 'status': statuses[2] if len(statuses) > 2 else statuses[0], 'amount': Decimal('18000.00')},
        ]

        for idx, scenario in enumerate(scenarios):
            try:
                # Create unique email based on period and scenario
                period_str = f"{period_start.year}{period_start.month:02d}"
                email = f'tds_demo_{period_str}_{idx+1}_{"pan" if scenario["has_pan"] else "nopan"}@wedesignz.com'
                name = f'TDS Demo {period_str} {idx+1} {"PAN" if scenario["has_pan"] else "NoPAN"}'
                
                # Create or get user
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        'username': email.split('@')[0],
                        'first_name': name.split()[2] if len(name.split()) > 2 else 'Demo',
                        'last_name': name.split()[3] if len(name.split()) > 3 else 'Designer',
                        'is_active': True,
                    }
                )
                if created:
                    user.set_password('demo123')
                    user.save()

                # Create designer profile
                profile, _ = DesignerProfile.objects.get_or_create(
                    created_by=user,
                    defaults={
                        'status': 'verified',
                        'onboarding_completed': True,
                        'bio': f'Demo designer for TDS testing - {name}',
                    }
                )
                profile.status = 'verified'
                profile.onboarding_completed = True
                profile.save()

                # Create studio
                studio, _ = Studio.objects.get_or_create(
                    created_by=user,
                    defaults={
                        'name': f"{name}'s Studio",
                        'wedesignz_auto_name': f"studio_{user.id}",
                        'studio_industry_type': 'design_studio',
                        'status': 'active',
                    }
                )

                # Create business details with/without PAN
                business_details, _ = StudioBusinessDetails.objects.get_or_create(
                    studio=studio,
                    defaults={
                        'bank_account_number': f'123456789{random.randint(100, 999)}',
                        'bank_ifsc_code': random.choice(['HDFC0001234', 'ICIC0005678', 'SBIN0009012']),
                        'bank_account_holder_name': name,
                        'account_type': 'savings',
                        'legal_business_name': f"{name} Business",
                        'pan_number': scenario['pan_number'],
                        'pan_card': f'https://example.com/pan_{user.id}.pdf' if scenario['has_pan'] else None,
                        'created_by': user,
                    }
                )
                # Update PAN if needed
                if scenario['has_pan'] and not business_details.pan_number:
                    business_details.pan_number = scenario['pan_number']
                    business_details.save()
                elif not scenario['has_pan']:
                    business_details.pan_number = None
                    business_details.pan_card = None
                    business_details.save()

                # Create or get wallet
                wallets = get_user_wallets(user)
                wallet = wallets.first()
                if not wallet:
                    wallet = Wallet.objects.create(created_by=user, balance=Decimal('0.00'))

                # Create wallet transactions
                transaction_count = random.randint(3, 6)
                total_credits = Decimal('0.00')
                
                for i in range(transaction_count):
                    transaction_date = period_start + timedelta(
                        days=random.randint(0, (period_end - period_start).days)
                    )
                    transaction_datetime = kolkata_tz.localize(
                        datetime.combine(transaction_date, datetime.min.time())
                    )
                    
                    amount = scenario['amount'] / Decimal(str(transaction_count))
                    amount = amount.quantize(Decimal('0.01'))
                    
                    transaction = WalletTransaction.objects.create(
                        wallet_transaction_type='credit',
                        amount=amount,
                        description=f"Earnings from order #{random.randint(1000, 9999)}",
                        reference_id=f"order_{random.randint(1000, 9999)}",
                        created_by=user,
                        created_at=transaction_datetime,
                    )
                    wallet.attach_wallet_transaction(transaction)
                    total_credits += amount

                wallet.balance = total_credits
                wallet.save()

                # Create settlement request
                settlement_request, created = SettlementRequest.objects.get_or_create(
                    designer_id=user.id,
                    settlement_period_start=period_start,
                    defaults={
                        'settlement_period_end': period_end,
                        'wallet_balance_at_period_end': scenario['amount'],
                        'settlement_amount': scenario['amount'],
                        'status': scenario['status'],
                    }
                )

                # Update settlement based on status
                if scenario['status'] == 'opted_in':
                    settlement_request.opted_in = True
                    settlement_request.opted_in_at = timezone.now() - timedelta(days=random.randint(1, 4))
                    settlement_request.status = 'opted_in'
                    
                elif scenario['status'] == 'processing':
                    settlement_request.opted_in = True
                    settlement_request.opted_in_at = timezone.now() - timedelta(days=6)
                    settlement_request.status = 'processing'
                    if settlement_date:
                        settlement_request.settlement_date = settlement_date
                    
                    # Mark transactions as settled
                    period_end_datetime = kolkata_tz.localize(
                        datetime.combine(period_end, datetime.max.time())
                    )
                    WalletTransaction.objects.filter(
                        created_by=user,
                        wallet_transaction_type='credit',
                        created_at__lte=period_end_datetime,
                        settlement_request__isnull=True
                    ).update(
                        settlement_request=settlement_request,
                        settled_at=timezone.now() - timedelta(days=2)
                    )
                    
                    # Create debit transaction
                    debit_transaction = WalletTransaction.objects.create(
                        wallet_transaction_type='debit',
                        amount=scenario['amount'],
                        description=f"Settlement for period {period_start} to {period_end}",
                        reference_id=f"settlement_{settlement_request.id}",
                        created_by=user,
                        created_at=kolkata_tz.localize(
                            datetime.combine(settlement_request.settlement_date or date.today(), datetime.min.time())
                        )
                    )
                    wallet.attach_wallet_transaction(debit_transaction)
                    wallet.balance = wallet.balance - scenario['amount']
                    wallet.save()
                    
                elif scenario['status'] == 'completed':
                    settlement_request.opted_in = True
                    settlement_request.opted_in_at = timezone.now() - timedelta(days=6)
                    settlement_request.status = 'completed'
                    if settlement_date:
                        settlement_request.settlement_date = settlement_date
                    settlement_request.razorpay_transfer_id = f'UTR{random.randint(100000, 999999)}'
                    
                    # Mark transactions as settled
                    period_end_datetime = kolkata_tz.localize(
                        datetime.combine(period_end, datetime.max.time())
                    )
                    WalletTransaction.objects.filter(
                        created_by=user,
                        wallet_transaction_type='credit',
                        created_at__lte=period_end_datetime,
                        settlement_request__isnull=True
                    ).update(
                        settlement_request=settlement_request,
                        settled_at=timezone.now() - timedelta(days=5)
                    )
                    
                    # Create debit transaction
                    debit_transaction = WalletTransaction.objects.create(
                        wallet_transaction_type='debit',
                        amount=scenario['amount'],
                        description=f"Settlement for period {period_start} to {period_end}",
                        reference_id=f"settlement_{settlement_request.id}",
                        created_by=user,
                        created_at=kolkata_tz.localize(
                            datetime.combine(settlement_request.settlement_date or date.today(), datetime.min.time())
                        )
                    )
                    wallet.attach_wallet_transaction(debit_transaction)
                    wallet.balance = wallet.balance - scenario['amount']
                    wallet.save()
                    
                elif scenario['status'] == 'failed':
                    settlement_request.opted_in = True
                    settlement_request.opted_in_at = timezone.now() - timedelta(days=6)
                    settlement_request.status = 'failed'
                    if settlement_date:
                        settlement_request.settlement_date = settlement_date
                    settlement_request.failure_reason = 'Bank account details incorrect'

                # Link designer to settlement request
                settlement_request.set_designer(user)
                settlement_request.save()

                # For Day 6 onwards settlements, create TDS record (simulating download)
                tds_info = None
                if settlement_date and scenario['status'] in ['processing', 'completed', 'failed']:
                    from Wallet.views import calculate_settlement_tds
                    tds_info = calculate_settlement_tds(settlement_request)
                    
                    SettlementTDS.objects.get_or_create(
                        settlement_request=settlement_request,
                        defaults={
                            'settlement_amount': settlement_request.settlement_amount,
                            'tds_percentage': tds_info['tds_percentage'],
                            'tds_amount': tds_info['tds_amount'],
                            'net_amount': tds_info['net_amount'],
                            'has_pan': tds_info['has_pan'],
                            'pan_number': tds_info['pan_number'],
                        }
                    )

                tds_display = f' - TDS: {tds_info["tds_percentage"]}%' if tds_info else ''
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Created {name}: ₹{scenario["amount"]} - '
                        f'Status: {scenario["status"]} - '
                        f'PAN: {"Yes" if scenario["has_pan"] else "No"}{tds_display}'
                    )
                )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Failed to create {scenario}: {str(e)}')
                )
                import traceback
                traceback.print_exc()

