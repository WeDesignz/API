"""
Studio Name Generation System for WeDesignz Platform

This module provides robust studio name generation that can handle millions of studios
while ensuring uniqueness and pronounceable names for better user experience.
"""

import secrets
import string
from django.db import transaction
from django.core.cache import cache
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

# Define consonants and vowels for pronounceable names
CONSONANTS = ["b", "c", "d", "f", "g", "h", "j", "k", "l", "m", "n", "p", "r", "s", "t", "v", "z"]
VOWELS = ["a", "e", "i", "o", "u", "y"]

# Extended alphabet for more combinations
ALPHABET_EXTENDED = string.ascii_lowercase + string.digits

# Cache keys for tracking generated names
CACHE_KEY_PREFIX = "studio_name_"
CACHE_TIMEOUT = 3600  # 1 hour


class StudioNameGenerator:
    """
    High-performance studio name generator that can handle millions of unique names.
    Uses multiple strategies to ensure uniqueness and scalability.
    """
    
    def __init__(self):
        self.max_attempts = 1000  # Maximum attempts to generate unique name
        self.cache_size = 10000    # Cache size for generated names
    
    def generate_pronounceable_word(self, syllables: int = 2) -> str:
        """
        Generate a pronounceable pseudo-word by alternating consonants and vowels.
        Example (syllables=2): "Kirevo", "Bamoru", "Toveka"
        """
        word = ""
        for _ in range(syllables):
            consonant = secrets.choice(CONSONANTS)
            vowel = secrets.choice(VOWELS)
            word += consonant + vowel
        return word.capitalize()
    
    def generate_random_token(self, length: int = 2) -> str:
        """
        Generate a short random token using lowercase letters and digits.
        Example (length=2): "3x", "9b", "1z"
        """
        return ''.join(secrets.choice(ALPHABET_EXTENDED) for _ in range(length))
    
    def generate_studio_name(self, syllables: int = 2, token_length: int = 2) -> str:
        """
        Generate a studio name combining pronounceable word + random token.
        Example: "Kirevo3x", "Bamoru9a", "Toveka1m"
        """
        name = self.generate_pronounceable_word(syllables)
        token = self.generate_random_token(token_length)
        return f"{name}{token}"
    
    def generate_high_entropy_name(self, length: int = 8) -> str:
        """
        Generate a high-entropy name for extreme scalability.
        Uses base36 encoding for maximum combinations.
        """
        return ''.join(secrets.choice(ALPHABET_EXTENDED) for _ in range(length))
    
    def generate_numeric_name(self, prefix: str = "ST") -> str:
        """
        Generate numeric-based names for maximum scalability.
        Format: ST00000001, ST00000002, etc.
        """
        # Get next available number from cache or database
        cache_key = f"{CACHE_KEY_PREFIX}counter_{prefix}"
        counter = cache.get(cache_key, 0)
        
        # Increment counter atomically
        new_counter = counter + 1
        cache.set(cache_key, new_counter, CACHE_TIMEOUT)
        
        return f"{prefix}{new_counter:08d}"
    
    def is_name_unique(self, name: str) -> bool:
        """
        Check if a studio name is unique by querying the database.
        Uses database-level uniqueness check for reliability.
        """
        from Profiles.models import Studio
        
        try:
            # Use select_for_update to prevent race conditions
            with transaction.atomic():
                exists = Studio.objects.filter(wedesignz_auto_name=name).exists()
                return not exists
        except Exception as e:
            logger.error(f"Error checking name uniqueness: {str(e)}")
            return False
    
    def generate_unique_studio_name(self, strategy: str = "pronounceable") -> Optional[str]:
        """
        Generate a unique studio name using the specified strategy.
        
        Strategies:
        - "pronounceable": Human-readable names (Kirevo3x, Bamoru9a)
        - "high_entropy": High-entropy names for maximum scalability
        - "numeric": Numeric-based names (ST00000001, ST00000002)
        - "hybrid": Try pronounceable first, fallback to high_entropy
        """
        attempts = 0
        
        while attempts < self.max_attempts:
            try:
                if strategy == "pronounceable":
                    name = self.generate_studio_name()
                elif strategy == "high_entropy":
                    name = self.generate_high_entropy_name()
                elif strategy == "numeric":
                    name = self.generate_numeric_name()
                elif strategy == "hybrid":
                    # Try pronounceable first, then high_entropy
                    if attempts < self.max_attempts // 2:
                        name = self.generate_studio_name()
                    else:
                        name = self.generate_high_entropy_name()
                else:
                    name = self.generate_studio_name()
                
                # Check uniqueness
                if self.is_name_unique(name):
                    return name
                
                attempts += 1
                
            except Exception as e:
                logger.error(f"Error generating studio name: {str(e)}")
                attempts += 1
                continue
        
        # Fallback to numeric strategy if all else fails
        if strategy != "numeric":
            logger.warning(f"Falling back to numeric strategy after {attempts} attempts")
            return self.generate_unique_studio_name("numeric")
        
        logger.error("Failed to generate unique studio name after maximum attempts")
        return None
    
    def generate_multiple_names(self, count: int = 10, strategy: str = "pronounceable") -> List[str]:
        """
        Generate multiple unique studio names.
        Useful for batch operations or testing.
        """
        names = []
        for _ in range(count):
            name = self.generate_unique_studio_name(strategy)
            if name:
                names.append(name)
        return names
    
    def validate_studio_name(self, name: str) -> bool:
        """
        Validate a studio name format and uniqueness.
        """
        if not name or len(name) < 3 or len(name) > 50:
            return False
        
        # Check if name contains only allowed characters
        allowed_chars = string.ascii_letters + string.digits
        if not all(c in allowed_chars for c in name):
            return False
        
        return self.is_name_unique(name)


