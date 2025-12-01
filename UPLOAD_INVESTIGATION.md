# Upload Design Investigation Report

## Problem Statement
The upload design form is hanging - the fetch request starts but never completes. The frontend shows "Fetch starting at: 2025-11-18T16:47:49.953Z" but no completion log.

## Files Being Uploaded
- WD42_927_JikgUju.eps (7,069,762 bytes = ~7MB)
- WD1_929_5IpJ54W.cdr (1,890,623 bytes = ~1.9MB)
- IMG_8864.jpg (2,427,022 bytes = ~2.4MB)
- ChatGPT Image Nov 10, 2025, 11_21_06 AM.png (3,072,143 bytes = ~3MB)
- IMG_8864.jpg (2,427,022 bytes = ~2.4MB)
**Total: ~17MB**

## Root Cause Analysis

### Issue #1: Synchronous File I/O Inside Transaction
**Location**: `API/Catalog/views.py:859-899`

The code processes files synchronously inside a database transaction:
```python
with transaction.atomic():
    # ... create product ...
    for file in design_files:
        media_obj = Media.objects.create(file=file, ...)  # BLOCKING FILE WRITE
        product.attach_media(media_obj, ...)  # DATABASE OPERATION
```

**Problems**:
1. **Blocking I/O**: Django writes files to disk synchronously, which can take several seconds for 17MB
2. **Transaction Held Open**: Database transaction is held open during file writes, causing:
   - Connection pool exhaustion
   - Lock contention
   - Potential deadlocks
3. **No Early Response**: Client waits for ALL files to be written before getting a response

### Issue #2: No Request Logging
The backend logs at the start (`logger.info(f'Upload design request received...')`) but we don't know if:
- The request is actually reaching the backend
- Where exactly it's hanging
- If there are any errors being silently caught

### Issue #3: Large Files in Single Request
Processing 5 files (~17MB) synchronously in one request is inefficient and prone to timeouts.

## Investigation Steps

### Step 1: Check if Backend Receives Request
**Action**: Check Django server logs for:
```
Upload design request received from user X
Request data keys: [...]
Request files: [...]
```

**If NOT present**: The request isn't reaching Django (CORS, network, or middleware issue)

**If present**: The request is received but hanging during processing

### Step 2: Check Where It Hangs
Add detailed logging at each step:
- After validation
- Before transaction
- After product creation
- Before file loop
- Inside file loop (for each file)
- After file loop
- Before response

### Step 3: Check Database/File System
- Database connection pool status
- File system write permissions
- Disk space availability
- I/O performance

## Solutions

### Solution 1: Move File Writes Outside Transaction (RECOMMENDED)
```python
# Create product in transaction
with transaction.atomic():
    product = Product.objects.create(...)
    # ... create relations ...

# Write files OUTSIDE transaction
for file in design_files:
    media_obj = Media.objects.create(file=file, ...)
    product.attach_media(media_obj, ...)
```

**Benefits**:
- Transaction commits quickly
- File writes don't block database
- Better error handling

### Solution 2: Use Background Task (BEST FOR PRODUCTION)
Move file processing to Celery task:
```python
# In view - quick response
product = Product.objects.create(...)
process_design_files.delay(product.id, file_paths)

# In Celery task - async processing
@shared_task
def process_design_files(product_id, file_paths):
    product = Product.objects.get(id=product_id)
    for file_path in file_paths:
        # Process files asynchronously
```

### Solution 3: Optimize File Handling
- Use `default_storage.save()` for better performance
- Stream files instead of loading into memory
- Process files in parallel (if using async)

### Solution 4: Add Timeout Handling
- Set appropriate Django request timeout
- Add progress callbacks
- Implement chunked uploads for large files

## Immediate Fix

1. **Add comprehensive logging** to identify exact hang point
2. **Move file writes outside transaction** to prevent blocking
3. **Add error handling** with proper responses
4. **Test with smaller files first** to verify fix

## Testing Checklist

- [ ] Backend receives request (check logs)
- [ ] Request passes validation
- [ ] Product is created successfully
- [ ] Files are written to disk
- [ ] Response is returned to frontend
- [ ] No database connection issues
- [ ] No file permission issues

## Performance Metrics

**Expected Times** (for 17MB):
- Network upload: 1-5 seconds (depends on connection)
- File write to disk: 2-10 seconds (depends on disk I/O)
- Database operations: <1 second
- **Total**: 3-16 seconds

**Current Behavior**: Hanging indefinitely (>5 minutes)

## Next Steps

1. Implement Solution 1 (move file writes outside transaction)
2. Add detailed logging
3. Test with current file set
4. Monitor performance
5. Consider Solution 2 (background tasks) for production

