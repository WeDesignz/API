from rest_framework import serializers
from django.contrib.auth.models import User
from .models import CustomOrderRequest
from Accounts.serializers import UserSerializer
from MediaFiles.serializers import MediaSerializer
from common.relations import get_related

class CustomOrderRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for CustomOrderRequest model with full CRUD operations.
    Handles custom order request creation, updates, and management.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    media = serializers.SerializerMethodField()
    deliverables = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomOrderRequest
        fields = [
            'id', 'title', 'description', 'status', 'payment_status', 'used_free_custom_order_allowance', 'budget',
            'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id', 'media', 'deliverables', 'sla_deadline',
            'delivery_files_uploaded', 'delivery_message'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_media(self, obj):
        """
        Get related media for the custom order request.
        """
        if obj:
            media = obj.get_media()
            return MediaSerializer(media, many=True).data
        return []
    
    def get_deliverables(self, obj):
        """Get delivery files (media with delivery_file type in meta)."""
        from MediaFiles.models import Media, Relation
        
        # Get request from context to build absolute URLs
        request = self.context.get('request') if hasattr(self, 'context') and self.context else None
        
        # Get all media files for this custom order
        media = obj.get_media()
        deliverables = []
        
        for m in media:
            try:
                # Check if this media has delivery_file in relation meta
                relation = Relation.objects.filter(
                    relation_type='CustomRequest:Media',
                    id_1=obj.pk,
                    id_2=m.pk
                ).first()
                
                if relation and relation.meta:
                    meta_data = relation.meta
                    # Check if metadata indicates this is a delivery file
                    is_delivery_file = False
                    if isinstance(meta_data, dict):
                        is_delivery_file = meta_data.get('type') == 'delivery_file'
                    elif isinstance(meta_data, str):
                        is_delivery_file = 'delivery_file' in str(meta_data).lower()
                    
                    if is_delivery_file:
                        # Get file URL and build absolute URL if request context is available
                        file_url = None
                        file_name = 'file'
                        file_size = None
                        if m.file:
                            url = m.file.url
                            file_name = m.file.name.split('/')[-1] if m.file.name else 'file'
                            file_size = m.file.size if hasattr(m.file, 'size') else None
                            
                            # Build absolute URL if we have request context
                            if request and url:
                                if url.startswith('/'):
                                    file_url = request.build_absolute_uri(url)
                                elif url.startswith('http'):
                                    file_url = url
                                else:
                                    file_url = request.build_absolute_uri('/' + url)
                            else:
                                file_url = url
                        
                        if file_url:
                            deliverables.append({
                                'id': str(m.id),
                                'fileName': file_name,
                                'url': file_url,
                                'file_url': file_url,
                                'file': file_url,  # For backward compatibility
                                'file_size': file_size,
                                'uploadedAt': m.created_at.isoformat() if m.created_at else None
                            })
            except Exception:
                continue
        
        return deliverables
    
    def validate_budget(self, value):
        """
        Validate budget is positive if provided.
        """
        if value is not None and value <= 0:
            raise serializers.ValidationError("Budget must be positive.")
        return value
    
    def validate_title(self, value):
        """
        Validate title is not empty.
        """
        if not value.strip():
            raise serializers.ValidationError("Title cannot be empty.")
        return value.strip()
    
    def validate_description(self, value):
        """
        Validate description is not empty.
        """
        if not value.strip():
            raise serializers.ValidationError("Description cannot be empty.")
        return value.strip()

class CustomOrderRequestListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for CustomOrderRequest model used in list views.
    """
    created_by = UserSerializer(read_only=True)
    media_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomOrderRequest
        fields = [
            'id', 'title', 'status', 'payment_status', 'budget', 'created_by', 'created_at', 'media_count'
        ]
    
    def get_media_count(self, obj):
        """
        Get count of related media.
        """
        return len(obj.get_media())

class CustomOrderRequestCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating custom order requests with minimal required fields.
    """
    created_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = CustomOrderRequest
        fields = ['title', 'description', 'budget', 'created_by_id']
    
    def validate_title(self, value):
        """
        Validate title is not empty.
        """
        if not value.strip():
            raise serializers.ValidationError("Title cannot be empty.")
        return value.strip()
    
    def validate_description(self, value):
        """
        Validate description is not empty.
        """
        if not value.strip():
            raise serializers.ValidationError("Description cannot be empty.")
        return value.strip()

class CustomOrderRequestUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating custom order requests with selective field updates.
    """
    updated_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = CustomOrderRequest
        fields = ['title', 'description', 'status', 'budget', 'updated_by_id']
    
    def validate_title(self, value):
        """
        Validate title is not empty.
        """
        if value is not None and not value.strip():
            raise serializers.ValidationError("Title cannot be empty.")
        return value.strip() if value else value
    
    def validate_description(self, value):
        """
        Validate description is not empty.
        """
        if value is not None and not value.strip():
            raise serializers.ValidationError("Description cannot be empty.")
        return value.strip() if value else value

class CustomOrderRequestStatusUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating custom order request status.
    """
    status = serializers.ChoiceField(choices=CustomOrderRequest.STATUS_CHOICES)
    updated_by_id = serializers.IntegerField(required=False)
    
    def validate_status(self, value):
        """
        Validate status transition is allowed.
        """
        # Add business logic for status transitions here
        # For example, prevent moving from 'completed' to 'pending'
        return value

class CustomOrderRequestSearchSerializer(serializers.Serializer):
    """
    Serializer for custom order request search functionality.
    """
    query = serializers.CharField(max_length=200, required=False)
    status = serializers.ChoiceField(
        choices=CustomOrderRequest.STATUS_CHOICES,
        required=False
    )
    min_budget = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_budget = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    user_id = serializers.IntegerField(required=False)
    
    def validate(self, attrs):
        """
        Validate search parameters.
        """
        min_budget = attrs.get('min_budget')
        max_budget = attrs.get('max_budget')
        
        if min_budget is not None and max_budget is not None:
            if min_budget > max_budget:
                raise serializers.ValidationError("Min budget cannot be greater than max budget.")
        
        created_after = attrs.get('created_after')
        created_before = attrs.get('created_before')
        
        if created_after and created_before:
            if created_after >= created_before:
                raise serializers.ValidationError("Created after date must be before created before date.")
        
        return attrs

class CustomOrderRequestFilterSerializer(serializers.Serializer):
    """
    Serializer for custom order request filtering functionality.
    """
    statuses = serializers.ListField(
        child=serializers.ChoiceField(choices=CustomOrderRequest.STATUS_CHOICES),
        required=False
    )
    budget_range = serializers.DictField(
        child=serializers.DecimalField(max_digits=10, decimal_places=2),
        required=False
    )
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    has_budget = serializers.BooleanField(required=False)
    
    def validate_budget_range(self, value):
        """
        Validate budget range format.
        """
        if value:
            if 'min' not in value or 'max' not in value:
                raise serializers.ValidationError("Budget range must have 'min' and 'max' keys.")
            if value['min'] > value['max']:
                raise serializers.ValidationError("Min budget cannot be greater than max budget.")
        return value

class CustomOrderRequestStatsSerializer(serializers.Serializer):
    """
    Serializer for custom order request statistics.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    user_id = serializers.IntegerField(required=False)
    
    def validate(self, attrs):
        """
        Validate date range.
        """
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        return attrs

class CustomOrderRequestAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for custom order request analytics data.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=['status', 'created_by', 'budget_range'],
        required=False
    )
    
    def validate(self, attrs):
        """
        Validate date range and grouping options.
        """
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        return attrs

class BulkCustomOrderRequestUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk custom order request updates.
    """
    request_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    updates = serializers.DictField()
    
    def validate_request_ids(self, value):
        """
        Validate that all custom order requests exist.
        """
        existing_requests = CustomOrderRequest.objects.filter(id__in=value).count()
        if existing_requests != len(value):
            raise serializers.ValidationError("One or more custom order requests do not exist.")
        return value
    
    def validate_updates(self, value):
        """
        Validate update fields.
        """
        allowed_fields = ['status', 'budget']
        for field in value.keys():
            if field not in allowed_fields:
                raise serializers.ValidationError(f"Field '{field}' is not allowed for bulk update.")
        return value

class CustomOrderRequestMediaSerializer(serializers.Serializer):
    """
    Serializer for managing media attachments to custom order requests.
    """
    request_id = serializers.IntegerField()
    media_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    action = serializers.ChoiceField(choices=['attach', 'detach'])
    
    def validate_request_id(self, value):
        """
        Validate that custom order request exists.
        """
        try:
            CustomOrderRequest.objects.get(id=value)
        except CustomOrderRequest.DoesNotExist:
            raise serializers.ValidationError("Custom order request does not exist.")
        return value
    
    def validate_media_ids(self, value):
        """
        Validate that all media exist.
        """
        try:
            from MediaFiles.models import Media
            existing_media = Media.objects.filter(id__in=value).count()
            if existing_media != len(value):
                raise serializers.ValidationError("One or more media files do not exist.")
        except:
            raise serializers.ValidationError("Invalid media IDs.")
        return value

class CustomOrderRequestTimelineSerializer(serializers.Serializer):
    """
    Serializer for custom order request timeline/activity tracking.
    """
    request_id = serializers.IntegerField()
    
    def validate_request_id(self, value):
        """
        Validate that custom order request exists.
        """
        try:
            CustomOrderRequest.objects.get(id=value)
        except CustomOrderRequest.DoesNotExist:
            raise serializers.ValidationError("Custom order request does not exist.")
        return value

class CustomOrderListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing custom orders in admin panel.
    """
    created_by = UserSerializer(read_only=True)
    assigned_to = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()
    sla_status = serializers.SerializerMethodField()
    media_count = serializers.SerializerMethodField()
    deliverables = serializers.SerializerMethodField()
    reference_files = serializers.SerializerMethodField()
    
    order_id = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomOrderRequest
        fields = [
            'id', 'title', 'description', 'status', 'payment_status', 'budget',
            'created_by', 'created_at', 'updated_at',
            'assigned_to', 'time_remaining', 'sla_status', 'media_count',
            'sla_deadline', 'started_at', 'completed_at', 'delivered_at',
            'delivery_files_uploaded', 'order_id', 'deliverables', 'reference_files'
        ]
    
    def get_order_id(self, obj):
        """Get the associated Order ID if exists."""
        try:
            # Access the reverse OneToOne relation
            # Use getattr to safely access the relation
            order = getattr(obj, 'order', None)
            if order:
                return order.id
            # If order is not prefetched, try to get it directly
            from Orders.models import Order
            try:
                order = Order.objects.get(custom_order_request=obj)
                return order.id
            except Order.DoesNotExist:
                pass
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)

        return None
    
    def get_assigned_to(self, obj):
        """Get assigned admin user."""
        if obj.assigned_to_id:
            from django.contrib.auth.models import User
            users = get_related(obj, 'CustomOrderRequest:User', User)
            user = users.first()
            if user:
                return {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                }
        return None
    
    def get_time_remaining(self, obj):
        """Get time remaining until SLA deadline."""
        time_remaining = obj.get_time_remaining()
        if time_remaining:
            return {
                'seconds': int(time_remaining.total_seconds()),
                'formatted': str(time_remaining),
                'is_expired': time_remaining.total_seconds() <= 0
            }
        return None
    
    def get_sla_status(self, obj):
        """Get SLA status."""
        return obj.get_sla_status()
    
    def get_media_count(self, obj):
        """Get count of related media files."""
        media = obj.get_media()
        return len(media)
    
    def get_deliverables(self, obj):
        """Get delivery files (media with delivery_file type in meta)."""
        from MediaFiles.models import Media, Relation
        from MediaFiles.serializers import MediaSerializer
        
        # Get request from context to build absolute URLs
        request = self.context.get('request') if hasattr(self, 'context') and self.context else None
        
        # Get all media files for this custom order
        media = obj.get_media()
        deliverables = []
        
        for m in media:
            try:
                # Check if this media has delivery_file in relation meta
                relation = Relation.objects.filter(
                    relation_type='CustomRequest:Media',
                    id_1=obj.pk,
                    id_2=m.pk
                ).first()
                
                if relation and relation.meta:
                    meta_data = relation.meta
                    # Check if metadata indicates this is a delivery file
                    is_delivery_file = False
                    if isinstance(meta_data, dict):
                        is_delivery_file = meta_data.get('type') == 'delivery_file'
                    elif isinstance(meta_data, str):
                        is_delivery_file = 'delivery_file' in str(meta_data).lower()
                    
                    if is_delivery_file:
                        # Get file URL and build absolute URL if request context is available
                        file_url = None
                        if m.file:
                            url = m.file.url
                            file_name = m.file.name.split('/')[-1] if m.file.name else 'file'
                            
                            # Build absolute URL if we have request context
                            if request and url:
                                if url.startswith('/'):
                                    file_url = request.build_absolute_uri(url)
                                elif url.startswith('http'):
                                    file_url = url
                                else:
                                    file_url = request.build_absolute_uri('/' + url)
                            else:
                                file_url = url
                        else:
                            file_name = 'file'
                        
                        if file_url:
                            deliverables.append({
                                'id': str(m.id),
                                'fileName': file_name,
                                'url': file_url,
                                'uploadedAt': m.created_at.isoformat() if m.created_at else None
                            })
            except Exception:
                continue
        
        return deliverables
    
    def get_reference_files(self, obj):
        """Get reference files (media that are NOT delivery files)."""
        from MediaFiles.models import Media, Relation
        from MediaFiles.serializers import MediaSerializer
        
        # Get request from context to build absolute URLs
        request = self.context.get('request') if hasattr(self, 'context') and self.context else None
        
        # Get all media files for this custom order
        media = obj.get_media()
        reference_files = []
        delivery_file_ids = set()
        
        # First, collect all delivery file IDs
        for m in media:
            try:
                relation = Relation.objects.filter(
                    relation_type='CustomRequest:Media',
                    id_1=obj.pk,
                    id_2=m.pk
                ).first()
                
                if relation and relation.meta:
                    meta_data = relation.meta
                    is_delivery_file = False
                    if isinstance(meta_data, dict):
                        is_delivery_file = meta_data.get('type') == 'delivery_file'
                    elif isinstance(meta_data, str):
                        is_delivery_file = 'delivery_file' in str(meta_data).lower()
                    
                    if is_delivery_file:
                        delivery_file_ids.add(m.pk)
            except Exception:
                continue
        
        # Now collect all non-delivery files as reference files
        for m in media:
            if m.pk not in delivery_file_ids:
                try:
                    # Get file URL and build absolute URL if request context is available
                    file_url = None
                    if m.file:
                        url = m.file.url
                        file_name = m.file.name.split('/')[-1] if m.file.name else 'file'
                        
                        # Build absolute URL if we have request context
                        if request and url:
                            if url.startswith('/'):
                                file_url = request.build_absolute_uri(url)
                            elif url.startswith('http'):
                                file_url = url
                            else:
                                file_url = request.build_absolute_uri('/' + url)
                        else:
                            file_url = url
                    else:
                        file_name = 'file'
                    
                    if file_url:
                        reference_files.append({
                            'id': str(m.id),
                            'fileName': file_name,
                            'url': file_url,
                            'uploadedAt': m.created_at.isoformat() if m.created_at else None
                        })
                except Exception:
                    continue
        
        return reference_files

class CustomOrderDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed custom order information in admin panel.
    """
    created_by = UserSerializer(read_only=True)
    assigned_to = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()
    sla_status = serializers.SerializerMethodField()
    media = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()
    can_be_cancelled = serializers.SerializerMethodField()
    can_be_delivered = serializers.SerializerMethodField()
    refund_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomOrderRequest
        fields = [
            'id', 'title', 'description', 'status', 'payment_status', 'budget',
            'created_by', 'created_at', 'updated_at',
            'assigned_to', 'time_remaining', 'sla_status', 'media', 'comments',
            'sla_deadline', 'started_at', 'completed_at', 'delivered_at',
            'delivery_files_uploaded', 'delivery_message',
            'cancellation_reason', 'cancellation_type', 'refund_amount', 'refund_reason',
            'can_be_cancelled', 'can_be_delivered', 'refund_percentage',
            'admin_notified', 'customer_notified'
        ]
    
    def get_assigned_to(self, obj):
        """Get assigned admin user."""
        if obj.assigned_to_id:
            from django.contrib.auth.models import User
            users = get_related(obj, 'CustomOrderRequest:User', User)
            user = users.first()
            if user:
                return {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                }
        return None
    
    def get_time_remaining(self, obj):
        """Get time remaining until SLA deadline."""
        time_remaining = obj.get_time_remaining()
        if time_remaining:
            return {
                'seconds': int(time_remaining.total_seconds()),
                'formatted': str(time_remaining),
                'is_expired': time_remaining.total_seconds() <= 0
            }
        return None
    
    def get_sla_status(self, obj):
        """Get SLA status."""
        return obj.get_sla_status()
    
    def get_media(self, obj):
        """Get related media files."""
        media = obj.get_media()
        return MediaSerializer(media, many=True).data
    
    def get_comments(self, obj):
        """Get related comments."""
        # Comments are now handled through OrderComment model via Order
        # Get comments through the associated Order if it exists
        if hasattr(obj, 'order') and obj.order:
            from Orders.models import OrderComment
            comments = OrderComment.objects.filter(order=obj.order).order_by('-created_at')[:10]
            from Orders.serializers import OrderCommentSerializer
            return OrderCommentSerializer(comments, many=True).data
        return []
    
    def get_can_be_cancelled(self, obj):
        """Check if order can be cancelled."""
        return obj.can_be_cancelled()
    
    def get_can_be_delivered(self, obj):
        """Check if order can be delivered."""
        return obj.can_be_delivered()
    
    def get_refund_percentage(self, obj):
        """Get refund percentage."""
        return obj.get_refund_percentage()

class CustomOrderActionSerializer(serializers.Serializer):
    """
    Serializer for custom order actions.
    """
    ACTION_CHOICES = [
        ('start', 'Start Order'),
        ('complete', 'Complete Order'),
        ('deliver', 'Deliver Order'),
        ('cancel', 'Cancel Order'),
        ('assign', 'Assign Order'),
        ('mark_delayed', 'Mark as Delayed'),
    ]
    
    action = serializers.ChoiceField(choices=ACTION_CHOICES)
    admin_notes = serializers.CharField(required=False, allow_blank=True)
    
    # For delivery action
    delivery_message = serializers.CharField(required=False, allow_blank=True)
    
    # For cancellation action
    cancellation_reason = serializers.CharField(required=False, allow_blank=True)
    cancellation_type = serializers.ChoiceField(
        choices=[('customer', 'Customer Requested'), ('admin', 'Admin Cancelled'), ('system', 'System Error')],
        required=False
    )
    refund_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    refund_reason = serializers.CharField(required=False, allow_blank=True)
    
    # For assignment action
    assigned_to_id = serializers.IntegerField(required=False, allow_null=True)
    
    def validate(self, attrs):
        """Validate action-specific requirements."""
        action = attrs.get('action')
        
        if action == 'deliver':
            if not attrs.get('delivery_message'):
                raise serializers.ValidationError("Delivery message is required for delivery action.")
        
        elif action == 'cancel':
            if not attrs.get('cancellation_reason'):
                raise serializers.ValidationError("Cancellation reason is required for cancellation action.")
            
            cancellation_type = attrs.get('cancellation_type', 'admin')
            refund_amount = attrs.get('refund_amount')
            
            if cancellation_type == 'customer' and refund_amount is None:
                # Auto-calculate 50% refund for customer cancellation
                pass
            elif cancellation_type == 'admin' and refund_amount is None:
                raise serializers.ValidationError("Refund amount is required for admin cancellation.")
        
        elif action == 'assign':
            if not attrs.get('assigned_to_id'):
                raise serializers.ValidationError("Assigned user ID is required for assignment action.")
        
        return attrs

class CustomOrderFileUploadSerializer(serializers.Serializer):
    """
    Serializer for file upload actions.
    """
    files = serializers.ListField(
        child=serializers.FileField(),
        allow_empty=False,
        help_text="List of files to upload"
    )
    delivery_message = serializers.CharField(required=False, allow_blank=True)
    admin_notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_files(self, value):
        """Validate uploaded files."""
        if len(value) == 0:
            raise serializers.ValidationError("At least one file must be uploaded.")
        
        # Check file size (max 10MB per file)
        max_size = 10 * 1024 * 1024  # 10MB
        for file in value:
            if file.size > max_size:
                raise serializers.ValidationError(f"File {file.name} is too large. Maximum size is 10MB.")
        
        return value

class CustomOrderFilterSerializer(serializers.Serializer):
    """
    Serializer for filtering custom orders.
    """
    status = serializers.ChoiceField(
        choices=CustomOrderRequest.STATUS_CHOICES,
        required=False
    )
    sla_status = serializers.ChoiceField(
        choices=[('normal', 'Normal'), ('warning', 'Warning'), ('critical', 'Critical'), ('breached', 'Breached'), ('completed', 'Completed')],
        required=False
    )
    assigned_to_id = serializers.IntegerField(required=False)
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    sla_deadline_after = serializers.DateTimeField(required=False)
    sla_deadline_before = serializers.DateTimeField(required=False)
    has_budget = serializers.BooleanField(required=False)
    min_budget = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_budget = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    search = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, attrs):
        """Validate filter parameters."""
        created_after = attrs.get('created_after')
        created_before = attrs.get('created_before')
        
        if created_after and created_before:
            if created_after >= created_before:
                raise serializers.ValidationError("Created after date must be before created before date.")
        
        sla_deadline_after = attrs.get('sla_deadline_after')
        sla_deadline_before = attrs.get('sla_deadline_before')
        
        if sla_deadline_after and sla_deadline_before:
            if sla_deadline_after >= sla_deadline_before:
                raise serializers.ValidationError("SLA deadline after date must be before SLA deadline before date.")
        
        min_budget = attrs.get('min_budget')
        max_budget = attrs.get('max_budget')
        
        if min_budget is not None and max_budget is not None:
            if min_budget > max_budget:
                raise serializers.ValidationError("Min budget cannot be greater than max budget.")
        
        return attrs

class CustomOrderAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for custom order analytics.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=['status', 'assigned_to', 'created_by', 'hour', 'day'],
        required=False
    )
    
    def validate(self, attrs):
        """Validate analytics parameters."""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        return attrs

class CustomOrderNotificationSerializer(serializers.Serializer):
    """
    Serializer for custom order notifications.
    """
    order_id = serializers.IntegerField()
    notification_type = serializers.ChoiceField(
        choices=[
            ('new_order', 'New Order'),
            ('status_update', 'Status Update'),
            ('sla_warning', 'SLA Warning'),
            ('sla_breach', 'SLA Breach'),
            ('delivery_ready', 'Delivery Ready'),
            ('cancellation', 'Cancellation')
        ]
    )
    message = serializers.CharField()
    send_email = serializers.BooleanField(default=True)
    send_in_app = serializers.BooleanField(default=True)
    recipients = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of user IDs to notify (if not provided, notifies all admins)"
    )

class CustomOrderSLAStatusSerializer(serializers.Serializer):
    """
    Serializer for SLA status information.
    """
    order_id = serializers.IntegerField()
    sla_status = serializers.CharField()
    time_remaining = serializers.DictField()
    sla_deadline = serializers.DateTimeField()
    is_breached = serializers.BooleanField()
    breach_time = serializers.DateTimeField(required=False, allow_null=True)
    assigned_to = serializers.DictField(required=False, allow_null=True)
    priority = serializers.CharField()

class CustomOrderRefundSerializer(serializers.Serializer):
    """
    Serializer for custom order refund processing.
    """
    order_id = serializers.IntegerField()
    refund_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    refund_reason = serializers.CharField()
    refund_type = serializers.ChoiceField(
        choices=[('partial', 'Partial Refund'), ('full', 'Full Refund')]
    )
    admin_notes = serializers.CharField(required=False, allow_blank=True)
    process_immediately = serializers.BooleanField(default=False)
    
    def validate_refund_amount(self, value):
        """Validate refund amount."""
        if value <= 0:
            raise serializers.ValidationError("Refund amount must be positive.")
        return value
