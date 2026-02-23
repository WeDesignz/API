from rest_framework import serializers
from django.contrib.auth.models import User
from .models import FeedbackQuestion, FeedbackReview, ReportIssue, SupportThread, SupportMessage, FAQ, FAQTag
from Accounts.serializers import UserSerializer
from MediaFiles.serializers import MediaSerializer


class FeedbackQuestionSerializer(serializers.ModelSerializer):
    """
    Serializer for FeedbackQuestion model with full CRUD operations.
    Handles feedback question creation, updates, and management.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    reviews_count = serializers.SerializerMethodField()
    
    class Meta:
        model = FeedbackQuestion
        fields = [
            'id', 'question', 'feedback_question_type', 'status', 'for_whom',
            'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id', 'reviews_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_reviews_count(self, obj):
        """
        Get count of reviews for this feedback question.
        """
        return obj.reviews.count()
    
    def validate_question(self, value):
        """
        Validate question is not empty.
        """
        if not value.strip():
            raise serializers.ValidationError("Question cannot be empty.")
        return value.strip()
    
    def validate(self, attrs):
        """
        Validate business logic for feedback questions.
        """
        feedback_question_type = attrs.get('feedback_question_type')
        for_whom = attrs.get('for_whom')
        
        # Validate that rating questions have appropriate settings
        if feedback_question_type == 'rating' and for_whom not in ['customers', 'designers']:
            raise serializers.ValidationError("Rating questions are typically for customers or designers.")
        
        return attrs


class FeedbackQuestionListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for FeedbackQuestion model used in list views.
    """
    reviews_count = serializers.SerializerMethodField()
    
    class Meta:
        model = FeedbackQuestion
        fields = [
            'id', 'question', 'feedback_question_type', 'status', 'for_whom', 'created_at', 'reviews_count'
        ]
    
    def get_reviews_count(self, obj):
        """
        Get count of reviews for this feedback question.
        """
        return obj.reviews.count()


class FeedbackQuestionCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating feedback questions with minimal required fields.
    """
    created_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = FeedbackQuestion
        fields = ['question', 'feedback_question_type', 'for_whom', 'created_by_id']
    
    def validate_question(self, value):
        """
        Validate question is not empty.
        """
        if not value.strip():
            raise serializers.ValidationError("Question cannot be empty.")
        return value.strip()


class FeedbackReviewSerializer(serializers.ModelSerializer):
    """
    Serializer for FeedbackReview model with full CRUD operations.
    Handles feedback review creation, updates, and management.
    """
    feedback_question = FeedbackQuestionSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    feedback_question_id = serializers.IntegerField(write_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = FeedbackReview
        fields = [
            'id', 'feedback_question', 'feedback_question_id', 'review', 'rating',
            'created_by', 'created_at', 'created_by_id'
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate_feedback_question_id(self, value):
        """
        Validate that feedback question exists.
        """
        try:
            FeedbackQuestion.objects.get(id=value)
        except FeedbackQuestion.DoesNotExist:
            raise serializers.ValidationError("Feedback question does not exist.")
        return value
    
    def validate_rating(self, value):
        """
        Validate rating is within valid range.
        """
        if value is not None:
            if value < 1 or value > 5:
                raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value
    
    def validate(self, attrs):
        """
        Validate business logic for feedback reviews.
        """
        feedback_question_id = attrs.get('feedback_question_id')
        rating = attrs.get('rating')
        
        if feedback_question_id:
            try:
                question = FeedbackQuestion.objects.get(id=feedback_question_id)
                
                # Validate rating is required for rating questions
                if question.feedback_question_type == 'rating' and rating is None:
                    raise serializers.ValidationError("Rating is required for rating questions.")
                
                # Validate review text is required for review questions
                if question.feedback_question_type == 'review' and not attrs.get('review', '').strip():
                    raise serializers.ValidationError("Review text is required for review questions.")
                
            except FeedbackQuestion.DoesNotExist:
                raise serializers.ValidationError("Feedback question does not exist.")
        
        return attrs


class FeedbackReviewListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for FeedbackReview model used in list views.
    """
    feedback_question = FeedbackQuestionListSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = FeedbackReview
        fields = [
            'id', 'feedback_question', 'review', 'rating', 'created_by', 'created_at'
        ]


class FeedbackReviewCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating feedback reviews with minimal required fields.
    """
    feedback_question_id = serializers.IntegerField()
    created_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = FeedbackReview
        fields = ['feedback_question_id', 'review', 'rating', 'created_by_id']
    
    def validate_feedback_question_id(self, value):
        """
        Validate that feedback question exists and is active.
        """
        try:
            question = FeedbackQuestion.objects.get(id=value)
            if question.status != 'enable':
                raise serializers.ValidationError("Feedback question is not active.")
        except FeedbackQuestion.DoesNotExist:
            raise serializers.ValidationError("Feedback question does not exist.")
        return value


class ReportIssueSerializer(serializers.ModelSerializer):
    """
    Serializer for ReportIssue model with full CRUD operations.
    Handles issue reporting, updates, and management.
    """
    user = UserSerializer(read_only=True)
    resolved_by = UserSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True, required=False)
    resolved_by_id = serializers.IntegerField(write_only=True, required=False)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    media = serializers.SerializerMethodField()
    
    class Meta:
        model = ReportIssue
        fields = [
            'id', 'user', 'user_id', 'title', 'description', 'priority', 'status',
            'resolution', 'resolved_by', 'resolved_by_id', 'resolved_at',
            'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id', 'media'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'resolved_at']
    
    def get_media(self, obj):
        """
        Get related media for the report issue.
        """
        if obj:
            media = obj.get_media()
            return MediaSerializer(media, many=True).data
        return []
    
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
    
    def validate(self, attrs):
        """
        Validate business logic for report issues.
        """
        status = attrs.get('status')
        resolution = attrs.get('resolution')
        resolved_by_id = attrs.get('resolved_by_id')
        
        # Validate resolution is provided when status is resolved
        if status == 'resolved' and not resolution:
            raise serializers.ValidationError("Resolution is required when status is resolved.")
        
        # Validate resolved_by is provided when status is resolved
        if status == 'resolved' and not resolved_by_id:
            raise serializers.ValidationError("Resolved by user is required when status is resolved.")
        
        return attrs


class ReportIssueListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for ReportIssue model used in list views.
    """
    user = UserSerializer(read_only=True)
    resolved_by = UserSerializer(read_only=True)
    media_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ReportIssue
        fields = [
            'id', 'user', 'title', 'priority', 'status', 'resolved_by',
            'resolved_at', 'created_at', 'media_count'
        ]
    
    def get_media_count(self, obj):
        """
        Get count of related media.
        """
        return len(obj.get_media())


class ReportIssueCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating report issues with minimal required fields.
    """
    user_id = serializers.IntegerField(required=False)
    created_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = ReportIssue
        fields = ['user_id', 'title', 'description', 'priority', 'created_by_id']
    
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


class ReportIssueUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating report issues with selective field updates.
    """
    updated_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = ReportIssue
        fields = ['title', 'description', 'priority', 'status', 'resolution', 'updated_by_id']
    
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


class ReportIssueStatusUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating report issue status.
    """
    status = serializers.ChoiceField(choices=ReportIssue._meta.get_field('status').choices)
    resolution = serializers.CharField(required=False, allow_blank=True)
    resolved_by_id = serializers.IntegerField(required=False)
    
    def validate(self, attrs):
        """
        Validate status update logic.
        """
        status = attrs.get('status')
        resolution = attrs.get('resolution')
        resolved_by_id = attrs.get('resolved_by_id')
        
        # Validate resolution is provided when status is resolved
        if status == 'resolved' and not resolution:
            raise serializers.ValidationError("Resolution is required when status is resolved.")
        
        # Validate resolved_by is provided when status is resolved
        if status == 'resolved' and not resolved_by_id:
            raise serializers.ValidationError("Resolved by user is required when status is resolved.")
        
        return attrs


class FeedbackSearchSerializer(serializers.Serializer):
    """
    Serializer for feedback search functionality.
    """
    query = serializers.CharField(max_length=200, required=False)
    feedback_question_type = serializers.ChoiceField(
        choices=FeedbackQuestion.TYPE_CHOICES,
        required=False
    )
    for_whom = serializers.ChoiceField(
        choices=FeedbackQuestion.FOR_CHOICES,
        required=False
    )
    status = serializers.ChoiceField(
        choices=FeedbackQuestion.STATUS_CHOICES,
        required=False
    )
    min_rating = serializers.IntegerField(required=False)
    max_rating = serializers.IntegerField(required=False)
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    
    def validate(self, attrs):
        """
        Validate search parameters.
        """
        min_rating = attrs.get('min_rating')
        max_rating = attrs.get('max_rating')
        
        if min_rating is not None and max_rating is not None:
            if min_rating > max_rating:
                raise serializers.ValidationError("Min rating cannot be greater than max rating.")
        
        created_after = attrs.get('created_after')
        created_before = attrs.get('created_before')
        
        if created_after and created_before:
            if created_after >= created_before:
                raise serializers.ValidationError("Created after date must be before created before date.")
        
        return attrs


class ReportIssueSearchSerializer(serializers.Serializer):
    """
    Serializer for report issue search functionality.
    """
    query = serializers.CharField(max_length=200, required=False)
    priority = serializers.ChoiceField(
        choices=ReportIssue._meta.get_field('priority').choices,
        required=False
    )
    status = serializers.ChoiceField(
        choices=ReportIssue._meta.get_field('status').choices,
        required=False
    )
    user_id = serializers.IntegerField(required=False)
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    
    def validate(self, attrs):
        """
        Validate search parameters.
        """
        created_after = attrs.get('created_after')
        created_before = attrs.get('created_before')
        
        if created_after and created_before:
            if created_after >= created_before:
                raise serializers.ValidationError("Created after date must be before created before date.")
        
        return attrs


class FeedbackAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for feedback analytics data.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=['feedback_question_type', 'for_whom', 'rating'],
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


class ReportIssueAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for report issue analytics data.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=['priority', 'status', 'user'],
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


class BulkFeedbackQuestionUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk feedback question updates.
    """
    question_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    updates = serializers.DictField()
    
    def validate_question_ids(self, value):
        """
        Validate that all feedback questions exist.
        """
        existing_questions = FeedbackQuestion.objects.filter(id__in=value).count()
        if existing_questions != len(value):
            raise serializers.ValidationError("One or more feedback questions do not exist.")
        return value
    
    def validate_updates(self, value):
        """
        Validate update fields.
        """
        allowed_fields = ['status', 'for_whom']
        for field in value.keys():
            if field not in allowed_fields:
                raise serializers.ValidationError(f"Field '{field}' is not allowed for bulk update.")
        return value


class BulkReportIssueUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk report issue updates.
    """
    issue_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    updates = serializers.DictField()
    
    def validate_issue_ids(self, value):
        """
        Validate that all report issues exist.
        """
        existing_issues = ReportIssue.objects.filter(id__in=value).count()
        if existing_issues != len(value):
            raise serializers.ValidationError("One or more report issues do not exist.")
        return value
    
    def validate_updates(self, value):
        """
        Validate update fields.
        """
        allowed_fields = ['priority', 'status', 'resolution']
        for field in value.keys():
            if field not in allowed_fields:
                raise serializers.ValidationError(f"Field '{field}' is not allowed for bulk update.")
        return value


# ==================== SUPPORT SERIALIZERS ====================

class SupportMessageSerializer(serializers.ModelSerializer):
    """
    Serializer for SupportMessage model.
    """
    sender = UserSerializer(read_only=True)
    sender_name = serializers.SerializerMethodField()
    sender_type = serializers.SerializerMethodField()
    timestamp = serializers.DateTimeField(source='created_at', read_only=True)
    content = serializers.CharField(source='message', read_only=True)
    
    class Meta:
        model = SupportMessage
        fields = [
            'id', 'thread', 'sender', 'sender_name', 'sender_type', 'message', 'content', 'read_at', 'read_by',
            'created_at', 'updated_at', 'timestamp'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'read_at', 'read_by', 'content']
    
    def get_sender_name(self, obj):
        """Get sender name as string."""
        if obj.sender.first_name and obj.sender.last_name:
            return f"{obj.sender.first_name} {obj.sender.last_name}"
        return obj.sender.username or obj.sender.email or 'Support Team'
    
    def get_sender_type(self, obj):
        """Determine if sender is user or support/admin."""
        if obj.sender.is_staff or obj.sender.is_superuser:
            return 'support'
        return 'user'


class SupportThreadSerializer(serializers.ModelSerializer):
    """
    Serializer for SupportThread model with full details.
    """
    created_by = UserSerializer(read_only=True)
    assigned_to = UserSerializer(read_only=True)
    resolved_by = UserSerializer(read_only=True)
    last_activity = serializers.DateTimeField(read_only=True)
    message_count = serializers.IntegerField(read_only=True)
    messages = SupportMessageSerializer(many=True, read_only=True)
    
    class Meta:
        model = SupportThread
        fields = [
            'id', 'subject', 'category', 'priority', 'status',
            'created_by', 'assigned_to', 'resolved_by', 'resolved_at',
            'resolution', 'created_at', 'updated_at', 'last_activity',
            'message_count', 'messages'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'resolved_at']
    
    def to_representation(self, instance):
        """Add thread_id as alias for id."""
        data = super().to_representation(instance)
        data['thread_id'] = instance.id
        return data


class SupportThreadListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for SupportThread model used in list views.
    """
    created_by = UserSerializer(read_only=True)
    last_activity = serializers.DateTimeField(read_only=True)
    message_count = serializers.IntegerField(read_only=True)
    last_message = serializers.SerializerMethodField()
    last_sender = serializers.SerializerMethodField()
    last_sender_type = serializers.SerializerMethodField()
    has_unread = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    creator_type = serializers.SerializerMethodField()
    
    class Meta:
        model = SupportThread
        fields = [
            'id', 'subject', 'category', 'priority', 'status', 'thread_type',
            'created_by', 'created_at', 'updated_at', 'last_activity',
            'message_count', 'last_message', 'last_sender', 'last_sender_type', 'has_unread', 'unread_count', 'creator_type'
        ]
    
    def get_last_message(self, obj):
        """Get the last message in the thread."""
        last_message = obj.messages.order_by('-created_at').first()
        if last_message:
            return {
                'id': last_message.id,
                'message': last_message.message,
                'content': last_message.message,
                'created_at': last_message.created_at,
                'timestamp': last_message.created_at,
            }
        return None
    
    def get_last_sender(self, obj):
        """Get the sender of the last message."""
        last_message = obj.messages.order_by('-created_at').first()
        if last_message:
            if last_message.sender.first_name and last_message.sender.last_name:
                return f"{last_message.sender.first_name} {last_message.sender.last_name}"
            return last_message.sender.username or last_message.sender.email
        return 'Support Team'
    
    def get_last_sender_type(self, obj):
        """Get the type of the last sender (user or support/admin)."""
        last_message = obj.messages.order_by('-created_at').first()
        if last_message:
            if last_message.sender.is_staff or last_message.sender.is_superuser:
                return 'support'
            return 'user'
        return 'support'
    
    def get_has_unread(self, obj):
        """Check if thread has unread messages for the current user."""
        request = self.context.get('request')
        if request and request.user:
            return obj.get_unread_count(request.user) > 0
        return False
    
    def get_unread_count(self, obj):
        """Get the count of unread messages for the current user."""
        request = self.context.get('request')
        if request and request.user:
            return obj.get_unread_count(request.user)
        return 0
    
    def get_creator_type(self, obj):
        """Determine if the thread creator is a customer or designer."""
        try:
            from Profiles.models import DesignerProfile
            # Check if creator is admin/staff first
            if obj.created_by.is_staff or obj.created_by.is_superuser:
                return 'admin'
            # Check if the creator has a verified DesignerProfile or completed onboarding
            # Only mark as designer if they have an active/verified profile
            designer_profile = DesignerProfile.objects.filter(created_by=obj.created_by).first()
            if designer_profile:
                # Only consider them a designer if profile is verified or onboarding is complete
                if designer_profile.status == 'verified' or designer_profile.onboarding_completed:
                    return 'designer'
            # Otherwise, it's a customer
            return 'customer'
        except Exception:
            # Fallback: if we can't determine, assume customer
            return 'customer'
    
    def to_representation(self, instance):
        """Add thread_id as alias for id."""
        data = super().to_representation(instance)
        data['thread_id'] = instance.id
        return data


class SupportThreadCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating support threads.
    """
    created_by_id = serializers.IntegerField(required=False)
    message = serializers.CharField(write_only=True)
    thread_type = serializers.ChoiceField(
        choices=[('customer', 'Customer'), ('designer', 'Designer')],
        required=False,
        help_text='Type of thread: customer or designer. If not provided, will be auto-detected.'
    )
    
    class Meta:
        model = SupportThread
        fields = ['subject', 'category', 'priority', 'message', 'created_by_id', 'thread_type']
    
    def validate_subject(self, value):
        """Validate subject is not empty."""
        if not value.strip():
            raise serializers.ValidationError("Subject cannot be empty.")
        return value.strip()
    
    def validate_message(self, value):
        """Validate message is not empty."""
        if not value.strip():
            raise serializers.ValidationError("Message cannot be empty.")
        return value.strip()
    
    def create(self, validated_data):
        """Create thread and initial message."""
        message_text = validated_data.pop('message')
        created_by_id = validated_data.pop('created_by_id', None)
        thread_type = validated_data.pop('thread_type', None)
        
        # Get user from request context
        request = self.context.get('request')
        if created_by_id:
            from django.contrib.auth.models import User
            created_by = User.objects.get(id=created_by_id)
        elif request and request.user:
            created_by = request.user
        else:
            raise serializers.ValidationError("User is required to create support thread.")
        
        # Determine thread_type if not provided
        if not thread_type:
            # Check if user is a verified designer
            try:
                from Profiles.models import DesignerProfile
                designer_profile = DesignerProfile.objects.filter(
                    created_by=created_by
                ).first()
                
                if designer_profile and (designer_profile.status == 'verified' or designer_profile.onboarding_completed):
                    # User is a designer, default to designer type
                    # But we should check query param or header to determine context
                    # For now, default to customer unless explicitly set
                    thread_type = 'customer'  # Default, frontend should pass thread_type
                else:
                    thread_type = 'customer'
            except Exception:
                thread_type = 'customer'
        
        # Create thread with thread_type
        thread = SupportThread.objects.create(
            **validated_data,
            created_by=created_by,
            thread_type=thread_type
        )
        
        # Create initial message
        SupportMessage.objects.create(
            thread=thread,
            sender=created_by,
            message=message_text
        )
        
        return thread


class SupportMessageCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating support messages.
    """
    sender_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = SupportMessage
        fields = ['thread', 'message', 'sender_id']
    
    def validate_message(self, value):
        """Validate message is not empty."""
        if not value.strip():
            raise serializers.ValidationError("Message cannot be empty.")
        return value.strip()
    
    def create(self, validated_data):
        """Create message."""
        sender_id = validated_data.pop('sender_id', None)
        
        # Get user from request context
        request = self.context.get('request')
        if sender_id:
            from django.contrib.auth.models import User
            sender = User.objects.get(id=sender_id)
        elif request and request.user:
            sender = request.user
        else:
            raise serializers.ValidationError("User is required to send message.")
        
        thread = validated_data.pop('thread')
        
        # Create message
        message = SupportMessage.objects.create(
            thread=thread,
            sender=sender,
            **validated_data
        )
        
        # Update thread's updated_at timestamp
        thread.save(update_fields=['updated_at'])
        
        # Create notifications for new message
        self._create_notifications(message, thread, sender)
        
        return message
    
    def _create_notifications(self, message, thread, sender):
        """Create notifications when a support message is sent."""
        try:
            # Check if sender is admin (has admin_profile)
            is_admin = hasattr(sender, 'admin_profile')
            
            if is_admin:
                # Admin sent message - notify customer (thread creator)
                customer = thread.created_by
                if customer and customer.id != sender.id:
                    from CoreAdmin.models import CustomerNotification
                    from common.relations import attach_relation
                    
                    # Create customer notification
                    notification = CustomerNotification.objects.create(
                        customer_id=customer.id,
                        notification_type='other',
                        title=f'New message in support ticket: {thread.subject}',
                        message=f'You have a new message in your support ticket "{thread.subject}". Click to view and respond.',
                    )
                    # Link notification to customer
                    attach_relation('User:CustomerNotification', customer, notification)
                    
            else:
                # Customer sent message - notify admins
                from CoreAdmin.models import AdminUserProfile, AdminNotification
                from django.contrib.auth.models import User
                from common.relations import attach_relation
                
                # Get all active admin users
                admin_profiles = AdminUserProfile.objects.filter(is_active=True)
                admin_users = [profile.user for profile in admin_profiles]
                
                # If thread is assigned, notify that specific admin
                if thread.assigned_to and thread.assigned_to.id != sender.id:
                    try:
                        notification = AdminNotification.objects.create(
                            admin_id=thread.assigned_to.id,
                            notification_type='support_message',
                            title=f'New message in support ticket: {thread.subject}',
                            message=f'Customer {sender.get_full_name() or sender.username} sent a new message in support ticket "{thread.subject}". Click to view and respond.',
                            related_thread_id=thread.id,
                        )
                        attach_relation('User:AdminNotification', thread.assigned_to, notification)
                    except Exception as e:
                        pass
                else:
                    # Notify all active admins if no specific assignment
                    for admin_user in admin_users:
                        if admin_user.id != sender.id:
                            try:
                                notification = AdminNotification.objects.create(
                                    admin_id=admin_user.id,
                                    notification_type='support_message',
                                    title=f'New message in support ticket: {thread.subject}',
                                    message=f'Customer {sender.get_full_name() or sender.username} sent a new message in support ticket "{thread.subject}". Click to view and respond.',
                                    related_thread_id=thread.id,
                                )
                                attach_relation('User:AdminNotification', admin_user, notification)
                            except Exception as e:
                                pass
                
                # Also notify customer that their message was sent
                try:
                    from CoreAdmin.models import CustomerNotification
                    notification = CustomerNotification.objects.create(
                        customer_id=sender.id,
                        notification_type='other',
                        title=f'Message sent in support ticket: {thread.subject}',
                        message=f'Your message has been sent to our support team. We will respond soon.',
                    )
                    attach_relation('User:CustomerNotification', sender, notification)
                except Exception as e:
                    pass
                    
        except Exception as e:
            pass


