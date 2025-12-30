# Media Files Migration Guide

This guide explains how to migrate existing files to the new user-centric directory structure.

## Overview

The new file structure organizes all user data by user ID:
```
/media/
   /<user-id>/
       /invoices/          # User's invoices
       /pdfs/              # User's PDF downloads
       /designs/           # User's design files
           /<product-id>/
               WD01.jpg
               WD01.png
       /uploads/           # Bulk ZIP uploads (temporary)
       /temp/              # Temporary single file uploads
```

## Migration Commands

### 1. Migrate Design Files Only

This command migrates design files (Media objects related to Products) from the old structure to the new user/product structure.

```bash
# Dry run - see what would be migrated without making changes
python manage.py migrate_media_files --dry-run

# Perform the actual migration
python manage.py migrate_media_files

# Verbose output - see details for each file
python manage.py migrate_media_files --verbose

# Skip files already in correct location
python manage.py migrate_media_files --skip-existing

# Process in larger batches (default is 50)
python manage.py migrate_media_files --batch-size 100
```

### 2. Migrate All User Files (Complete Migration)

This command migrates all file types (invoices, PDFs, designs, uploads, temp files) to the new user-centric structure.

```bash
# Dry run - preview all migrations
python manage.py migrate_user_files --dry-run

# Migrate all file types
python manage.py migrate_user_files

# Migrate specific file type only
python manage.py migrate_user_files --type invoices
python manage.py migrate_user_files --type pdfs
python manage.py migrate_user_files --type designs
python manage.py migrate_user_files --type uploads
python manage.py migrate_user_files --type temp

# Verbose output
python manage.py migrate_user_files --verbose

# Skip files already in correct location
python manage.py migrate_user_files --skip-existing
```

## Migration Types

### Invoices
- **From**: `invoices/INV-2024-001.pdf`
- **To**: `{user_id}/invoices/INV-2024-001.pdf`
- **Command**: `python manage.py migrate_user_files --type invoices`

### PDF Downloads
- **From**: `pdfs/pdf_download_123.pdf`
- **To**: `{user_id}/pdfs/pdf_download_123.pdf`
- **Command**: `python manage.py migrate_user_files --type pdfs`

### Design Files
- **From**: `media/WD01.jpg` or `{user_id}/{product_id}/WD01.jpg`
- **To**: `{user_id}/designs/{product_id}/WD01.jpg`
- **Command**: `python manage.py migrate_user_files --type designs`

### Bulk Uploads
- **From**: `design_uploads/{user_id}/20240101_designs.zip`
- **To**: `{user_id}/uploads/20240101_designs.zip`
- **Command**: `python manage.py migrate_user_files --type uploads`

### Temp Uploads
- **From**: `temp_uploads/{user_id}/20240101_file.jpg`
- **To**: `{user_id}/temp/20240101_file.jpg`
- **Command**: `python manage.py migrate_user_files --type temp`

## Command Options

### migrate_media_files
- `--dry-run`: Preview what would be migrated without making changes
- `--batch-size N`: Process N files at a time (default: 50)
- `--skip-existing`: Skip files that are already in the correct location
- `--verbose`: Show detailed information for each file being processed

### migrate_user_files
- `--dry-run`: Preview what would be migrated without making changes
- `--type TYPE`: Migrate specific file type (invoices, pdfs, designs, uploads, temp, all)
- `--batch-size N`: Process N files at a time (default: 50)
- `--skip-existing`: Skip files that are already in the correct location
- `--verbose`: Show detailed information for each file being processed

## What the Migrations Do

### Design Files Migration (migrate_media_files)
1. **Finds all Media objects** related to Products (via Product:Media relation)
2. **Determines the correct path** based on:
   - User ID from `product.created_by.id`
   - Product ID from the related Product
   - Original filename
3. **Moves files** from old location to new location (`{user_id}/designs/{product_id}/`)
4. **Updates the database** to point to the new file location
5. **Deletes old files** (only if they were in the `media/` directory)

