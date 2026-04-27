from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Media, Relation
from Accounts.serializers import UserSerializer


class MediaSerializer(serializers.ModelSerializer):
    """
    Serializer for Media model with full CRUD operations.
    Handles media file creation, updates, and management.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    file_url = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    
    class Meta:
        model = Media
        fields = [
            'id', 'file', 'file_url', 'file_size', 'media_type', 'visibility',
            'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_file_url(self, obj):
        """
        Get the URL of the media file.
        Returns absolute URL if request is available in context, otherwise relative URL.
        """
        if obj.file:
            url = obj.file.url
            # Try to get request from context to build absolute URL
            request = self.context.get('request') if hasattr(self, 'context') and self.context else None
            if request and url:
                # Build absolute URL if we have request context
                if url.startswith('/'):
                    return request.build_absolute_uri(url)
                elif url.startswith('http'):
                    return url
                else:
                    return request.build_absolute_uri('/' + url)
            return url
        return None
    
    def get_file_size(self, obj):
        """
        Get the size of the media file in bytes.
        """
        if obj.file:
            try:
                return obj.file.size
            except (OSError, ValueError):
                return None
        return None
    
    def validate_file(self, value):
        """
        Validate media file format and size.
        """
        if value:
            # Check file size (e.g., max 50MB)
            max_size = 50 * 1024 * 1024  # 50MB in bytes
            if value.size > max_size:
                raise serializers.ValidationError("File size cannot exceed 50MB.")
            
            # Check file type based on media_type
            allowed_image_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            allowed_video_types = ['video/mp4', 'video/avi', 'video/mov', 'video/webm']
            
            if hasattr(self, 'initial_data') and 'media_type' in self.initial_data:
                media_type = self.initial_data['media_type']
                if media_type == 'image' and value.content_type not in allowed_image_types:
                    raise serializers.ValidationError("Invalid image file type.")
                elif media_type == 'video' and value.content_type not in allowed_video_types:
                    raise serializers.ValidationError("Invalid video file type.")
        
        return value
    
    def validate_media_type(self, value):
        """
        Validate media type matches file content.
        """
        if hasattr(self, 'initial_data') and 'file' in self.initial_data:
            file = self.initial_data['file']
            if file:
                content_type = file.content_type
                if value == 'image' and not content_type.startswith('image/'):
                    raise serializers.ValidationError("File type does not match media type.")
                elif value == 'video' and not content_type.startswith('video/'):
                    raise serializers.ValidationError("File type does not match media type.")
        
        return value


class MediaListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for Media model used in list views.
    """
    file_url = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    
    class Meta:
        model = Media
        fields = ['id', 'file_url', 'file_size', 'media_type', 'visibility', 'created_at']
    
    def get_file_url(self, obj):
        """
        Get the URL of the media file.
        Returns absolute URL if request is available in context, otherwise relative URL.
        """
        if obj.file:
            url = obj.file.url
            # Try to get request from context to build absolute URL
            request = self.context.get('request') if hasattr(self, 'context') and self.context else None
            if request and url:
                # Build absolute URL if we have request context
                if url.startswith('/'):
                    return request.build_absolute_uri(url)
                elif url.startswith('http'):
                    return url
                else:
                    return request.build_absolute_uri('/' + url)
            return url
        return None
    
    def get_file_size(self, obj):
        """
        Get the size of the media file in bytes.
        """
        if obj.file:
            try:
                return obj.file.size
            except (OSError, ValueError):
                return None
        return None


class MediaCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating media files with minimal required fields.
    """
    created_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = Media
        fields = ['file', 'media_type', 'visibility', 'created_by_id']
    
    def validate_file(self, value):
        """
        Validate media file format and size.
        """
        if value:
            # Check file size (e.g., max 50MB)
            max_size = 50 * 1024 * 1024  # 50MB in bytes
            if value.size > max_size:
                raise serializers.ValidationError("File size cannot exceed 50MB.")
        
        return value


class MediaUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating media files with selective field updates.
    """
    updated_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = Media
        fields = ['media_type', 'visibility', 'updated_by_id']
    
    def validate_media_type(self, value):
        """
        Validate media type is valid.
        """
        if value not in ['image', 'video']:
            raise serializers.ValidationError("Invalid media type.")
        return value


class RelationSerializer(serializers.ModelSerializer):
    """
    Serializer for Relation model with full CRUD operations.
    Handles relationship creation, updates, and management.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = Relation
        fields = [
            'id', 'id_1', 'id_2', 'relation_type', 'meta',
            'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_relation_type(self, value):
        """
        Validate relation type is valid.
        """
        valid_types = [choice[0] for choice in Relation.RELATION_TYPE_CHOICES]
        if value not in valid_types:
            raise serializers.ValidationError("Invalid relation type.")
        return value
    
    def validate(self, attrs):
        """
        Validate business logic for relations.
        """
        id_1 = attrs.get('id_1')
        id_2 = attrs.get('id_2')
        relation_type = attrs.get('relation_type')
        
        # Prevent self-relation
        if id_1 == id_2:
            raise serializers.ValidationError("Cannot create relation to self.")
        
        # Check for duplicate relations
        if Relation.objects.filter(
            id_1=id_1, id_2=id_2, relation_type=relation_type
        ).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("This relation already exists.")
        
        return attrs


class RelationListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for Relation model used in list views.
    """
    class Meta:
        model = Relation
        fields = ['id', 'id_1', 'id_2', 'relation_type', 'created_at']


class RelationCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating relations with minimal required fields.
    """
    created_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = Relation
        fields = ['id_1', 'id_2', 'relation_type', 'meta', 'created_by_id']
    
    def validate_relation_type(self, value):
        """
        Validate relation type is valid.
        """
        valid_types = [choice[0] for choice in Relation.RELATION_TYPE_CHOICES]
        if value not in valid_types:
            raise serializers.ValidationError("Invalid relation type.")
        return value


class RelationUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating relations with selective field updates.
    """
    updated_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = Relation
        fields = ['meta', 'updated_by_id']


class RelationSearchSerializer(serializers.Serializer):
    """
    Serializer for relation search functionality.
    """
    relation_type = serializers.ChoiceField(
        choices=Relation.RELATION_TYPE_CHOICES,
        required=False
    )
    id_1 = serializers.IntegerField(required=False)
    id_2 = serializers.IntegerField(required=False)
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


class MediaSearchSerializer(serializers.Serializer):
    """
    Serializer for media search functionality.
    """
    query = serializers.CharField(max_length=200, required=False)
    media_type = serializers.ChoiceField(
        choices=Media.MEDIA_TYPE_CHOICES,
        required=False
    )
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    min_file_size = serializers.IntegerField(required=False)
    max_file_size = serializers.IntegerField(required=False)
    
    def validate(self, attrs):
        """
        Validate search parameters.
        """
        created_after = attrs.get('created_after')
        created_before = attrs.get('created_before')
        
        if created_after and created_before:
            if created_after >= created_before:
                raise serializers.ValidationError("Created after date must be before created before date.")
        
        min_file_size = attrs.get('min_file_size')
        max_file_size = attrs.get('max_file_size')
        
        if min_file_size is not None and max_file_size is not None:
            if min_file_size > max_file_size:
                raise serializers.ValidationError("Min file size cannot be greater than max file size.")
        
        return attrs


class MediaFilterSerializer(serializers.Serializer):
    """
    Serializer for media filtering functionality.
    """
    media_types = serializers.ListField(
        child=serializers.ChoiceField(choices=Media.MEDIA_TYPE_CHOICES),
        required=False
    )
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    file_size_range = serializers.DictField(
        child=serializers.IntegerField(),
        required=False
    )
    created_by_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    
    def validate_file_size_range(self, value):
        """
        Validate file size range format.
        """
        if value:
            if 'min' not in value or 'max' not in value:
                raise serializers.ValidationError("File size range must have 'min' and 'max' keys.")
            if value['min'] > value['max']:
                raise serializers.ValidationError("Min file size cannot be greater than max file size.")
        return value


class RelationFilterSerializer(serializers.Serializer):
    """
    Serializer for relation filtering functionality.
    """
    relation_types = serializers.ListField(
        child=serializers.ChoiceField(choices=Relation.RELATION_TYPE_CHOICES),
        required=False
    )
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    created_by_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    has_meta = serializers.BooleanField(required=False)


class BulkMediaUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk media updates.
    """
    media_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    updates = serializers.DictField()
    
    def validate_media_ids(self, value):
        """
        Validate that all media exist.
        """
        existing_media = Media.objects.filter(id__in=value).count()
        if existing_media != len(value):
            raise serializers.ValidationError("One or more media files do not exist.")
        return value
    
    def validate_updates(self, value):
        """
        Validate update fields.
        """
        allowed_fields = ['media_type', 'visibility']
        for field in value.keys():
            if field not in allowed_fields:
                raise serializers.ValidationError(f"Field '{field}' is not allowed for bulk update.")
        return value


class BulkRelationUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk relation updates.
    """
    relation_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    updates = serializers.DictField()
    
    def validate_relation_ids(self, value):
        """
        Validate that all relations exist.
        """
        existing_relations = Relation.objects.filter(id__in=value).count()
        if existing_relations != len(value):
            raise serializers.ValidationError("One or more relations do not exist.")
        return value
    
    def validate_updates(self, value):
        """
        Validate update fields.
        """
        allowed_fields = ['meta']
        for field in value.keys():
            if field not in allowed_fields:
                raise serializers.ValidationError(f"Field '{field}' is not allowed for bulk update.")
        return value


class MediaAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for media analytics data.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=['media_type', 'created_by'],
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


class RelationAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for relation analytics data.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=['relation_type', 'created_by'],
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


class MediaUploadSerializer(serializers.Serializer):
    """
    Serializer for media file upload with additional metadata.
    """
    file = serializers.FileField()
    media_type = serializers.ChoiceField(choices=Media.MEDIA_TYPE_CHOICES)
    title = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False
    )
    created_by_id = serializers.IntegerField(required=False)
    
    def validate_file(self, value):
        """
        Validate media file format and size.
        """
        if value:
            # Check file size (e.g., max 50MB)
            max_size = 50 * 1024 * 1024  # 50MB in bytes
            if value.size > max_size:
                raise serializers.ValidationError("File size cannot exceed 50MB.")
        
        return value


class RelationCreateBulkSerializer(serializers.Serializer):
    """
    Serializer for creating multiple relations at once.
    """
    relations = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=False
    )
    created_by_id = serializers.IntegerField(required=False)
    
    def validate_relations(self, value):
        """
        Validate all relations in the list.
        """
        for relation_data in value:
            if 'id_1' not in relation_data or 'id_2' not in relation_data or 'relation_type' not in relation_data:
                raise serializers.ValidationError("Each relation must have id_1, id_2, and relation_type.")
            
            # Validate relation type
            valid_types = [choice[0] for choice in Relation.RELATION_TYPE_CHOICES]
            if relation_data['relation_type'] not in valid_types:
                raise serializers.ValidationError(f"Invalid relation type: {relation_data['relation_type']}")
        
        return value