# ==================== FAQ SERIALIZERS ====================

class FAQTagSerializer(serializers.ModelSerializer):
    """
    Serializer for FAQTag model.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    faqs_count = serializers.SerializerMethodField()
    
    class Meta:
        model = FAQTag
        fields = [
            'id', 'name', 'faqs_count', 'created_by', 'created_at',
            'updated_by', 'updated_at', 'created_by_id', 'updated_by_id'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'faqs_count']
    
    def get_faqs_count(self, obj):
        """Get count of FAQs with this tag."""
        return obj.faqs.count()
    
    def validate_name(self, value):
        """Validate name is not empty."""
        if not value.strip():
            raise serializers.ValidationError("Tag name cannot be empty.")
        return value.strip()


class FAQTagListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for FAQTag model used in list views.
    """
    faqs_count = serializers.SerializerMethodField()
    
    class Meta:
        model = FAQTag
        fields = ['id', 'name', 'faqs_count', 'created_at']
    
    def get_faqs_count(self, obj):
        """Get count of FAQs with this tag."""
        return obj.faqs.count()


class FAQSerializer(serializers.ModelSerializer):
    """
    Serializer for FAQ model with full CRUD operations.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    tags = FAQTagListSerializer(many=True, read_only=True)
    tag_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = FAQ
        fields = [
            'id', 'question', 'answer', 'slug', 'is_active', 'view_count',
            'sort_order', 'display_locations', 'tags', 'tag_ids', 'created_by', 'created_at',
            'updated_by', 'updated_at', 'created_by_id', 'updated_by_id'
        ]
        read_only_fields = ['id', 'slug', 'view_count', 'created_at', 'updated_at']
    
    def validate_question(self, value):
        """Validate question is not empty."""
        if not value.strip():
            raise serializers.ValidationError("Question cannot be empty.")
        return value.strip()
    
    def validate_answer(self, value):
        """Validate answer is not empty."""
        if not value.strip():
            raise serializers.ValidationError("Answer cannot be empty.")
        return value.strip()
    
    def create(self, validated_data):
        """Create FAQ with tags."""
        tag_ids = validated_data.pop('tag_ids', [])
        created_by_id = validated_data.pop('created_by_id', None)
        
        # Get user from request context
        request = self.context.get('request')
        if created_by_id:
            from django.contrib.auth.models import User
            created_by = User.objects.get(id=created_by_id)
        elif request and request.user:
            created_by = request.user
        else:
            raise serializers.ValidationError("User is required to create FAQ.")
        
        # Create FAQ
        faq = FAQ.objects.create(**validated_data, created_by=created_by)
        
        # Add tags
        if tag_ids:
            tags = FAQTag.objects.filter(id__in=tag_ids)
            faq.tags.set(tags)
        
        return faq
    
    def update(self, instance, validated_data):
        """Update FAQ with tags."""
        tag_ids = validated_data.pop('tag_ids', None)
        updated_by_id = validated_data.pop('updated_by_id', None)
        
        # Get user from request context
        request = self.context.get('request')
        if updated_by_id:
            from django.contrib.auth.models import User
            updated_by = User.objects.get(id=updated_by_id)
        elif request and request.user:
            updated_by = request.user
        else:
            updated_by = instance.updated_by
        
        # Update FAQ fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.updated_by = updated_by
        instance.save()
        
        # Update tags if provided
        if tag_ids is not None:
            tags = FAQTag.objects.filter(id__in=tag_ids)
            instance.tags.set(tags)
        
        return instance


class FAQListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for FAQ model used in list views.
    """
    created_by = UserSerializer(read_only=True)
    tags = FAQTagListSerializer(many=True, read_only=True)
    
    class Meta:
        model = FAQ
        fields = [
            'id', 'question', 'answer', 'slug', 'is_active', 'view_count',
            'sort_order', 'display_locations', 'tags', 'created_by', 'created_at'
        ]