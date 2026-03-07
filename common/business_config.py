"""
Business configuration utilities for accessing system configuration.
This module provides easy access to business-related configuration values.
Values are read from SystemConfig model (set in AdminWebApp), with fallback to environment variables.
"""

from decimal import Decimal
from django.conf import settings


class BusinessConfig:
    """Business configuration helper class."""
    
    @staticmethod
    def _get_system_config():
        """Get SystemConfig instance, with fallback to None if not available."""
        try:
            from CoreAdmin.models import SystemConfig
            return SystemConfig.get_config()
        except Exception:
            # Fallback if SystemConfig is not available (e.g., during migrations)
            return None
    
    @staticmethod
    def get_commission_rate():
        """Get the platform commission rate as a percentage.
        Reads from SystemConfig, falls back to environment variable if not set.
        """
        config = BusinessConfig._get_system_config()
        if config and config.commission_rate is not None:
            return float(config.commission_rate)
        # Fallback to environment variable
        return getattr(settings, 'COMMISSION_RATE', 10.0)
    
    @staticmethod
    def get_gst_percentage():
        """Get the GST percentage.
        Reads from SystemConfig, falls back to environment variable if not set.
        """
        config = BusinessConfig._get_system_config()
        if config and config.gst_percentage is not None:
            return float(config.gst_percentage)
        # Fallback to environment variable
        return getattr(settings, 'GST_PERCENTAGE', 18.0)
    
    @staticmethod
    def get_custom_order_time_slot_hours():
        """Get the custom order time slot in hours.
        Reads from SystemConfig, falls back to environment variable if not set.
        """
        config = BusinessConfig._get_system_config()
        if config and config.custom_order_time_slot_hours is not None:
            return int(config.custom_order_time_slot_hours)
        # Fallback to environment variable
        return getattr(settings, 'CUSTOM_ORDER_TIME_SLOT_HOURS', 1)
    
    @staticmethod
    def get_minimum_required_designs_onboard():
        """Get the minimum required designs for onboarding.
        Reads from SystemConfig, falls back to environment variable if not set.
        """
        config = BusinessConfig._get_system_config()
        if config and config.minimum_required_designs is not None:
            return int(config.minimum_required_designs)
        # Fallback to environment variable
        return getattr(settings, 'MINIMUM_REQUIRED_DESIGNS_ONBOARD', 50)
    
    @staticmethod
    def get_free_mock_pdf_downloads_no_plan_per_month():
        """Get free mock PDF downloads per month for users without a plan.
        Reads from SystemConfig. Use a high value (e.g. 999) for unlimited.
        """
        config = BusinessConfig._get_system_config()
        if config and hasattr(config, 'free_mock_pdf_downloads_no_plan_per_month') and config.free_mock_pdf_downloads_no_plan_per_month is not None:
            return int(config.free_mock_pdf_downloads_no_plan_per_month)
        return getattr(settings, 'FREE_MOCK_PDF_DOWNLOADS_NO_PLAN_PER_MONTH', 999)

    @staticmethod
    def get_free_designs_per_account_one_time():
        """Get number of free design downloads per account (one-time only). Default 10."""
        config = BusinessConfig._get_system_config()
        if config and hasattr(config, 'free_designs_per_account_one_time') and config.free_designs_per_account_one_time is not None:
            return int(config.free_designs_per_account_one_time)
        return getattr(settings, 'FREE_DESIGNS_PER_ACCOUNT_ONE_TIME', 10)

    @staticmethod
    def get_free_custom_orders_per_account():
        """Get number of free custom orders per account. Default 2."""
        config = BusinessConfig._get_system_config()
        if config and hasattr(config, 'free_custom_orders_per_account') and config.free_custom_orders_per_account is not None:
            return int(config.free_custom_orders_per_account)
        return getattr(settings, 'FREE_CUSTOM_ORDERS_PER_ACCOUNT', 2)

    @staticmethod
    def get_paid_pdf_designs_options():
        """Get PDF download design count options (e.g. [20, 50, 100]).
        First value is used for free PDFs. Only 20, 50, 100 allowed (values > 100 filtered out).
        Reads from SystemConfig, falls back to .env.
        """
        config = BusinessConfig._get_system_config()
        if config and hasattr(config, 'paid_pdf_designs_options') and config.paid_pdf_designs_options:
            opts = config.paid_pdf_designs_options
            if isinstance(opts, list) and len(opts) > 0:
                filtered = [int(x) for x in opts if str(x).strip() and int(x) <= 100]
                return filtered if filtered else [20, 50, 100]
        return getattr(settings, 'PAID_PDF_DESIGNS_OPTIONS', [20, 50, 100])
    
    @staticmethod
    def calculate_commission_amount(amount):
        """Calculate commission amount from a given amount."""
        # Convert to Decimal to avoid mixing Decimal and float
        commission_rate = Decimal(str(BusinessConfig.get_commission_rate()))
        return amount * (commission_rate / Decimal('100'))
    
    @staticmethod
    def calculate_gst_amount(amount):
        """Calculate GST amount from a given amount."""
        # Convert to Decimal to avoid mixing Decimal and float
        gst_percentage = Decimal(str(BusinessConfig.get_gst_percentage()))
        return amount * (gst_percentage / Decimal('100'))
    
    @staticmethod
    def get_design_price():
        """Get the global design price per design.
        Reads from SystemConfig, falls back to environment variable if not set.
        """
        config = BusinessConfig._get_system_config()
        if config and config.design_price is not None:
            return Decimal(str(config.design_price))
        # Fallback to environment variable
        return Decimal(str(getattr(settings, 'DESIGN_PRICE', 50.00)))
    
    @staticmethod
    def get_custom_order_price():
        """Get the default price for custom orders.
        Reads from SystemConfig, falls back to environment variable if not set.
        """
        config = BusinessConfig._get_system_config()
        if config and config.custom_order_price is not None:
            return Decimal(str(config.custom_order_price))
        # Fallback to environment variable
        return Decimal(str(getattr(settings, 'CUSTOM_ORDER_PRICE', 200.00)))
    
    @staticmethod
    def get_delivery_promise_text():
        """Get formatted delivery promise text."""
        hours = BusinessConfig.get_custom_order_time_slot_hours()
        return f"{hours} hour{'s' if hours != 1 else ''}"
