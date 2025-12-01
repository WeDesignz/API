# Pinterest Integration Setup Guide

## Overview

This integration automatically posts approved designs to your Pinterest account. It includes:
- OAuth authentication
- Automatic posting when designs are approved
- Failed post queue with automatic retry
- Admin panel management

## Setup Steps

### 1. Run Database Migrations

```bash
python manage.py makemigrations common
python manage.py migrate
```

### 2. Configure Environment Variables

Add to your `.env` file:

```bash
# Pinterest App Credentials (from Pinterest Developer Portal)
PINTEREST_APP_ID=your_app_id
PINTEREST_APP_SECRET=your_app_secret

# Redirect URI (must match Pinterest app settings)
PINTEREST_REDIRECT_URI=https://wedesignz.com/api/pinterest/callback

# Site Domain (for building image URLs)
SITE_DOMAIN=wedesignz.com
```

### 3. Authorize Pinterest

1. Visit: `https://wedesignz.com/api/pinterest/authorize/`
2. You'll be redirected to Pinterest to authorize the app
3. After authorization, you'll see your access token and a list of boards
4. The access token is automatically saved to the database

### 4. Set Board ID

Option A: Using Management Command (Recommended)
```bash
# First, list your boards
python manage.py pinterest_setup --get-boards

# Then set the board ID
python manage.py pinterest_setup --set-board YOUR_BOARD_ID
```

Option B: Using Admin Panel
1. Go to Django Admin: `/admin/common/pinterestintegration/`
2. Edit the Pinterest Integration record
3. Set the `board_id` field
4. Save

### 5. Check Status

```bash
python manage.py pinterest_setup --status
```

## How It Works

### Design Approval Flow

1. Admin approves a design
2. Design status changes to 'active' ✅
3. A `PinterestPost` record is created (status='pending')
4. Celery task queues Pinterest post (async, non-blocking)
5. If successful: `PinterestPost` status → 'success', pin_id saved
6. If failed: `PinterestPost` status → 'failed', error saved

### Failed Posts & Retry

- All failed posts are tracked in the database
- When Pinterest is reconnected, failed posts are automatically retried
- You can manually retry posts from the admin panel
- Posts can be retried multiple times

### Automatic Retry

When you re-authorize Pinterest (token expires), the system automatically:
1. Saves the new access token
2. Finds all failed `PinterestPost` records
3. Queues them for retry

## Admin Panel

### Pinterest Integration

Location: `/admin/common/pinterestintegration/`

- View integration status
- Enable/disable Pinterest posting
- View last successful post
- View last error (if any)
- Edit board ID

### Pinterest Posts

Location: `/admin/common/pinterestpost/`

- View all post attempts
- Filter by status (pending, success, failed, retrying)
- See error messages for failed posts
- Retry failed posts (click "Retry" button)

## API Endpoints

- `GET /api/pinterest/authorize/` - Initiate OAuth flow
- `GET /api/pinterest/callback/` - OAuth callback (handled automatically)
- `GET /api/pinterest/status/` - Check integration status (JSON)

## Management Commands

```bash
# Check status
python manage.py pinterest_setup --status

# List all boards
python manage.py pinterest_setup --get-boards

# Set board ID
python manage.py pinterest_setup --set-board BOARD_ID
```

## Troubleshooting

### Token Expired

1. Visit `/api/pinterest/authorize/` to re-authorize
2. Failed posts will automatically retry

### Posts Not Appearing on Pinterest

1. Check status: `python manage.py pinterest_setup --status`
2. Check admin panel for error messages
3. Verify board ID is correct
4. Verify image URLs are publicly accessible

### No Boards Listed

- Ensure you have boards in your Pinterest account
- Check that `boards:read` scope is granted
- Verify access token is valid

## Database Models

### PinterestIntegration

Stores OAuth tokens and configuration (singleton - only one instance).

Fields:
- `access_token` - OAuth access token
- `refresh_token` - OAuth refresh token (if available)
- `board_id` - Pinterest board ID where pins are posted
- `is_enabled` - Enable/disable posting
- `last_successful_post` - Timestamp of last successful post
- `last_error` - Last error message (if any)

### PinterestPost

Tracks each Pinterest post attempt for approved designs.

Fields:
- `product` - Foreign key to Product (design)
- `status` - pending, success, failed, retrying
- `pin_id` - Pinterest pin ID (if successful)
- `pin_url` - URL to the Pinterest pin
- `error_message` - Error message (if failed)
- `retry_count` - Number of retry attempts

## Notes

- Design approval always succeeds, even if Pinterest posting fails
- Pinterest posting happens asynchronously (doesn't block approval)
- Failed posts can be retried manually or automatically
- Image URLs must be publicly accessible for Pinterest to access them
- Pinterest API has rate limits - check Pinterest documentation

