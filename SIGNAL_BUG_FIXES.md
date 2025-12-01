# Signal Bug Fixes - Product.save() Issues

## ⚠️ CRITICAL: DO NOT USE `product.save()` FOR STATUS UPDATES

## Problem
The `Product` model has a `pre_save` signal (`generate_design_numbers_signal`) that can hang when querying the Studio model. This causes requests to timeout when `product.save()` is called.

## Solution
**ALWAYS** use `Product.objects.filter(pk=product.pk).update(...)` instead of `product.save()` for status/metadata updates to bypass Django signals and perform direct SQL UPDATE queries.

## Fixed Locations

### 1. API/CoreAdmin/models.py

#### approve_design() method (Line ~382)
- **Before**: `product.save(update_fields=['status', 'rejection_reason'])`
- **After**: `Product.objects.filter(pk=self.product_id).update(status='active', rejection_reason=None)`
- **Status**: ✅ Fixed

#### reject_design() method (Line ~445)
- **Before**: `product.save()`
- **After**: `Product.objects.filter(pk=self.product_id).update(status='inactive', rejection_reason=rejection_reason)`
- **Status**: ✅ Fixed

#### disable_design() method (Line ~507)
- **Before**: `product.save()`
- **After**: `Product.objects.filter(pk=self.product_id).update(status='inactive')`
- **Status**: ✅ Fixed

#### disable_design() in CopyrightReport (Line ~773)
- **Before**: `product.save()`
- **After**: `Product.objects.filter(pk=product.pk).update(status='inactive')`
- **Status**: ✅ Fixed

### 2. API/CoreAdmin/views.py

#### design_action() - flag action (Line ~3456)
- **Before**: `design.save(update_fields=['product_metadata'])`
- **After**: `Product.objects.filter(pk=design.pk).update(product_metadata=design.product_metadata)`
- **Status**: ✅ Fixed

#### design_action() - resolve_flag action (Line ~3470)
- **Before**: `design.save(update_fields=['product_metadata'])`
- **After**: `Product.objects.filter(pk=design.pk).update(product_metadata=design.product_metadata)`
- **Status**: ✅ Fixed

## Why This Works

1. **`.update()` bypasses signals**: Django's `.update()` method performs a direct SQL UPDATE query without triggering `pre_save` or `post_save` signals.

2. **Faster performance**: Direct SQL UPDATE is faster than loading the object, modifying it, and saving it.

3. **No signal overhead**: Avoids the expensive Studio query in the `generate_design_numbers_signal` handler.

## When to Use `.update()` vs `.save()`

### Use `.update()` when:
- ✅ Only updating simple fields (status, metadata, etc.)
- ✅ Don't need signal handlers to run
- ✅ Performance is critical
- ✅ Updating Product status/metadata

### Use `.save()` when:
- ✅ Need signal handlers to run (e.g., generating design numbers on creation)
- ✅ Updating complex relationships
- ✅ Need model-level validation
- ✅ Creating new instances

## Prevention Guidelines - MANDATORY

1. **NEVER use `product.save()` for status/metadata updates** - ALWAYS use `.update()`
2. **Code Review Checklist** - Before merging any PR that updates Product:
   - ✅ Search for `product.save()` or `Product.objects.*.save()`
   - ✅ Verify all Product status updates use `.update()`
   - ✅ Check for any new Product.save() calls
3. **Pre-commit Hook** - Consider adding a git hook to warn about Product.save() usage
4. **Test timeout scenarios** - Ensure all Product status updates complete quickly (< 1 second)
5. **Monitor logs** - Watch for slow Product.save() operations in production

## Code Pattern to Follow

### ❌ WRONG - Will cause timeout:
```python
product.status = 'active'
product.save()  # ❌ Triggers pre_save signal - can hang!
```

### ✅ CORRECT - Fast and reliable:
```python
Product.objects.filter(pk=product.pk).update(status='active')  # ✅ Bypasses signals
```

## Additional Fixes Applied

### Backend Response Format Fix
- **Issue**: Backend was returning `detail` field in success responses
- **Problem**: Frontend's `transformResponse` treats `detail` as an error
- **Fix**: Removed `detail` from success responses in `design_action` endpoint
- **Location**: `API/CoreAdmin/views.py` line ~3575

## Testing

All fixed methods have been tested and verified to:
- ✅ Complete quickly (< 1 second)
- ✅ Update database correctly
- ✅ Not trigger signal handlers
- ✅ Not cause request timeouts

## Related Files

- `API/Catalog/models.py` - Contains the problematic `pre_save` signal (line 336)
- `API/common/signals.py` - Contains `post_save` signal for Product (line 279)

