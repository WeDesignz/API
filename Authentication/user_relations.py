"""
User Relations Helper Functions

This module provides helper functions for managing User relations with other models.
All relations follow the one-to-many pattern where User is the "one" side.

User Relations:
- User:PromotionUsage
- User:Address
- User:Subscription
- User:CustomOrderRequest
- User:Media
- User:Email
- User:MobileNumber
- User:OTP
- User:FeedbackReview
- User:Cart
- User:Order
- User:DesignerProfile
- User:StudioMember
- User:RazorpayPayment
- User:Wallet
"""

from django.contrib.auth.models import User
from common.relations import attach_relation, get_related, detach_relation


def get_user_promotion_usages(user):
    """Get all promotion usages for a user"""
    from Coupons.models import CouponUsage
    return get_related(user, 'User:PromotionUsage', CouponUsage)


def attach_user_promotion_usage(user, promotion_usage_obj, meta=None, created_by=None):
    """Attach a promotion usage to a user"""
    from Coupons.models import CouponUsage
    return attach_relation('User:PromotionUsage', user, promotion_usage_obj, meta=meta, created_by=created_by)


def detach_user_promotion_usage(user, promotion_usage_obj):
    """Detach a promotion usage from a user"""
    from Coupons.models import CouponUsage
    return detach_relation('User:PromotionUsage', user, promotion_usage_obj)


def get_user_addresses(user):
    """Get all addresses for a user"""
    from Profiles.models import Addresses
    return get_related(user, 'User:Address', Addresses)


def attach_user_address(user, address_obj, meta=None, created_by=None):
    """Attach an address to a user"""
    from Profiles.models import Addresses
    return attach_relation('User:Address', user, address_obj, meta=meta, created_by=created_by)


def detach_user_address(user, address_obj):
    """Detach an address from a user"""
    from Profiles.models import Addresses
    return detach_relation('User:Address', user, address_obj)


def get_user_subscriptions(user):
    """Get all subscriptions for a user"""
    from Plans.models import Subscription
    return get_related(user, 'User:Subscription', Subscription)


def attach_user_subscription(user, subscription_obj, meta=None, created_by=None):
    """Attach a subscription to a user"""
    from Plans.models import Subscription
    return attach_relation('User:Subscription', user, subscription_obj, meta=meta, created_by=created_by)


def detach_user_subscription(user, subscription_obj):
    """Detach a subscription from a user"""
    from Plans.models import Subscription
    return detach_relation('User:Subscription', user, subscription_obj)


def get_user_custom_order_requests(user):
    """Get all custom order requests for a user"""
    from CustomRequests.models import CustomOrderRequest
    return get_related(user, 'User:CustomOrderRequest', CustomOrderRequest)


def attach_user_custom_order_request(user, custom_order_request_obj, meta=None, created_by=None):
    """Attach a custom order request to a user"""
    from CustomRequests.models import CustomOrderRequest
    return attach_relation('User:CustomOrderRequest', user, custom_order_request_obj, meta=meta, created_by=created_by)


def detach_user_custom_order_request(user, custom_order_request_obj):
    """Detach a custom order request from a user"""
    from CustomRequests.models import CustomOrderRequest
    return detach_relation('User:CustomOrderRequest', user, custom_order_request_obj)


def get_user_media(user):
    """Get all media for a user"""
    from MediaFiles.models import Media
    return get_related(user, 'User:Media', Media)


def attach_user_media(user, media_obj, meta=None, created_by=None):
    """Attach media to a user"""
    from MediaFiles.models import Media
    return attach_relation('User:Media', user, media_obj, meta=meta, created_by=created_by)


def detach_user_media(user, media_obj):
    """Detach media from a user"""
    from MediaFiles.models import Media
    return detach_relation('User:Media', user, media_obj)


def get_user_emails(user):
    """Get all emails for a user"""
    from Authentication.models import Email
    return get_related(user, 'User:Email', Email)


def attach_user_email(user, email_obj, meta=None, created_by=None):
    """Attach an email to a user"""
    from Authentication.models import Email
    return attach_relation('User:Email', user, email_obj, meta=meta, created_by=created_by)


def detach_user_email(user, email_obj):
    """Detach an email from a user"""
    from Authentication.models import Email
    return detach_relation('User:Email', user, email_obj)


def get_user_mobile_numbers(user):
    """Get all mobile numbers for a user"""
    from Authentication.models import MobileNumber
    return get_related(user, 'User:MobileNumber', MobileNumber)


def attach_user_mobile_number(user, mobile_number_obj, meta=None, created_by=None):
    """Attach a mobile number to a user"""
    from Authentication.models import MobileNumber
    return attach_relation('User:MobileNumber', user, mobile_number_obj, meta=meta, created_by=created_by)


def detach_user_mobile_number(user, mobile_number_obj):
    """Detach a mobile number from a user"""
    from Authentication.models import MobileNumber
    return detach_relation('User:MobileNumber', user, mobile_number_obj)