### Complete Migration (migrate_user_files)
1. **Invoices**: Moves from `invoices/` to `{user_id}/invoices/` and updates Invoice model
2. **PDFs**: Moves from `pdfs/` to `{user_id}/pdfs/` and updates PDFDownload model
3. **Designs**: Moves from `media/` or `{user_id}/{product_id}/` to `{user_id}/designs/{product_id}/` and updates Media model
4. **Bulk Uploads**: Moves from `design_uploads/{user_id}/` to `{user_id}/uploads/`
5. **Temp Uploads**: Moves from `temp_uploads/{user_id}/` to `{user_id}/temp/`

## Migration Statistics

Both commands provide detailed statistics:
- Total files found
- Successfully migrated
- Already in correct location
- Skipped (if using --skip-existing)
- Missing files
- Errors encountered

## Error Handling

The migration scripts handle various edge cases:
- Files that don't exist in storage
- Media objects without related Products
- Products without a `created_by` user
- PDF downloads without associated users
- Files already in the correct location
- Destination file conflicts (automatically handles)

## Safety Features

1. **Dry Run Mode**: Test the migration without making changes
2. **Batch Processing**: Process files in batches to avoid memory issues
3. **Error Logging**: Detailed error messages for troubleshooting
4. **Backup**: Files are moved (not copied), but old directories remain until manually cleaned
5. **Idempotent**: Safe to run multiple times (skips already-migrated files)

## Example Output

```
================================================================================
User Files Migration Script
================================================================================

--- Migrating Invoices ---

Found 150 invoices to process...
  Invoice 1: invoices/INV-2024-001.pdf -> 123/invoices/INV-2024-001.pdf
    ✓ Migrated successfully
  ...

--- Migrating PDF Downloads ---

Found 75 PDF downloads to process...
  PDF 1: pdfs/pdf_download_123.pdf -> 456/pdfs/pdf_download_123.pdf
    ✓ Migrated successfully
  ...

================================================================================
Migration Summary
================================================================================

INVOICES:
  Total: 150
  ✓ Migrated: 145
  ⊘ Skipped: 5
  ✗ Errors: 0

PDFS:
  Total: 75
  ✓ Migrated: 70
  ⊘ Skipped: 5
  ✗ Errors: 0

Migration completed!
```

## Before Running Migration

1. **Backup your database** (recommended)
2. **Ensure sufficient disk space** (files are moved, not copied)
3. **Test with --dry-run first** to see what will happen
4. **Run during low-traffic period** if possible
5. **Stop file uploads** temporarily to avoid conflicts

## After Migration

1. **Verify file access** - Check that files are accessible via the application
2. **Check file counts** - Ensure all expected files were migrated
3. **Review error logs** - Address any errors that occurred
4. **Clean up old directories** - Old directories can be removed after verification:
   - `media/invoices/` (if empty)
   - `media/pdfs/` (if empty)
   - `media/design_uploads/` (if empty)
   - `media/temp_uploads/` (if empty)
   - `media/media/` (legacy design files, if empty)

## Troubleshooting

**Files not migrating:**
- Check if Media objects have related Products
- Verify Products have a `created_by` user
- Check PDF downloads have associated users
- Check file permissions on storage

**Errors during migration:**
- Review verbose output with `--verbose` flag
- Check Django logs for detailed error messages
- Ensure storage backend has write permissions

**Performance issues:**
- Reduce batch size with `--batch-size 25`
- Run during off-peak hours
- Consider running in smaller chunks by file type

## Recommended Migration Order

1. **First**: Run `migrate_user_files --dry-run --type all` to preview
2. **Second**: Run `migrate_user_files --type designs` (most critical)
3. **Third**: Run `migrate_user_files --type invoices`
4. **Fourth**: Run `migrate_user_files --type pdfs`
5. **Fifth**: Run `migrate_user_files --type uploads`
6. **Last**: Run `migrate_user_files --type temp`

Or run all at once:
```bash
python manage.py migrate_user_files
```

## Notes

- Only Media objects related to Products are migrated for designs
- Other Media objects (profile photos, etc.) remain in `media/` directory
- The migration is safe to run multiple times
- Files are moved (not copied) to save disk space
- Old directories remain and can be manually cleaned up after verification
