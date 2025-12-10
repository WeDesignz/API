# Instagram Integration Setup Guide

## Overview

This integration allows you to post designs to Instagram from the admin panel. It includes:
- OAuth authentication through Facebook (Instagram uses Facebook's OAuth system)
- Automatic posting when designs are selected
- Support for both regular posts and stories
- Failed post queue with automatic retry
- Admin panel management

## Prerequisites

1. **Instagram Business or Creator Account** - Your Instagram account must be a Business or Creator account (not a personal account)
2. **Facebook Page** - Your Instagram Business account must be linked to a Facebook Page
3. **Facebook App** - You need a Facebook App with Instagram Graph API product added

## Setup Steps

### 1. Run Database Migrations

```bash
python manage.py makemigrations common
python manage.py migrate
```

### 2. Configure Environment Variables

Your `.env` file should already have these (verify they're correct):

```bash
# Instagram/Facebook App Credentials (from Facebook Developer Portal)
INSTAGRAM_APP_ID=1893744058116614
INSTAGRAM_APP_SECRET=cb7e5ca34795b85078d13f25b7cd2c48

# Redirect URI (must match Facebook app settings)
INSTAGRAM_REDIRECT_URI=https://wedesignz.com/api/common/instagram/callback

# Optional: Pre-existing access token (OAuth will generate a new one)
INSTAGRAM_ACCESS_TOKEN=your_token_here
```

### 3. Configure Facebook App Settings

1. Go to: https://developers.facebook.com/apps/1893744058116614/
2. Navigate to: **Settings → Basic**
3. Add to **Valid OAuth Redirect URIs**:
   ```
   https://wedesignz.com/api/common/instagram/callback
   ```
   For local development:
   ```
   http://localhost:8000/api/common/instagram/callback
   ```
4. Save changes

### 4. Add Instagram Graph API Product

1. In your app dashboard, click **"Add Product"**
2. Find **"Instagram Graph API"** and click **"Set Up"**
3. Follow the setup wizard

### 5. Request Instagram Permissions

1. Go to: **App Review → Permissions and Features**
2. Request these permissions:
   - `instagram_basic` - Basic Instagram account info
   - `instagram_content_publish` - Post to Instagram
   - `pages_show_list` - List Facebook pages (needed for Instagram Business accounts)
   - `pages_read_engagement` - Read page engagement

**Note:** In Development mode, you can test with your own account without App Review. For production, you'll need App Review approval.

### 6. Authorize Instagram

1. Restart your Django server to load new environment variables
2. Go to Admin Web App: `/settings?tab=instagram`
3. Click **"Connect Instagram"**
4. You'll be redirected to Facebook to authorize
5. After authorization, you'll be redirected back and the token will be saved automatically

## How It Works

### Posting Flow

1. Admin selects products in `/instagram-posts` page
2. Chooses image type (Mockup, JPG, or PNG) for each product
3. Adds captions for each post
4. Selects post type (Post or Story)
5. Clicks "Post to Instagram"
6. Posts are queued in Celery for async processing
7. Each post is processed and published to Instagram
8. Status is tracked in the database

### OAuth Flow

1. Admin clicks "Connect Instagram" in Settings
2. Redirects to Facebook OAuth page
3. User authorizes the app
4. Callback exchanges code for:
   - Short-lived access token
   - Long-lived access token (60 days)
   - Instagram Business Account ID
   - Instagram username
5. Tokens saved to `InstagramIntegration` model

### Failed Posts & Retry

- All failed posts are tracked in the database
- You can retry failed posts from Django Admin
- Automatic retry is built into Celery tasks

## Testing

### Test OAuth Flow

1. Visit: `https://wedesignz.com/api/common/instagram/authorize/`
2. You should be redirected to Facebook
3. After authorization, you'll see a success page

### Check Status

Visit: `https://wedesignz.com/api/common/instagram/status/`

You should see:
```json
{
  "is_enabled": true,
  "is_configured": true,
  "is_token_valid": true,
  "username": "your_instagram_username",
  ...
}
```

### Test Posting

1. Go to Admin Web App → Instagram Posts
2. Select products
3. Choose image types and add captions
4. Click "Post to Instagram"
5. Check Django Admin → Instagram Posts to see status

## Troubleshooting

### "Facebook/Instagram App ID not configured"

- Verify `INSTAGRAM_APP_ID` is in `.env`
- Restart Django server after adding to `.env`
- Check `API/API/settings.py` has the config loaded

### "Instagram access token expired"

- Tokens expire after 60 days
- Click "Re-authorize" in Settings to refresh

### "No Instagram Business Account found"

- Ensure your Instagram account is a Business or Creator account
- Link your Instagram account to a Facebook Page
- The Facebook Page must be connected to your Facebook App

### OAuth Redirect URI Mismatch

- Ensure the redirect URI in `.env` matches exactly what's in Facebook App settings
- Check for trailing slashes (should be consistent)
- For production, use HTTPS

### Permission Errors

- Ensure all required permissions are requested in App Review
- In Development mode, only your account can be used
- For production, submit for App Review

## Admin Panel

### Django Admin

- View Instagram integration status: `/admin/common/instagramintegration/`
- View Instagram posts: `/admin/common/instagrampost/`
- Retry failed posts from the admin interface

### Admin Web App

- Configure Instagram: `/settings?tab=instagram`
- Create posts: `/instagram-posts`

## API Endpoints

- `GET /api/common/instagram/status/` - Check integration status
- `GET /api/common/instagram/authorize/` - Initiate OAuth flow
- `GET /api/common/instagram/callback/` - OAuth callback (handled automatically)
- `POST /api/common/instagram/post/` - Create Instagram posts (bulk support)
- `GET /api/common/instagram/posts/` - List Instagram posts with pagination

## Notes

- Instagram uses Facebook's OAuth system, so authorization goes through Facebook
- Long-lived tokens are valid for 60 days
- The system automatically refreshes tokens when possible
- Instagram Business accounts are required (not personal accounts)
- Stories and regular posts use the same API but different endpoints

