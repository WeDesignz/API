from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Count
from datetime import datetime, date, timedelta
from decimal import Decimal
import pytz
import random

from Wallet.models import Wallet, WalletTransaction, SettlementRequest
from Profiles.models import DesignerProfile, Studio, StudioBusinessDetails
from Authentication.user_relations import get_user_wallets
from common.relations import attach_relation


class Command(BaseCommand):
    help = 'Create demo settlement data for testing admin settlement page'

    def add_arguments(self, parser):
        parser.add_argument(
            '--period',
            type=str,
            help='Settlement period start date (YYYY-MM-DD). Default: Previous month',
            default=None
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing demo settlement data before creating new data'
        )

    def handle(self, *args, **options):
        kolkata_tz = pytz.timezone('Asia/Kolkata')
        
        # Calculate settlement period (previous month)
        if options['period']:
            try:
                period_start = datetime.strptime(options['period'], '%Y-%m-%d').date()
                if period_start.day != 1:
                    self.stdout.write(self.style.ERROR('Period start must be the 1st of a month'))
                    return
                # Calculate period end (last day of that month)
                if period_start.month == 12:
                    period_end = date(period_start.year, 12, 31)
                else:
                    next_month = date(period_start.year, period_start.month + 1, 1)
                    period_end = next_month - timedelta(days=1)
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD'))
                return
        else:
            # Default to previous month
            today = datetime.now(kolkata_tz).date()
            if today.month == 1:
                period_start = date(today.year - 1, 12, 1)
                period_end = date(today.year - 1, 12, 31)
            else:
                period_start = date(today.year, today.month - 1, 1)
                first_day_current = date(today.year, today.month, 1)
                period_end = first_day_current - timedelta(days=1)

        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('CREATING DEMO SETTLEMENT DATA'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(f'\nSettlement Period: {period_start} to {period_end}\n')

        # Clear existing demo data if requested
        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing existing demo settlement data...'))
            # Delete demo settlements (those with demo email pattern)
            demo_users = User.objects.filter(email__startswith='demo_designer_')
            SettlementRequest.objects.filter(designer_id__in=demo_users.values_list('id', flat=True)).delete()
            self.stdout.write(self.style.SUCCESS('Cleared existing demo data\n'))

        # Create demo designers with different settlement statuses
        designers_data = [
            {
                'name': 'Demo Designer Pending',
                'email': 'demo_designer_pending@wedesignz.com',
                'amount': Decimal('5000.00'),
                'status': 'pending',
                'has_bank': True,
            },
            {
                'name': 'Demo Designer Opted In',
                'email': 'demo_designer_opted_in@wedesignz.com',
                'amount': Decimal('7500.00'),
                'status': 'opted_in',
                'has_bank': True,
            },
            {
                'name': 'Demo Designer Processing',
                'email': 'demo_designer_processing@wedesignz.com',
                'amount': Decimal('12000.00'),
                'status': 'processing',
                'has_bank': True,
                'settlement_date': date.today() - timedelta(days=2),  # 2 days ago
            },
            {
                'name': 'Demo Designer Completed',
                'email': 'demo_designer_completed@wedesignz.com',
                'amount': Decimal('8500.00'),
                'status': 'completed',
                'has_bank': True,
                'settlement_date': date.today() - timedelta(days=5),
                'manual_ref': 'UTR123456789',
            },
            {
                'name': 'Demo Designer Failed',
                'email': 'demo_designer_failed@wedesignz.com',
                'amount': Decimal('3000.00'),
                'status': 'failed',
                'has_bank': True,
                'settlement_date': date.today() - timedelta(days=3),
                'failure_reason': 'Bank account details incorrect',
            },
            {
                'name': 'Demo Designer Expired',
                'email': 'demo_designer_expired@wedesignz.com',
                'amount': Decimal('6000.00'),
                'status': 'expired',
                'has_bank': True,
                'settlement_date': date.today() - timedelta(days=8),  # 8 days ago (expired)
            },
            {
                'name': 'Demo Designer No Bank',
                'email': 'demo_designer_no_bank@wedesignz.com',
                'amount': Decimal('4000.00'),
                'status': 'pending',
                'has_bank': False,  # No bank details
            },
            {
                'name': 'Demo Designer Large Amount',
                'email': 'demo_designer_large@wedesignz.com',
                'amount': Decimal('50000.00'),
                'status': 'processing',
                'has_bank': True,
                'settlement_date': date.today() - timedelta(days=1),
            },
        ]

        created_count = 0
        for designer_data in designers_data:
            try:
                # Create or get user
                user, created = User.objects.get_or_create(
                    email=designer_data['email'],
                    defaults={
                        'username': designer_data['email'].split('@')[0],
                        'first_name': designer_data['name'].split()[1] if len(designer_data['name'].split()) > 1 else 'Demo',
                        'last_name': designer_data['name'].split()[2] if len(designer_data['name'].split()) > 2 else 'Designer',
                        'is_active': True,
                    }
                )
                if created:
                    user.set_password('demo123')
                    user.save()

                # Create or get designer profile
                profile, _ = DesignerProfile.objects.get_or_create(
                    created_by=user,
                    defaults={
                        'status': 'verified',
                        'onboarding_completed': True,
                        'bio': f'Demo designer profile for {designer_data["name"]}',
                    }
                )
                profile.status = 'verified'
                profile.onboarding_completed = True
                profile.save()

                # Create or get studio
                studio, _ = Studio.objects.get_or_create(
                    created_by=user,
                    defaults={
                        'name': f"{designer_data['name']}'s Studio",
                        'wedesignz_auto_name': f"studio_{user.id}",
                        'studio_industry_type': 'design_studio',
                        'status': 'active',
                    }
                )

                # Create or get business details with bank info
                if designer_data['has_bank']:
                    business_details, _ = StudioBusinessDetails.objects.get_or_create(
                        studio=studio,
                        defaults={
                            'bank_account_number': f'1234567890{random.randint(100, 999)}',
                            'bank_ifsc_code': 'HDFC0001234',
                            'bank_account_holder_name': designer_data['name'],
                            'account_type': 'savings',
                            'legal_business_name': f"{designer_data['name']} Business",
                            'pan_number': f'ABCDE{random.randint(1000, 9999)}F',
                            'created_by': user,
                        }
                    )
                else:
                    # Create business details without bank info
                    business_details, _ = StudioBusinessDetails.objects.get_or_create(
                        studio=studio,
                        defaults={
                            'legal_business_name': f"{designer_data['name']} Business",
                            'pan_number': f'ABCDE{random.randint(1000, 9999)}F',
                            'created_by': user,
                        }
                    )

                # Create or get wallet
                wallets = get_user_wallets(user)
                wallet = wallets.first()
                if not wallet:
                    # Wallet will be automatically linked to user via signal (auto_link_wallet_to_user)
                    wallet = Wallet.objects.create(created_by=user, balance=Decimal('0.00'))

                # Create wallet transactions (credits) to match settlement amount
                # These simulate earnings from orders/subscriptions
                transaction_count = random.randint(3, 8)
                total_credits = Decimal('0.00')
                
                # Create credit transactions throughout the period
                for i in range(transaction_count):
                    transaction_date = period_start + timedelta(
                        days=random.randint(0, (period_end - period_start).days)
                    )
                    transaction_datetime = kolkata_tz.localize(
                        datetime.combine(transaction_date, datetime.min.time())
                    )
                    
                    amount = designer_data['amount'] / Decimal(str(transaction_count))
                    amount = amount.quantize(Decimal('0.01'))
                    
                    transaction = WalletTransaction.objects.create(
                        wallet_transaction_type='credit',
                        amount=amount,
                        description=f"Earnings from order #{random.randint(1000, 9999)} ({random.randint(1, 5)} designs)",
                        reference_id=f"order_{random.randint(1000, 9999)}",
                        created_by=user,
                        created_at=transaction_datetime,
                    )
                    wallet.attach_wallet_transaction(transaction)
                    total_credits += amount

                # Adjust wallet balance
                wallet.balance = total_credits
                wallet.save()

                # Create settlement request
                settlement_request, created = SettlementRequest.objects.get_or_create(
                    designer_id=user.id,
                    settlement_period_start=period_start,
                    defaults={
                        'settlement_period_end': period_end,
                        'wallet_balance_at_period_end': designer_data['amount'],
                        'settlement_amount': designer_data['amount'],
                        'status': designer_data['status'],
                    }
                )

                # Update settlement based on status
                if designer_data['status'] == 'opted_in':
                    settlement_request.opted_in = True
                    settlement_request.opted_in_at = timezone.now() - timedelta(days=random.randint(1, 4))
                    settlement_request.status = 'opted_in'
                elif designer_data['status'] == 'processing':
                    settlement_request.opted_in = True
                    settlement_request.opted_in_at = timezone.now() - timedelta(days=5)
                    settlement_request.status = 'processing'
                    settlement_request.settlement_date = designer_data.get('settlement_date', date.today() - timedelta(days=2))
                    
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
                        amount=designer_data['amount'],
                        description=f"Settlement for period {period_start} to {period_end}",
                        reference_id=f"settlement_{settlement_request.id}",
                        created_by=user,
                        created_at=kolkata_tz.localize(
                            datetime.combine(settlement_request.settlement_date, datetime.min.time())
                        )
                    )
                    wallet.attach_wallet_transaction(debit_transaction)
                    wallet.balance = wallet.balance - designer_data['amount']
                    wallet.save()
                    
                elif designer_data['status'] == 'completed':
                    settlement_request.opted_in = True
                    settlement_request.opted_in_at = timezone.now() - timedelta(days=6)
                    settlement_request.status = 'completed'
                    settlement_request.settlement_date = designer_data.get('settlement_date', date.today() - timedelta(days=5))
                    settlement_request.razorpay_transfer_id = designer_data.get('manual_ref', 'UTR123456789')
                    
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
                        amount=designer_data['amount'],
                        description=f"Settlement for period {period_start} to {period_end}",
                        reference_id=f"settlement_{settlement_request.id}",
                        created_by=user,
                        created_at=kolkata_tz.localize(
                            datetime.combine(settlement_request.settlement_date, datetime.min.time())
                        )
                    )
                    wallet.attach_wallet_transaction(debit_transaction)
                    wallet.balance = wallet.balance - designer_data['amount']
                    wallet.save()
                    
                elif designer_data['status'] == 'failed':
                    settlement_request.opted_in = True
                    settlement_request.opted_in_at = timezone.now() - timedelta(days=6)
                    settlement_request.status = 'failed'
                    settlement_request.settlement_date = designer_data.get('settlement_date', date.today() - timedelta(days=3))
                    settlement_request.failure_reason = designer_data.get('failure_reason', 'Bank account details incorrect')
                    
                elif designer_data['status'] == 'expired':
                    settlement_request.opted_in = True
                    settlement_request.opted_in_at = timezone.now() - timedelta(days=9)
                    settlement_request.status = 'expired'
                    settlement_request.settlement_date = designer_data.get('settlement_date', date.today() - timedelta(days=8))
                    settlement_request.failure_reason = 'Settlement expired - not completed within 7 days of processing'

                # Link designer to settlement request
                settlement_request.set_designer(user)
                settlement_request.save()

                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Created {designer_data["name"]}: '
                        f'₹{designer_data["amount"]} - Status: {designer_data["status"]}'
                    )
                )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Failed to create {designer_data["name"]}: {str(e)}')
                )
                import traceback
                traceback.print_exc()

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS(f'Successfully created {created_count} demo settlements'))
        self.stdout.write('=' * 80)
        self.stdout.write('\nDemo Data Summary:')
        self.stdout.write(f'  - Period: {period_start} to {period_end}')
        self.stdout.write(f'  - Total Settlements: {created_count}')
        self.stdout.write('\nSettlement Statuses:')
        
        demo_users = User.objects.filter(email__startswith='demo_designer_')
        statuses = SettlementRequest.objects.filter(
            designer_id__in=demo_users.values_list('id', flat=True)
        ).values('status').annotate(
            count=Count('id')
        )
        
        for status_info in statuses:
            self.stdout.write(f'  - {status_info["status"]}: {status_info["count"]}')
        
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('Demo data creation completed!'))
        self.stdout.write('=' * 80)
        self.stdout.write('\nYou can now test the admin settlement page with this demo data.')
        self.stdout.write('All demo designers have password: demo123')
        self.stdout.write('\n')



