from django.contrib import admin
from django.apps import apps
from django.db.models import Q
from .models import Media, Relation


@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    """
    Admin interface for Media model.
    Manages media files including images and videos with file uploads.
    """
    list_display = ['id', 'file', 'media_type', 'created_by', 'created_at']
    list_filter = ['media_type', 'created_at', 'updated_at']
    search_fields = ['file', 'created_by__username', 'created_by__email']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['media_type']
    ordering = ['-created_at']
    list_per_page = 25  # Default number of items per page
    
    fieldsets = (
        ('Media Information', {
            'fields': ('file', 'media_type', 'created_by')
        }),
        ('User Information', {
            'fields': ('updated_by',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by', 'updated_by')


@admin.register(Relation)
class RelationAdmin(admin.ModelAdmin):
    """
    Admin interface for Relation model.
    Manages flexible many-to-many relationships between various models.
    """
    list_display = ['id', 'relation_type', 'id_1', 'title_1', 'id_2', 'title_2', 'created_by', 'created_at']
    list_filter = ['relation_type', 'created_at', 'updated_at']
    search_fields = ['relation_type', 'created_by__username', 'created_by__email', 'id_1', 'id_2']
    readonly_fields = ['created_at', 'updated_at', 'title_1', 'title_2']
    ordering = ['-created_at']
    list_per_page = 50  # Default number of items per page
    list_max_show_all = 500  # Maximum number of items to show when "Show all" is clicked
    
    fieldsets = (
        ('Relation Information', {
            'fields': ('relation_type', 'id_1', 'title_1', 'id_2', 'title_2', 'meta', 'created_by')
        }),
        ('User Information', {
            'fields': ('updated_by',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by', 'updated_by')
    
    def get_search_results(self, request, queryset, search_term):
        """
        Custom search that searches in id_1, id_2, title_1, and title_2.
        """
        # First, get the base queryset from parent search (searches in relation_type, created_by, etc.)
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        
        if not search_term:
            return queryset, use_distinct
        
        # Start with all relations for searching in computed fields
        all_relations = Relation.objects.all()
        
        # Try to parse search term as integer for ID search
        try:
            search_id = int(search_term)
            # Search by id_1 or id_2
            id_matches = all_relations.filter(
                Q(id_1=search_id) | Q(id_2=search_id)
            )
            queryset = queryset | id_matches
            use_distinct = True
        except ValueError:
            # Not a number, will search in string representations
            pass
        
        # Search in title_1 and title_2 (string representations)
        # We need to iterate through relations and check their string representations
        # This is necessary for searching in computed fields
        matching_ids = []
        search_lower = search_term.lower()
        
        # Limit the search to a reasonable number to avoid performance issues
        # Search in the current queryset if it's filtered, otherwise search all
        relations_to_search = queryset if queryset.count() < 1000 else all_relations[:1000]
        
        for relation in relations_to_search:
            try:
                title_1_str = self._get_object_str(relation.relation_type, relation.id_1, is_id_1=True)
                title_2_str = self._get_object_str(relation.relation_type, relation.id_2, is_id_1=False)
                
                if (search_lower in title_1_str.lower() or 
                    search_lower in title_2_str.lower()):
                    matching_ids.append(relation.id)
            except Exception:
                # Skip if there's an error getting the string representation
                continue
        
        if matching_ids:
            # Filter queryset to include matching relations
            title_matches = Relation.objects.filter(id__in=matching_ids)
            queryset = queryset | title_matches
            use_distinct = True
        
        return queryset, use_distinct
    
    def _get_model_class(self, model_name):
        """
        Get model class dynamically from model name.
        Handles various model name formats and app locations.
        """
        # Map of model names to their app locations
        model_map = {
            'Product': ('Catalog', 'Product'),
            'Category': ('Catalog', 'Category'),
            'Tags': ('Catalog', 'Tags'),
            'Tag': ('Catalog', 'Tags'),
            'Media': ('MediaFiles', 'Media'),
            'User': ('auth', 'User'),
            'Order': ('Orders', 'Order'),
            'Cart': ('Orders', 'Cart'),
            'OrderTransaction': ('Orders', 'OrderTransaction'),
            'DesignerProfile': ('Profiles', 'DesignerProfile'),
            'Studio': ('Profiles', 'Studio'),
            'Address': ('Profiles', 'Addresses'),
            'Addresses': ('Profiles', 'Addresses'),
            'Plan': ('Plans', 'Plan'),
            'Counter': ('Catalog', 'ProductCounter'),
            'ProductCounter': ('Catalog', 'ProductCounter'),
            'DesignApproval': ('CoreAdmin', 'DesignApproval'),
            'DesignAnalytics': ('CoreAdmin', 'DesignAnalytics'),
            'CollectionBundle': ('Catalog', 'CollectionBundle'),
            'Coupon': ('Orders', 'Coupon'),
            'Usage': ('Orders', 'CouponUsage'),
            'Refund': ('Orders', 'Refund'),
            'RefundLog': ('Orders', 'RefundLog'),
            'RazorpayPayment': ('Razorpay', 'RazorpayPayment'),
            'Wallet': ('Wallet', 'Wallet'),
            'WalletTransaction': ('Wallet', 'WalletTransaction'),
            'WithdrawalRequest': ('Wallet', 'WithdrawalRequest'),
            'Email': ('Authentication', 'Email'),
            'MobileNumber': ('Authentication', 'MobileNumber'),
            'OTP': ('Authentication', 'OTP'),
            'PDFDownload': ('Catalog', 'PDFDownload'),
            'ReportIssue': ('Feedback', 'ReportIssue'),
            'FeedbackReview': ('Feedback', 'FeedbackReview'),
            'CustomOrderRequest': ('Orders', 'CustomOrderRequest'),
            'CustomRequest': ('Orders', 'CustomRequest'),
            'AdminActivityLog': ('CoreAdmin', 'AdminActivityLog'),
            'AdminSession': ('CoreAdmin', 'AdminSession'),
            'CustomerAccountStatus': ('Profiles', 'CustomerAccountStatus'),
            'CustomerDownloadHistory': ('Profiles', 'CustomerDownloadHistory'),
            'CustomerNotification': ('Profiles', 'CustomerNotification'),
            'CustomerViewHistory': ('Profiles', 'CustomerViewHistory'),
            'DesignerAccountSuspension': ('Profiles', 'DesignerAccountSuspension'),
            'DesignerNotification': ('Profiles', 'DesignerNotification'),
            'DesignerOnboardingStatus': ('Profiles', 'DesignerOnboardingStatus'),
            'Notification': ('Profiles', 'Notification'),
            'PromotionUsage': ('Orders', 'PromotionUsage'),
            'StudioMember': ('Profiles', 'StudioMember'),
            'Subscription': ('Plans', 'Subscription'),
            'TopDesignsReport': ('CoreAdmin', 'TopDesignsReport'),
            'TopDesignersReport': ('CoreAdmin', 'TopDesignersReport'),
        }
        
        if model_name in model_map:
            app_label, model_label = model_map[model_name]
            try:
                return apps.get_model(app_label, model_label)
            except LookupError:
                pass
        
        # Fallback: try common app locations
        for app_label in ['Catalog', 'MediaFiles', 'Profiles', 'Orders', 'Plans', 'CoreAdmin', 'Razorpay', 'Wallet', 'Authentication', 'Feedback']:
            try:
                return apps.get_model(app_label, model_name)
            except LookupError:
                continue
        
        return None
    
    def _get_object_str(self, relation_type, obj_id, is_id_1=True):
        """
        Get string representation of an object based on relation type and ID.
        """
        if not relation_type or not obj_id:
            return '-'
        
        try:
            # Parse relation type (e.g., "Product:Media" -> ["Product", "Media"])
            parts = relation_type.split(':')
            if len(parts) != 2:
                return '-'
            
            # Get model name based on which ID we're looking for
            model_name = parts[0] if is_id_1 else parts[1]
            
            # Get model class
            model_class = self._get_model_class(model_name)
            if not model_class:
                return f'Unknown Model ({model_name})'
            
            # Fetch the object
            try:
                obj = model_class.objects.get(pk=obj_id)
                return str(obj)
            except model_class.DoesNotExist:
                return f'Not Found (ID: {obj_id})'
            except Exception as e:
                return f'Error: {str(e)}'
        except Exception as e:
            return f'Error: {str(e)}'
    
    def title_1(self, obj):
        """Display string representation of object referenced by id_1"""
        return self._get_object_str(obj.relation_type, obj.id_1, is_id_1=True)
    title_1.short_description = 'Title 1'
    title_1.admin_order_field = 'id_1'
    
    def title_2(self, obj):
        """Display string representation of object referenced by id_2"""
        return self._get_object_str(obj.relation_type, obj.id_2, is_id_1=False)
    title_2.short_description = 'Title 2'
    title_2.admin_order_field = 'id_2'