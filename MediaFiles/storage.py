"""
Custom storage class to prevent Django from adding random suffixes to filenames
when files are in unique product folders.
"""
from django.core.files.storage import default_storage
from django.core.files.utils import validate_file_name
import os


class ProductMediaStorage:
    """
    Custom storage wrapper that prevents random suffix generation for product files.
    Since product files are in unique folders ({user_id}/designs/{product_id}/),
    filename collisions shouldn't occur, so we can safely use the exact filename.
    
    This wraps the default storage and overrides get_available_name.
    """
    
    def __init__(self):
        self.storage = default_storage
    
    def get_available_name(self, name, max_length=None):
        """
        Override to prevent Django from adding random suffixes.
        For product files in unique folders, we can use the exact filename.
        """
        # Check if this is a product file (in designs/{product_id}/ folder)
        if '/designs/' in name and name.count('/') >= 3:
            # This is a product file in a unique folder
            # Check if file already exists - if not, use exact name
            if not self.storage.exists(name):
                # Validate the filename but don't add random suffixes
                name = validate_file_name(name, allow_relative_path=True)
                return name
            # If file exists, let default storage handle it (shouldn't happen in unique folders)
        
        # For other files (profile, documents, etc.), use default behavior
        return self.storage.get_available_name(name, max_length)
    
    def get_valid_name(self, name):
        """
        Override to ensure valid filenames without random suffixes for product files.
        """
        # Check if this is a product file
        if '/designs/' in name and name.count('/') >= 3:
            # Just validate, don't modify
            name = validate_file_name(name, allow_relative_path=True)
            return name
        
        # For other files, use default behavior
        return self.storage.get_valid_name(name)
    
    def __getattr__(self, name):
        """Delegate all other attributes to the underlying storage."""
        return getattr(self.storage, name)

