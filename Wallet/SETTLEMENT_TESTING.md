# Settlement Flow Testing Guide

This guide explains how to test the settlement flow using time simulation with `freezegun`.

## Prerequisites

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Ensure you have:
   - Designers with wallet balances > 0
   - Designers with verified Razorpay onboarding status
   - Orders created through the platform (which credit designer wallets)

## Testing Workflow

### Step 1: Create Test Data via Platform

1. Create orders for customers purchasing from designer "john" (or any designer)
2. Orders will automatically credit money to designer wallets when payment is captured
3. Verify wallet balances:
   ```python
   # In Django shell
   from Wallet.models import Wallet
   from django.contrib.auth.models import User
   from Authentication.user_relations import get_user_wallets
   
   designer = User.objects.get(username='john')
   wallets = get_user_wallets(designer)
   wallet = wallets.first()
   print(f"Wallet balance: ₹{wallet.balance}")
   ```

### Step 2: Simulate Day 1 - Create Settlement Requests

This simulates the first day of the month when settlement requests are created.

**Option A: Use full flow command (recommended)**
```bash
python manage.py test_settlement_flow --month 1 --year 2025
```

**Option B: Use individual Day 1 command**
```bash
python manage.py simulate_day1 --date 2025-01-01
```

**What happens:**
- Creates `SettlementRequest` objects for all designers with wallet balance > 0
- Sets status to `pending`
- Calculates settlement period (previous month)

**Verify:**
- Check admin panel at `/settlements`
- You should see settlement requests with status "pending"

### Step 3: Simulate Days 2-5 - Designer Opt-In

Designers need to opt-in during this window. You can do this:

**Option A: Via Platform UI**
- Designer logs in and opts in through the designer console

**Option B: Manually (for testing)**
```python
# In Django shell
from Wallet.models import SettlementRequest
from django.utils import timezone

settlement = SettlementRequest.objects.filter(
    designer_id=designer_id,
    status='pending'
).latest('created_at')

settlement.opted_in = True
settlement.status = 'opted_in'
settlement.opted_in_at = timezone.now()
settlement.save()
```

### Step 4: Simulate Day 6 - Process Settlements

This simulates day 6 when settlements are processed and wallets are debited.

```bash
python manage.py simulate_day6 --date 2025-01-06
```

**What happens:**
- Processes all opted-in settlements
- Deducts amount from designer wallets
- Creates debit transactions
- Sets status to `processing`
- Sets `settlement_date` to day 6

**Verify:**
- Check wallet balances (should be reduced)
- Check settlement status (should be "processing")
- Check admin panel - "Download Sheet" button should be available

### Step 5: Test Download Sheet

1. Go to admin panel: `/settlements`
2. Click "Download Sheet" button
3. Verify the Excel/CSV file contains:
   - Designer details
   - Settlement amounts
   - Period information
   - Status

## Available Commands

### `test_settlement_flow`
Complete end-to-end test of the settlement flow.

```bash
python manage.py test_settlement_flow [--month MONTH] [--year YEAR] [--skip-day6]
```

**Options:**
- `--month`: Month to simulate (1-12). Default: previous month
- `--year`: Year to simulate. Default: current year
- `--skip-day6`: Skip Day 6 processing (only create settlements)

**Example:**
```bash
# Test previous month
python manage.py test_settlement_flow

# Test specific month
python manage.py test_settlement_flow --month 1 --year 2025

# Only create settlements (skip processing)
python manage.py test_settlement_flow --skip-day6
```

### `simulate_day1`
Simulate Day 1 - Create settlement requests.

```bash
python manage.py simulate_day1 [--date YYYY-MM-DD]
```

**Options:**
- `--date`: Date to simulate (must be 1st of a month). Default: 1st of current month

**Example:**
```bash
# Use current month
python manage.py simulate_day1

# Use specific date
python manage.py simulate_day1 --date 2025-01-01
```

### `simulate_day6`
Simulate Day 6 - Process settlement payouts.

```bash
python manage.py simulate_day6 [--date YYYY-MM-DD]
```

**Options:**
- `--date`: Date to simulate (must be 6th of a month). Default: 6th of current month

**Example:**
```bash
# Use current month
python manage.py simulate_day6

# Use specific date
python manage.py simulate_day6 --date 2025-01-06
```

## Quick Test Example

```bash
# 1. Create orders via platform (adds money to designer wallets)

# 2. Simulate Day 1
python manage.py simulate_day1 --date 2025-01-01

# 3. Opt-in via platform or manually

# 4. Simulate Day 6
python manage.py simulate_day6 --date 2025-01-06

# 5. Check admin panel and download sheet
```

## Troubleshooting

### No settlements created
- **Check:** Designers have wallet balance > 0
- **Check:** Designers have verified Razorpay onboarding status
- **Check:** Designers are active users

### No settlements to process on Day 6
- **Check:** Settlements exist with status `opted_in`
- **Check:** Settlements haven't been processed already (`settlement_date` is null)

### Time simulation not working
- **Check:** `freezegun` is installed: `pip install freezegun==1.2.2`
- **Check:** You're using the management commands (not calling tasks directly)

## Notes

- Time simulation only affects the settlement tasks, not the entire Django application
- Real orders created through the platform will have real timestamps
- Settlement periods are calculated based on the simulated date
- You can run these commands multiple times (they handle existing settlements)