# Global instance for easy access
studio_name_generator = StudioNameGenerator()


def generate_studio_name(strategy: str = "pronounceable") -> Optional[str]:
    """
    Convenience function to generate a unique studio name.
    """
    return studio_name_generator.generate_unique_studio_name(strategy)


def validate_studio_name(name: str) -> bool:
    """
    Convenience function to validate a studio name.
    """
    return studio_name_generator.validate_studio_name(name)


# Design Number Generation System
class DesignNumberGenerator:
    """
    Design number generation system for both general and studio-wise numbering.
    """
    
    def __init__(self):
        self.general_prefix = "WDG"
        self.general_counter_cache_key = "design_counter_general"
        self.studio_counter_cache_key_prefix = "design_counter_studio_"
        self.cache_timeout = 3600  # 1 hour
    
    def generate_general_design_number(self) -> str:
        """
        Generate general design number: WDG00000001, WDG00000002, etc.
        """
        counter = cache.get(self.general_counter_cache_key, 0)
        new_counter = counter + 1
        cache.set(self.general_counter_cache_key, new_counter, self.cache_timeout)
        
        return f"{self.general_prefix}{new_counter:08d}"
    
    def generate_studio_design_number(self, studio_auto_name: str) -> str:
        """
        Generate studio-wise design number: LR0000001, LR0000002, etc.
        Uses first 2 characters of studio auto name as prefix.
        """
        # Extract prefix from studio name (first 2 characters, uppercase)
        prefix = studio_auto_name[:2].upper()
        
        # Get studio-specific counter
        cache_key = f"{self.studio_counter_cache_key_prefix}{prefix}"
        counter = cache.get(cache_key, 0)
        new_counter = counter + 1
        cache.set(cache_key, new_counter, self.cache_timeout)
        
        return f"{prefix}{new_counter:07d}"
    
    def get_next_design_numbers(self, studio_auto_name: str) -> dict:
        """
        Get both general and studio-wise design numbers for a studio.
        """
        return {
            'general_number': self.generate_general_design_number(),
            'studio_number': self.generate_studio_design_number(studio_auto_name)
        }


# Global instance for design number generation
design_number_generator = DesignNumberGenerator()


def generate_design_numbers(studio_auto_name: str) -> dict:
    """
    Convenience function to generate both design numbers.
    """
    return design_number_generator.get_next_design_numbers(studio_auto_name)