def get_user_otps(user):
    """Get all OTPs for a user"""
    from Authentication.models import OTP
    return get_related(user, 'User:OTP', OTP)


def attach_user_otp(user, otp_obj, meta=None, created_by=None):
    """Attach an OTP to a user"""
    from Authentication.models import OTP
    return attach_relation('User:OTP', user, otp_obj, meta=meta, created_by=created_by)


def detach_user_otp(user, otp_obj):
    """Detach an OTP from a user"""
    from Authentication.models import OTP
    return detach_relation('User:OTP', user, otp_obj)


def get_user_feedback_reviews(user):
    """Get all feedback reviews for a user"""
    from Feedback.models import FeedbackReview
    return get_related(user, 'User:FeedbackReview', FeedbackReview)


def attach_user_feedback_review(user, feedback_review_obj, meta=None, created_by=None):
    """Attach a feedback review to a user"""
    from Feedback.models import FeedbackReview
    return attach_relation('User:FeedbackReview', user, feedback_review_obj, meta=meta, created_by=created_by)


def detach_user_feedback_review(user, feedback_review_obj):
    """Detach a feedback review from a user"""
    from Feedback.models import FeedbackReview
    return detach_relation('User:FeedbackReview', user, feedback_review_obj)


def get_user_carts(user):
    """Get all carts for a user"""
    from Orders.models import Cart
    return get_related(user, 'User:Cart', Cart)


def attach_user_cart(user, cart_obj, meta=None, created_by=None):
    """Attach a cart to a user"""
    from Orders.models import Cart
    return attach_relation('User:Cart', user, cart_obj, meta=meta, created_by=created_by)


def detach_user_cart(user, cart_obj):
    """Detach a cart from a user"""
    from Orders.models import Cart
    return detach_relation('User:Cart', user, cart_obj)


def get_user_orders(user):
    """Get all orders for a user"""
    from Orders.models import Order
    return get_related(user, 'User:Order', Order)


def attach_user_order(user, order_obj, meta=None, created_by=None):
    """Attach an order to a user"""
    from Orders.models import Order
    return attach_relation('User:Order', user, order_obj, meta=meta, created_by=created_by)


def detach_user_order(user, order_obj):
    """Detach an order from a user"""
    from Orders.models import Order
    return detach_relation('User:Order', user, order_obj)


def get_user_designer_profiles(user):
    """Get all designer profiles for a user"""
    from Profiles.models import DesignerProfile
    return get_related(user, 'User:DesignerProfile', DesignerProfile)


def attach_user_designer_profile(user, designer_profile_obj, meta=None, created_by=None):
    """Attach a designer profile to a user"""
    from Profiles.models import DesignerProfile
    return attach_relation('User:DesignerProfile', user, designer_profile_obj, meta=meta, created_by=created_by)


def detach_user_designer_profile(user, designer_profile_obj):
    """Detach a designer profile from a user"""
    from Profiles.models import DesignerProfile
    return detach_relation('User:DesignerProfile', user, designer_profile_obj)


def get_user_studio_members(user):
    """Get all studio members for a user"""
    from Profiles.models import StudioMember
    return get_related(user, 'User:StudioMember', StudioMember)


def attach_user_studio_member(user, studio_member_obj, meta=None, created_by=None):
    """Attach a studio member to a user"""
    from Profiles.models import StudioMember
    return attach_relation('User:StudioMember', user, studio_member_obj, meta=meta, created_by=created_by)


def detach_user_studio_member(user, studio_member_obj):
    """Detach a studio member from a user"""
    from Profiles.models import StudioMember
    return detach_relation('User:StudioMember', user, studio_member_obj)


def get_user_razorpay_payments(user):
    """Get all razorpay payments for a user"""
    from Razorpay.models import RazorpayPayment
    return get_related(user, 'User:RazorpayPayment', RazorpayPayment)


def attach_user_razorpay_payment(user, razorpay_payment_obj, meta=None, created_by=None):
    """Attach a razorpay payment to a user"""
    from Razorpay.models import RazorpayPayment
    return attach_relation('User:RazorpayPayment', user, razorpay_payment_obj, meta=meta, created_by=created_by)


def detach_user_razorpay_payment(user, razorpay_payment_obj):
    """Detach a razorpay payment from a user"""
    from Razorpay.models import RazorpayPayment
    return detach_relation('User:RazorpayPayment', user, razorpay_payment_obj)


def get_user_wallets(user):
    """Get all wallets for a user"""
    from Wallet.models import Wallet
    return get_related(user, 'User:Wallet', Wallet)


def attach_user_wallet(user, wallet_obj, meta=None, created_by=None):
    """Attach a wallet to a user"""
    from Wallet.models import Wallet
    return attach_relation('User:Wallet', user, wallet_obj, meta=meta, created_by=created_by)


def detach_user_wallet(user, wallet_obj):
    """Detach a wallet from a user"""
    from Wallet.models import Wallet
    return detach_relation('User:Wallet', user, wallet_obj)
