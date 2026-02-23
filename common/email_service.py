from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date


class EmailService:
    """
    Centralized email service for WeDesignz platform.
    Handles all email sending with templates and proper formatting.
    """
    
    @staticmethod
    def get_logo_urls():
        """Helper method to get base64 encoded logo URLs for email templates."""
        import os
        import base64
        
        logo_url = None
        text_url = None
        
        static_root = getattr(settings, 'STATIC_ROOT', None)
        if not static_root:
            static_root = os.path.join(settings.BASE_DIR, 'staticfiles')
        
        logo_path = os.path.join(static_root, 'Logos', 'ONLY LOGO.png')
        text_path = os.path.join(static_root, 'Logos', 'ONLY TEXT.png')
        
        if os.path.exists(logo_path):
            with open(logo_path, 'rb') as f:
                logo_data = f.read()
                logo_base64 = base64.b64encode(logo_data).decode('utf-8')
                logo_mime = 'image/png'
                logo_url = f"data:{logo_mime};base64,{logo_base64}"
        
        if os.path.exists(text_path):
            with open(text_path, 'rb') as f:
                text_data = f.read()
                text_base64 = base64.b64encode(text_data).decode('utf-8')
                text_mime = 'image/png'
                text_url = f"data:{text_mime};base64,{text_base64}"
        
        return logo_url, text_url
    
    @staticmethod
    def send_welcome_email(user):
        """Send welcome email to new users."""
        try:
            subject = "Welcome to WeDesignz! 🎨"
            context = {
                'user': user,
                'site_url': settings.SITE_URL,
            }
            
            html_content = render_to_string('emails/auth/welcome.html', context)
            text_content = f"Welcome to WeDesignz, {user.first_name}!\n\nYour account has been created successfully.\n\nVisit {settings.SITE_URL} to start exploring our designs."
            
            # Use INFO_EMAIL for informational emails like welcome
            from_email = settings.INFO_EMAIL
            msg = EmailMultiAlternatives(subject, text_content, from_email, [user.email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def send_otp_email(user, otp_code, verification_type="email"):
        """Send OTP verification email."""
        try:
            logo_url, text_url = EmailService.get_logo_urls()
            subject = f"OTP Verification - WeDesignz"
            context = {
                'user': user,
                'otp_code': otp_code,
                'verification_type': verification_type,
                'site_url': settings.SITE_URL,
                'logo_url': logo_url,
                'text_url': text_url,
            }
            
            html_content = render_to_string('emails/auth/otp_verification.html', context)
            text_content = f"Your OTP for {verification_type} verification is: {otp_code}\n\nThis OTP will expire in 10 minutes."
            
            # Use NO_REPLY_EMAIL for OTP messages
            from_email = settings.NO_REPLY_EMAIL
            msg = EmailMultiAlternatives(subject, text_content, from_email, [user.email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def send_password_reset_email(user, otp_code):
        """Send password reset OTP email."""
        try:
            logo_url, text_url = EmailService.get_logo_urls()
            subject = "Password Reset - WeDesignz"
            context = {
                'user': user,
                'otp_code': otp_code,
                'site_url': settings.SITE_URL,
                'logo_url': logo_url,
                'text_url': text_url,
            }
            
            html_content = render_to_string('emails/auth/password_reset.html', context)
            text_content = f"Your password reset OTP is: {otp_code}\n\nThis OTP will expire in 10 minutes."
            
            # Use NO_REPLY_EMAIL for password reset OTP
            from_email = settings.NO_REPLY_EMAIL
            msg = EmailMultiAlternatives(subject, text_content, from_email, [user.email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def send_order_confirmation_email(user, order, order_items):
        """Send order confirmation email for custom orders only."""
        try:
            # Only send for custom orders (not cart orders - those get invoice emails)
            if order.order_type != 'custom':
                return True
            
            logo_url, text_url = EmailService.get_logo_urls()
            subject = f"Custom Order Confirmed #{order.id} - WeDesignz"
            context = {
                'user': user,
                'order': order,
                'order_items': order_items,
                'site_url': settings.SITE_URL,
                'logo_url': logo_url,
                'text_url': text_url,
            }
            
            html_content = render_to_string('emails/orders/custom_order_confirmation.html', context)
            text_content = f"Thank you for your custom order #{order.id}!\n\nYour order has been confirmed and is being processed.\n\nVisit {settings.SITE_URL}/orders to track your order status."
            
            msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def send_custom_order_completion_email(user, custom_request, delivery_time):
        """Send custom order completion email."""
        try:
            logo_url, text_url = EmailService.get_logo_urls()
            subject = f"Custom Order Completed #{custom_request.id} - WeDesignz"
            context = {
                'user': user,
                'custom_request': custom_request,
                'delivery_time': delivery_time,
                'site_url': settings.SITE_URL,
                'logo_url': logo_url,
                'text_url': text_url,
            }
            
            html_content = render_to_string('emails/custom_requests/custom_order_completion.html', context)
            text_content = f"Your custom order #{custom_request.id} has been completed!\n\nTitle: {custom_request.title}\nDelivery Time: {delivery_time} minutes\n\nVisit {settings.SITE_URL}/downloads to access your design."
            
            msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def send_payment_success_email(user, payment_details):
        """Send payment success email."""
        try:
            logo_url, text_url = EmailService.get_logo_urls()
            subject = "Payment Successful - WeDesignz"
            context = {
                'user': user,
                'payment': payment_details,
                'site_url': settings.SITE_URL,
                'logo_url': logo_url,
                'text_url': text_url,
            }
            
            html_content = render_to_string('emails/razorpay/payment_success.html', context)
            text_content = f"Your payment of ₹{payment_details.get('amount', 0)} has been processed successfully.\n\nTransaction ID: {payment_details.get('transaction_id', 'N/A')}"
            
            msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def send_payment_failed_email(user, payment_details):
        """Send payment failed email."""
        try:
            logo_url, text_url = EmailService.get_logo_urls()
            subject = "Payment Failed - WeDesignz"
            context = {
                'user': user,
                'payment': payment_details,
                'site_url': settings.SITE_URL,
                'logo_url': logo_url,
                'text_url': text_url,
            }
            
            html_content = render_to_string('emails/razorpay/payment_failed.html', context)
            text_content = f"Your payment of ₹{payment_details.get('amount', 0)} could not be processed.\n\nPlease try again or contact support if the issue persists."
            
            msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def send_subscription_purchase_email(user, subscription):
        """Send subscription purchase/activation email."""
        try:
            import os
            import base64
            
            subject = "Subscription Activated - WeDesignz 🎉"
            logo_url, text_url = EmailService.get_logo_urls()
            
            context = {
                'user': user,
                'subscription': subscription,
                'site_url': settings.SITE_URL,
                'logo_url': logo_url,
                'text_url': text_url,
            }
            
            html_content = render_to_string('emails/plans/subscription_purchase.html', context)
            text_content = f"Congratulations! Your {subscription.plan.get_plan_name_display()} subscription has been activated. You now have access to all premium features!"
            
            msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def send_subscription_renewal_email(user, subscription):
        """Send subscription renewal notification email."""
        try:
            logo_url, text_url = EmailService.get_logo_urls()
            subject = "Subscription Renewal - WeDesignz"
            context = {
                'user': user,
                'subscription': subscription,
                'site_url': settings.SITE_URL,
                'logo_url': logo_url,
                'text_url': text_url,
            }
            
            html_content = render_to_string('emails/plans/subscription_renewal.html', context)
            text_content = f"Your {subscription.plan.get_plan_name_display()} subscription will be renewed automatically on {subscription.created_at + timezone.timedelta(days=30)}."
            
            msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def send_wallet_transaction_email(user, transaction):
        """Send wallet transaction notification email."""
        try:
            logo_url, text_url = EmailService.get_logo_urls()
            subject = f"Wallet {transaction.wallet_transaction_type.title()} - WeDesignz"
            context = {
                'user': user,
                'transaction': transaction,
                'site_url': settings.SITE_URL,
                'logo_url': logo_url,
                'text_url': text_url,
            }
            
            html_content = render_to_string('emails/wallet/wallet_transaction.html', context)
            text_content = f"Wallet {transaction.wallet_transaction_type}: ₹{transaction.amount}\nDescription: {transaction.description}"
            
            msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def send_promotional_email(users, subject, template, context):
        """Send promotional email to multiple users."""
        try:
            success_count = 0
            for user in users:
                try:
                    user_context = {**context, 'user': user, 'site_url': settings.SITE_URL}
                    html_content = render_to_string(template, user_context)
                    text_content = f"Check out our latest offers at {settings.SITE_URL}"
                    
                    msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
                    msg.attach_alternative(html_content, "text/html")
                    msg.send()
                    success_count += 1
                except Exception as e:
                    continue
            
            return success_count
        except Exception as e:
            return 0
    
    # ==================== DESIGNER CONSOLE EMAIL METHODS ====================
    
    @staticmethod
    def send_designer_onboarding_welcome_email(user):
        """Send welcome email to new designers after onboarding."""
        try:
            logo_url, text_url = EmailService.get_logo_urls()
            subject = "Welcome to Designer Console - WeDesignz 🎨"
            context = {
                'user': user,
                'site_url': settings.SITE_URL,
                'logo_url': logo_url,
                'text_url': text_url,
            }
            
            html_content = render_to_string('emails/designer_console/onboarding_welcome.html', context)
            text_content = f"Welcome to WeDesignz Designer Console, {user.first_name}!\n\nYour designer profile has been created successfully. You can now start uploading designs and earning money.\n\nVisit {settings.SITE_URL}/designer-console to access your dashboard."
            
            # Use INFO_EMAIL for informational welcome emails
            from_email = settings.INFO_EMAIL
            msg = EmailMultiAlternatives(subject, text_content, from_email, [user.email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def send_design_approved_email(user, design):
        """Send email when a design is approved."""
        try:
            logo_url, text_url = EmailService.get_logo_urls()
            subject = f"Design Approved: {design.title} - WeDesignz"
            context = {
                'user': user,
                'design': design,
                'site_url': settings.SITE_URL,
                'logo_url': logo_url,
                'text_url': text_url,
            }
            
            html_content = render_to_string('emails/designer_console/design_approved.html', context)
            text_content = f"Great news! Your design '{design.title}' has been approved and is now live on the platform.\n\nPlatform ID: {design.product_number}\nCategory: {design.category.name}\n\nVisit {settings.SITE_URL}/designer-console to track your design performance."
            
            msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def send_design_rejected_email(user, design, feedback_message=None):
        """Send email when a design is rejected with feedback."""
        try:
            logo_url, text_url = EmailService.get_logo_urls()
            subject = f"Design Feedback: {design.title} - WeDesignz"
            context = {
                'user': user,
                'design': design,
                'feedback_message': feedback_message,
                'site_url': settings.SITE_URL,
                'logo_url': logo_url,
                'text_url': text_url,
            }
            
            html_content = render_to_string('emails/designer_console/design_rejected.html', context)
            text_content = f"Your design '{design.title}' needs some improvements before it can be approved.\n\nPlatform ID: {design.product_number}\n\nPlease review our feedback and resubmit your design.\n\nVisit {settings.SITE_URL}/designer-console to edit and resubmit."
            
            msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def send_settlement_processed_email(user, settlement):
        """Send email when settlement is processed."""
        try:
            logo_url, text_url = EmailService.get_logo_urls()
            subject = f"Settlement Processed: ₹{settlement.amount} - WeDesignz"
            context = {
                'user': user,
                'settlement': settlement,
                'site_url': settings.SITE_URL,
                'logo_url': logo_url,
                'text_url': text_url,
            }
            
            html_content = render_to_string('emails/designer_console/settlement_processed.html', context)
            text_content = f"Your settlement of ₹{settlement.amount} has been processed successfully.\n\nTransaction ID: {settlement.transaction_id}\nProcessed on: {settlement.processed_at}\n\nVisit {settings.SITE_URL}/designer-console to view your earnings dashboard."
            
            msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def send_designer_performance_report_email(user, metrics, report_month):
        """Send monthly performance report to designer."""
        try:
            logo_url, text_url = EmailService.get_logo_urls()
            subject = f"Monthly Performance Report - {report_month} - WeDesignz"
            context = {
                'user': user,
                'metrics': metrics,
                'report_month': report_month,
                'site_url': settings.SITE_URL,
                'logo_url': logo_url,
                'text_url': text_url,
            }
            
            html_content = render_to_string('emails/designer_console/performance_report.html', context)
            text_content = f"Here's your monthly performance report for {report_month}:\n\nTotal Designs: {metrics.get('total_designs', 0)}\nApproved Designs: {metrics.get('approved_designs', 0)}\nTotal Earnings: ₹{metrics.get('total_earnings', 0)}\nPerformance Score: {metrics.get('performance_score', 0)}/100\n\nVisit {settings.SITE_URL}/designer-console for detailed analytics."
            
            msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            return True
        except Exception as e:
            return False
    
    # ==================== CUSTOM ORDER COMMENT EMAIL METHODS ====================
    
    @staticmethod
    def send_customer_comment_notification(comment):
        """Send notification to admin when customer adds a comment."""
        try:
            logo_url, text_url = EmailService.get_logo_urls()
            subject = f"New Comment on Custom Order #{comment.custom_order_request.id} - WeDesignz"
            context = {
                'comment': comment,
                'site_url': settings.SITE_URL,
                'logo_url': logo_url,
                'text_url': text_url,
            }
            
            html_content = render_to_string('emails/custom_requests/customer_comment_added.html', context)
            text_content = f"New comment added to custom order #{comment.custom_order_request.id}.\n\nCustomer: {comment.created_by.username}\nComment: {comment.message[:100]}...\n\nPlease review and respond if needed."
            
            msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [settings.ADMIN_EMAIL])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def send_admin_response_notification(comment):
        """Send notification to customer when admin responds."""
        try:
            logo_url, text_url = EmailService.get_logo_urls()
            subject = f"Admin Response to Your Custom Order #{comment.custom_order_request.id} - WeDesignz"
            context = {
                'user': comment.custom_order_request.created_by,
                'comment': comment,
                'site_url': settings.SITE_URL,
                'logo_url': logo_url,
                'text_url': text_url,
            }
            
            html_content = render_to_string('emails/custom_requests/admin_response.html', context)
            text_content = f"Admin response to your custom order #{comment.custom_order_request.id}.\n\nResponse: {comment.message}\n\nPlease check your custom order for more details."
            
            # Use SUPPORT_EMAIL for support-related emails
            from_email = settings.SUPPORT_EMAIL
            msg = EmailMultiAlternatives(subject, text_content, from_email, [comment.custom_order_request.created_by.email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def send_system_update_notification(comment):
        """Send notification to customer when system updates the order."""
        try:
            logo_url, text_url = EmailService.get_logo_urls()
            subject = f"Update on Your Custom Order #{comment.custom_order_request.id} - WeDesignz"
            context = {
                'user': comment.custom_order_request.created_by,
                'comment': comment,
                'site_url': settings.SITE_URL,
                'logo_url': logo_url,
                'text_url': text_url,
            }
            
            html_content = render_to_string('emails/custom_requests/system_update.html', context)
            text_content = f"Update on your custom order #{comment.custom_order_request.id}.\n\nUpdate: {comment.message}\n\nPlease check your custom order for more details."
            
            # Use SUPPORT_EMAIL for support-related order updates
            from_email = settings.SUPPORT_EMAIL
            msg = EmailMultiAlternatives(subject, text_content, from_email, [comment.custom_order_request.created_by.email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def send_studio_member_credentials_email(user, studio, role, password):
        """Send login credentials to a newly created studio member."""
        try:
            subject = f"Your Studio Member Account - {studio.name} - WeDesignz"
            login_url = f"{settings.SITE_URL}/login"
            role_display = "Design Lead" if role == "design_lead" else "Designer"
            
            # Create email content
            text_content = f"""
Welcome to {studio.name}!

You have been added as a {role_display} to the studio "{studio.name}" on WeDesignz.

Your login credentials are:
Email/Username: {user.email}
Password: {password}

Please log in at: {login_url}

IMPORTANT SECURITY NOTICE:
- This is a one-time password sent to you
- Please change your password immediately after your first login
- Do not share your credentials with anyone

Once logged in, you can:
- Upload designs for {studio.name}
- Access the Designer Console
- Track your design performance

If you have any questions, please contact your studio owner.

Best regards,
WeDesignz Team
"""
            
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
        .credentials {{ background: white; padding: 20px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #667eea; }}
        .credentials-item {{ margin: 10px 0; }}
        .credentials-label {{ font-weight: bold; color: #667eea; }}
        .button {{ display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
        .warning {{ background: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Welcome to {studio.name}!</h1>
        </div>
        <div class="content">
            <p>Hello {user.first_name or 'there'},</p>
            
            <p>You have been added as a <strong>{role_display}</strong> to the studio "<strong>{studio.name}</strong>" on WeDesignz.</p>
            
            <div class="credentials">
                <h3 style="margin-top: 0;">Your Login Credentials:</h3>
                <div class="credentials-item">
                    <span class="credentials-label">Email/Username:</span> {user.email}
                </div>
                <div class="credentials-item">
                    <span class="credentials-label">Password:</span> {password}
                </div>
            </div>
            
            <div style="text-align: center;">
                <a href="{login_url}" class="button">Log In Now</a>
            </div>
            
            <div class="warning">
                <strong>⚠️ IMPORTANT SECURITY NOTICE:</strong>
                <ul style="margin: 10px 0; padding-left: 20px;">
                    <li>This is a one-time password sent to you</li>
                    <li>Please change your password immediately after your first login</li>
                    <li>Do not share your credentials with anyone</li>
                </ul>
            </div>
            
            <h3>What you can do:</h3>
            <ul>
                <li>Upload designs for {studio.name}</li>
                <li>Access the Designer Console</li>
                <li>Track your design performance</li>
            </ul>
            
            <p>If you have any questions, please contact your studio owner.</p>
            
            <p>Best regards,<br>WeDesignz Team</p>
        </div>
        <div class="footer">
            <p>This is an automated email. Please do not reply to this message.</p>
        </div>
    </div>
</body>
</html>
"""
            
            msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            return True
        except Exception as e:
            return False
    
    # ==================== INVOICE EMAIL METHODS ====================
    
    @staticmethod
    def send_customer_invoice_email(invoice, order, products):
        """Send invoice email to customer with PDF attachment."""
        try:
            import os
            import base64
            
            subject = f"Invoice #{invoice.invoice_number} - Your Purchase from WeDesignz"
            
            # Embed logos as base64 for email
            logo_base64 = None
            text_base64 = None
            
            # Try to find and encode logo files
            static_root = getattr(settings, 'STATIC_ROOT', None)
            if not static_root:
                # Fallback to staticfiles directory
                static_root = os.path.join(settings.BASE_DIR, 'staticfiles')
            
            logo_path = os.path.join(static_root, 'Logos', 'ONLY LOGO.png')
            text_path = os.path.join(static_root, 'Logos', 'ONLY TEXT.png')
            
            if os.path.exists(logo_path):
                with open(logo_path, 'rb') as f:
                    logo_data = f.read()
                    logo_base64 = base64.b64encode(logo_data).decode('utf-8')
                    logo_mime = 'image/png'
                    logo_url = f"data:{logo_mime};base64,{logo_base64}"
            else:
                logo_url = None
            
            if os.path.exists(text_path):
                with open(text_path, 'rb') as f:
                    text_data = f.read()
                    text_base64 = base64.b64encode(text_data).decode('utf-8')
                    text_mime = 'image/png'
                    text_url = f"data:{text_mime};base64,{text_base64}"
            else:
                text_url = None
            
            context = {
                'user': invoice.user,
                'invoice': invoice,
                'order': order,
                'products': products,
                'site_url': settings.SITE_URL,
                'logo_url': logo_url,
                'text_url': text_url,
            }
            
            html_content = render_to_string('emails/invoices/customer_invoice.html', context)
            text_content = f"""
Hello {invoice.user.first_name or invoice.user.username},

Thank you for your purchase! Your invoice is attached.

Invoice Number: {invoice.invoice_number}
Order Number: {order.order_number}
Total Amount: ₹{invoice.total_amount}

Items Purchased:
"""
            for product in products:
                text_content += f"- {product.title}: ₹{product.price}\n"
            
            text_content += f"""
You can download your designs from: {settings.SITE_URL}/downloads

If you have any questions, please contact our support team.

Best regards,
WeDesignz Team
"""
            
            msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [invoice.user.email])
            msg.attach_alternative(html_content, "text/html")
            
            # Attach PDF invoice if it exists
            if invoice.pdf_file_path:
                file_path = os.path.join(settings.MEDIA_ROOT, invoice.pdf_file_path)
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as pdf:
                        msg.attach(
                            f'invoice_{invoice.invoice_number}.pdf',
                            pdf.read(),
                            'application/pdf'
                        )
            
            msg.send()
            
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def send_settlement_receipt_email(invoice, settlement_request):
        """Send receipt email to designer with PDF attachment."""
        try:
            import os
            import base64
            
            subject = f"Receipt #{invoice.invoice_number} - Settlement Payment from WeDesignz"
            
            # Embed logos as base64 for email
            logo_base64 = None
            text_base64 = None
            
            # Try to find and encode logo files
            static_root = getattr(settings, 'STATIC_ROOT', None)
            if not static_root:
                # Fallback to staticfiles directory
                static_root = os.path.join(settings.BASE_DIR, 'staticfiles')
            
            logo_path = os.path.join(static_root, 'Logos', 'ONLY LOGO.png')
            text_path = os.path.join(static_root, 'Logos', 'ONLY TEXT.png')
            
            if os.path.exists(logo_path):
                with open(logo_path, 'rb') as f:
                    logo_data = f.read()
                    logo_base64 = base64.b64encode(logo_data).decode('utf-8')
                    logo_mime = 'image/png'
                    logo_url = f"data:{logo_mime};base64,{logo_base64}"
            else:
                logo_url = None
            
            if os.path.exists(text_path):
                with open(text_path, 'rb') as f:
                    text_data = f.read()
                    text_base64 = base64.b64encode(text_data).decode('utf-8')
                    text_mime = 'image/png'
                    text_url = f"data:{text_mime};base64,{text_base64}"
            else:
                text_url = None
            
            designer = settlement_request.designer
            period_start = settlement_request.settlement_period_start.strftime('%B %d, %Y')
            period_end = settlement_request.settlement_period_end.strftime('%B %d, %Y')
            
            context = {
                'user': designer,
                'invoice': invoice,
                'settlement_request': settlement_request,
                'settlement_period': f"{period_start} - {period_end}",
                'site_url': settings.SITE_URL,
                'logo_url': logo_url,
                'text_url': text_url,
            }
            
            # Use a simple receipt email template (can reuse customer invoice template or create new one)
            html_content = render_to_string('emails/invoices/customer_invoice.html', context)
            text_content = f"""
Hello {designer.first_name or designer.username},

Your settlement payment has been processed successfully! Your receipt is attached.

Receipt Number: {invoice.invoice_number}
Settlement Period: {period_start} - {period_end}
Settlement Amount: ₹{settlement_request.settlement_amount}

The payment has been transferred to your registered bank account.

If you have any questions, please contact our support team.

Best regards,
WeDesignz Team
"""
            
            msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [designer.email])
            msg.attach_alternative(html_content, "text/html")
            
            # Attach PDF receipt if it exists
            if invoice.pdf_file_path:
                file_path = os.path.join(settings.MEDIA_ROOT, invoice.pdf_file_path)
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as pdf:
                        msg.attach(
                            f'receipt_{invoice.invoice_number}.pdf',
                            pdf.read(),
                            'application/pdf'
                        )
            
            msg.send()
            
            return True
        except Exception as e:
            return False