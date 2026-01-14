import os
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Category, Product, ProductCounter, CollectionBundle, Tags, PDFDownload
from Accounts.serializers import UserSerializer
from MediaFiles.serializers import MediaSerializer
from Plans.serializers import PlanSerializer


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for Category model with full CRUD operations.
    Handles category hierarchy and management.
    """
    created_by = UserSerializer(read_only=True, required=False)
    updated_by = UserSerializer(read_only=True, required=False)
    parent = serializers.StringRelatedField(read_only=True)
    parent_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    updated_by_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    subcategories = serializers.SerializerMethodField()
    products_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'icon_name', 'parent', 'parent_id', 'subcategories', 'products_count',
            'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by', 'updated_by']
    
    def get_subcategories(self, obj):
        """
        Get subcategories for this category.
        """
        if not obj:
            return []
        
        try:
            # Access subcategories - prefetch_related should have loaded them
            if hasattr(obj, 'subcategories'):
                # Use prefetched subcategories if available
                subcategories = obj.subcategories.all()
                # Always return an array, even if empty
                result = CategoryListSerializer(subcategories, many=True).data
                return result if result is not None else []
            return []
        except Exception as e:
            # Log error but return empty array
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting subcategories for category {obj.id if obj else 'unknown'}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def get_products_count(self, obj):
        """Get count of active and visible products in category and its subcategories"""
        # Get all subcategory IDs (including nested subcategories)
        def get_all_subcategory_ids(category):
            subcategory_ids = [category.id]
            for subcat in category.subcategories.all():
                subcategory_ids.extend(get_all_subcategory_ids(subcat))
            return subcategory_ids
        
        # Get all category IDs (this category + all subcategories)
        all_category_ids = get_all_subcategory_ids(obj)
        
        # Count products in this category and all subcategories
        from .models import Product
        return Product.objects.filter(
            category_id__in=all_category_ids,
            status='active',
            visibility_status='show'
        ).count()
    
    def validate_parent_id(self, value):
        """
        Validate that parent category exists and prevent circular references.
        """
        if value:
            try:
                parent = Category.objects.get(id=value)
                # Check for circular reference
                if self.instance and self.instance.id == value:
                    raise serializers.ValidationError("Category cannot be its own parent.")
            except Category.DoesNotExist:
                raise serializers.ValidationError("Parent category does not exist.")
        return value
    
    def validate(self, attrs):
        """
        Override validate to ensure created_by is not validated as required.
        It will be set in create() method from context.
        """
        # Don't validate created_by here - it will be set in create()
        return attrs
    
    def create(self, validated_data):
        """
        Create a new category instance.
        If created_by is not in validated_data, it will be set from the context.
        """
        # Remove created_by_id if present (we'll use created_by from context)
        validated_data.pop('created_by_id', None)
        validated_data.pop('updated_by_id', None)
        
        # Get created_by from context if available - this is required for the model
        created_by = self.context.get('created_by')
        if not created_by:
            # If no created_by in context, try to get from request if available
            request = self.context.get('request')
            if request and hasattr(request, 'user'):
                created_by = request.user
        
        if created_by:
            validated_data['created_by'] = created_by
        else:
            # This should not happen, but raise an error if it does
            raise serializers.ValidationError({
                'created_by': 'Created by user is required. Please ensure you are authenticated.'
            })
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """
        Update a category instance.
        Set updated_by from context if available.
        """
        # Remove updated_by_id if present (we'll use updated_by from context)
        validated_data.pop('updated_by_id', None)
        
        # Get updated_by from context if available
        updated_by = self.context.get('updated_by')
        if not updated_by:
            # If no updated_by in context, try to get from request if available
            request = self.context.get('request')
            if request and hasattr(request, 'user'):
                updated_by = request.user
        
        if updated_by:
            validated_data['updated_by'] = updated_by
        
        return super().update(instance, validated_data)


class CategoryListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for Category model used in list views.
    """
    parent = serializers.StringRelatedField(read_only=True)
    subcategories_count = serializers.SerializerMethodField()
    products_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'icon_name', 'parent', 'subcategories_count', 'products_count', 'created_at']
    
    def get_subcategories_count(self, obj):
        """
        Get count of subcategories.
        """
        return obj.subcategories.count()
    
    def get_products_count(self, obj):
        """Get count of active and visible products in category and its subcategories"""
        # Get all subcategory IDs (including nested subcategories)
        def get_all_subcategory_ids(category):
            subcategory_ids = [category.id]
            for subcat in category.subcategories.all():
                subcategory_ids.extend(get_all_subcategory_ids(subcat))
            return subcategory_ids
        
        # Get all category IDs (this category + all subcategories)
        all_category_ids = get_all_subcategory_ids(obj)
        
        # Count products in this category and all subcategories
        from .models import Product
        return Product.objects.filter(
            category_id__in=all_category_ids,
            status='active',
            visibility_status='show'
        ).count()


class TagsSerializer(serializers.ModelSerializer):
    """
    Serializer for Tags model with full CRUD operations.
    Handles tag creation, updates, and management.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = Tags
        fields = [
            'id', 'name', 'tags_type', 'created_by', 'created_at',
            'updated_by', 'updated_at', 'created_by_id', 'updated_by_id'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_name(self, value):
        """
        Validate tag name uniqueness.
        """
        if Tags.objects.filter(name=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("Tag with this name already exists.")
        return value


class TagsListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for Tags model used in list views.
    """
    class Meta:
        model = Tags
        fields = ['id', 'name', 'tags_type', 'created_at']


class ProductCounterSerializer(serializers.ModelSerializer):
    """
    Serializer for ProductCounter model with full CRUD operations.
    Handles product counter tracking and management.
    """
    created_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = ProductCounter
        fields = [
            'id', 'product_counter_type', 'created_by', 'created_at', 'created_by_id'
        ]
        read_only_fields = ['id', 'created_at']


class ProductCounterListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for ProductCounter model used in list views.
    """
    class Meta:
        model = ProductCounter
        fields = ['id', 'product_counter_type', 'created_at']


class ProductSerializer(serializers.ModelSerializer):
    """
    Serializer for Product model with full CRUD operations.
    Handles product creation, updates, and management with related data.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    category_id = serializers.IntegerField(write_only=True)
    category_name = serializers.SerializerMethodField()
    parent_category_name = serializers.SerializerMethodField()
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    
    # Related data fields
    media = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    plans = serializers.SerializerMethodField()
    counters = serializers.SerializerMethodField()
    uploaded_by_member = serializers.SerializerMethodField()
    studio_wedesignz_auto_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'product_metadata', 'title', 'description', 'category', 'category_id', 'category_name', 'parent_category_name',
            'status', 'product_plan_type', 'product_number', 'studio_design_number', 'color', 'price',
            'visibility_status', 'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id', 'media', 'tags', 'plans', 'counters', 'uploaded_by_member', 'studio_wedesignz_auto_name'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_category_name(self, obj):
        """
        Get the category name for easy access in frontend.
        If category has a parent, this returns the subcategory name.
        If category has no parent, this returns the category name.
        """
        if obj and obj.category:
            return obj.category.name
        return None
    
    def get_parent_category_name(self, obj):
        """
        Get the parent category name if the category is a subcategory.
        Returns None if the category has no parent (i.e., it's a top-level category).
        """
        if obj and obj.category and obj.category.parent:
            return obj.category.parent.name
        return None
    
    def get_uploaded_by_member(self, obj):
        """
        Get the studio member who uploaded this design (if any).
        Returns None if uploaded by the owner directly or not uploaded by a studio member.
        This allows studio owners to see which member uploaded each design.
        """
        if not obj or not obj.product_metadata:
            return None
        
        uploaded_by_member_id = obj.product_metadata.get('uploaded_by_member_id')
        if uploaded_by_member_id:
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                member = User.objects.get(id=uploaded_by_member_id)
                return {
                    'id': member.id,
                    'first_name': member.first_name or '',
                    'last_name': member.last_name or '',
                    'email': member.email or '',
                    'full_name': f"{member.first_name or ''} {member.last_name or ''}".strip() or member.email or 'Unknown'
                }
            except User.DoesNotExist:
                return None
        return None
    
    def get_studio_wedesignz_auto_name(self, obj):
        """
        Get the studio's WeDesignz auto name for the product creator.
        Returns None if the creator doesn't have a studio.
        """
        if not obj or not obj.created_by:
            return None
        
        try:
            from Profiles.models import Studio
            studio = Studio.objects.filter(created_by=obj.created_by).first()
            if studio and studio.wedesignz_auto_name:
                return studio.wedesignz_auto_name
        except Exception:
            pass
        
        return None
    
    def get_media(self, obj):
        """
        Get related media for the product with mockup detection and priority sorting.
        """
        if obj:
            media = obj.get_media()
            request = self.context.get('request') if hasattr(self, 'context') and self.context else None
            result = []
            
            for m in media:
                try:
                    # Get file URL safely
                    file_url = None
                    file_name = None
                    if hasattr(m, 'file') and m.file:
                        try:
                            url = m.file.url
                            file_name = m.file.name if hasattr(m.file, 'name') else None
                            # Build absolute URL if we have request context
                            if request and url:
                                if url.startswith('/'):
                                    file_url = request.build_absolute_uri(url)
                                elif url.startswith('http'):
                                    file_url = url
                                else:
                                    file_url = url
                            else:
                                file_url = url
                        except (ValueError, AttributeError):
                            file_url = None
                    
                    if not file_url:
                        continue
                    
                    # Get relation metadata once (used for both is_mockup and is_avif)
                    relation_meta = None
                    try:
                        from MediaFiles.models import Relation
                        relation = Relation.objects.filter(
                            relation_type='Product:Media',
                            id_1=obj.pk,
                            id_2=m.pk
                        ).first()
                        if relation and relation.meta:
                            relation_meta = relation.meta
                    except Exception:
                        pass
                    
                    # Check if this is a mockup image
                    is_mockup = False
                    if file_name:
                        file_name_lower = file_name.lower()
                        base_name = os.path.splitext(os.path.basename(file_name_lower))[0]
                        # Check for exact match or _MOCKUP pattern (e.g., WDG00000005_MOCKUP.jpg)
                        is_mockup = base_name == 'mockup' or base_name.endswith('_mockup') or '_mockup' in base_name
                    
                    # Also check metadata if available (FIX: Check dict value, not string search)
                    if not is_mockup and relation_meta:
                        if isinstance(relation_meta, dict):
                            is_mockup = relation_meta.get('is_mockup', False)
                        elif isinstance(relation_meta, str):
                            # Only check string metadata if it's actually a string (legacy support)
                            meta_lower = str(relation_meta).lower()
                            # More careful check - look for explicit mockup indicators
                            # but avoid matching 'is_mockup' key name
                            if 'mockup' in meta_lower and 'is_mockup' not in meta_lower:
                                is_mockup = True
                            # Also check for type: 'mockup' pattern
                            if 'type' in meta_lower and 'mockup' in meta_lower:
                                is_mockup = True
                    
                    # Check if it's JPG or PNG
                    is_jpg_png = False
                    if file_name:
                        file_name_lower = file_name.lower()
                        is_jpg_png = file_name_lower.endswith(('.jpg', '.jpeg', '.png'))
                    
                    # Check if it's AVIF
                    is_avif = False
                    if file_name:
                        file_name_lower = file_name.lower()
                        is_avif = file_name_lower.endswith('.avif')
                    
                    # Check metadata for AVIF (reuse relation_meta from above)
                    if not is_avif and relation_meta:
                        if isinstance(relation_meta, dict):
                            is_avif = relation_meta.get('is_avif', False)
                        elif isinstance(relation_meta, str):
                            is_avif = 'is_avif' in str(relation_meta).lower()
                    
                    result.append({
                        'id': getattr(m, 'id', None),
                        'file': file_url,
                        'url': file_url,
                        'media_type': getattr(m, 'media_type', 'image'),
                        'is_mockup': is_mockup,
                        'is_jpg_png': is_jpg_png,
                        'is_avif': is_avif,
                        'file_name': file_name,
                        'created_at': m.created_at.isoformat() if hasattr(m, 'created_at') and m.created_at else None
                    })
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f'Error accessing media file {getattr(m, "id", "unknown")}: {e}')
                    continue
            
            # Sort media: AVIF mockup first, then AVIF JPG/PNG, then mockup, then jpg/png, then others
            result.sort(key=lambda x: (
                0 if (x.get('is_avif') and x.get('is_mockup')) else
                1 if (x.get('is_avif') and x.get('is_jpg_png')) else
                2 if x.get('is_mockup') else
                3 if x.get('is_jpg_png') else 4,
                x.get('created_at', '')
            ))
            
            return result
        return []
    
    def get_tags(self, obj):
        """
        Get related tags for the product.
        """
        if obj:
            tags = obj.get_tags()
            return TagsListSerializer(tags, many=True).data
        return []
    
    def get_plans(self, obj):
        """
        Get related plans for the product.
        """
        if obj:
            plans = obj.get_plans()
            return PlanSerializer(plans, many=True).data
        return []
    
    def get_counters(self, obj):
        """
        Get related counters for the product.
        """
        if obj:
            counters = obj.get_counters()
            return ProductCounterListSerializer(counters, many=True).data
        return []
    
    def validate_category_id(self, value):
        """
        Validate that category exists.
        """
        try:
            Category.objects.get(id=value)
        except Category.DoesNotExist:
            raise serializers.ValidationError("Category does not exist.")
        return value
    
    def validate_price(self, value):
        """
        Validate price is positive.
        """
        if value is not None and value < 0:
            raise serializers.ValidationError("Price must be positive.")
        return value


class ProductListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for Product model used in list views.
    """
    category = CategoryListSerializer(read_only=True)
    media_count = serializers.SerializerMethodField()
    tags_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'title', 'category', 'status', 'product_plan_type',
            'price', 'visibility_status', 'created_at', 'media_count', 'tags_count'
        ]
    
    def get_media_count(self, obj):
        """
        Get count of related media.
        """
        return len(obj.get_media())
    
    def get_tags_count(self, obj):
        """
        Get count of related tags.
        """
        return len(obj.get_tags())


class ProductCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating products with minimal required fields.
    """
    category_id = serializers.IntegerField()
    created_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = Product
        fields = [
            'title', 'description', 'category_id', 'product_plan_type',
            'product_number', 'color', 'price', 'created_by_id'
        ]
    
    def validate_category_id(self, value):
        """
        Validate that category exists.
        """
        try:
            Category.objects.get(id=value)
        except Category.DoesNotExist:
            raise serializers.ValidationError("Category does not exist.")
        return value


class ProductUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating products with selective field updates.
    """
    updated_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = Product
        fields = [
            'product_metadata', 'title', 'description', 'status',
            'product_plan_type', 'product_number', 'color', 'price',
            'visibility_status', 'updated_by_id'
        ]


class CollectionBundleSerializer(serializers.ModelSerializer):
    """
    Serializer for CollectionBundle model with full CRUD operations.
    Handles collection bundle creation, updates, and management.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    plan = PlanSerializer(read_only=True)
    plan_id = serializers.IntegerField(write_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    products = serializers.SerializerMethodField()
    
    class Meta:
        model = CollectionBundle
        fields = [
            'id', 'name', 'product_ids', 'plan', 'plan_id', 'status',
            'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id', 'products'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_products(self, obj):
        """
        Get related products for the collection bundle.
        """
        if obj.product_ids:
            try:
                product_ids = [int(id) for id in obj.product_ids.split(',') if id.strip()]
                products = Product.objects.filter(id__in=product_ids)
                return ProductListSerializer(products, many=True).data
            except (ValueError, TypeError):
                return []
        return []
    
    def validate_plan_id(self, value):
        """
        Validate that plan exists.
        """
        try:
            from Plans.models import Plan
            Plan.objects.get(id=value)
        except:
            raise serializers.ValidationError("Plan does not exist.")
        return value
    
    def validate_product_ids(self, value):
        """
        Validate product IDs format and existence.
        """
        if value:
            try:
                product_ids = [int(id) for id in value.split(',') if id.strip()]
                existing_products = Product.objects.filter(id__in=product_ids).count()
                if existing_products != len(product_ids):
                    raise serializers.ValidationError("One or more products do not exist.")
            except (ValueError, TypeError):
                raise serializers.ValidationError("Invalid product IDs format.")
        return value


class CollectionBundleListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for CollectionBundle model used in list views.
    """
    plan = PlanSerializer(read_only=True)
    products_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CollectionBundle
        fields = ['id', 'name', 'plan', 'status', 'created_at', 'products_count']
    
    def get_products_count(self, obj):
        """
        Get count of products in the bundle.
        """
        if obj.product_ids:
            try:
                product_ids = [int(id) for id in obj.product_ids.split(',') if id.strip()]
                return len(product_ids)
            except (ValueError, TypeError):
                return 0
        return 0


class ProductSearchSerializer(serializers.Serializer):
    """
    Serializer for product search functionality.
    """
    query = serializers.CharField(max_length=200, required=False)
    category_id = serializers.IntegerField(required=False)
    product_plan_type = serializers.ChoiceField(
        choices=Product.PRODUCT_PLAN_TYPE_CHOICES,
        required=False
    )
    status = serializers.ChoiceField(
        choices=Product.STATUS_CHOICES,
        required=False
    )
    min_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False
    )
    
    def validate(self, attrs):
        """
        Validate search parameters.
        """
        min_price = attrs.get('min_price')
        max_price = attrs.get('max_price')
        
        if min_price is not None and max_price is not None:
            if min_price > max_price:
                raise serializers.ValidationError("Min price cannot be greater than max price.")
        
        return attrs


class ProductFilterSerializer(serializers.Serializer):
    """
    Serializer for product filtering functionality.
    """
    category_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    product_plan_types = serializers.ListField(
        child=serializers.ChoiceField(choices=Product.PRODUCT_PLAN_TYPE_CHOICES),
        required=False
    )
    statuses = serializers.ListField(
        child=serializers.ChoiceField(choices=Product.STATUS_CHOICES),
        required=False
    )
    visibility_statuses = serializers.ListField(
        child=serializers.ChoiceField(choices=Product.PRODUCT_VISIBILITY_CHOICES),
        required=False
    )
    price_range = serializers.DictField(
        child=serializers.DecimalField(max_digits=10, decimal_places=2),
        required=False
    )
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    
    def validate_price_range(self, value):
        """
        Validate price range format.
        """
        if value:
            if 'min' not in value or 'max' not in value:
                raise serializers.ValidationError("Price range must have 'min' and 'max' keys.")
            if value['min'] > value['max']:
                raise serializers.ValidationError("Min price cannot be greater than max price.")
        return value


class BulkProductUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk product updates.
    """
    product_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    updates = serializers.DictField()
    
    def validate_product_ids(self, value):
        """
        Validate that all products exist.
        """
        existing_products = Product.objects.filter(id__in=value).count()
        if existing_products != len(value):
            raise serializers.ValidationError("One or more products do not exist.")
        return value
    
    def validate_updates(self, value):
        """
        Validate update fields.
        """
        allowed_fields = [
            'status', 'visibility_status', 'product_plan_type',
            'price', 'color'
        ]
        for field in value.keys():
            if field not in allowed_fields:
                raise serializers.ValidationError(f"Field '{field}' is not allowed for bulk update.")
        return value


class PDFDownloadSerializer(serializers.ModelSerializer):
    """
    Serializer for PDFDownload model with full CRUD operations.
    Handles PDF download requests with free and paid options.
    One user can have multiple PDF downloads.
    """
    user = serializers.SerializerMethodField()
    user_id = serializers.IntegerField(write_only=True, required=False)
    razorpay_payment = serializers.StringRelatedField(read_only=True)
    included_products = serializers.SerializerMethodField()
    products_count = serializers.ReadOnlyField()
    
    class Meta:
        model = PDFDownload
        fields = [
            'id', 'user', 'user_id', 'download_type', 'status', 'total_pages',
            'selection_type', 'selected_products', 'search_filters', 'included_products',
            'products_count', 'price_per_design', 'total_amount', 'razorpay_payment', 
            'payment_status', 'pdf_file_path', 'file_size', 'created_at', 'updated_at', 
            'completed_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'completed_at', 'products_count']
    
    def get_user(self, obj):
        """
        Get user information via relation system.
        """
        user = obj.get_user()
        if user:
            return UserSerializer(user).data
        return None
    
    def get_included_products(self, obj):
        """
        Get products included in this PDF download.
        """
        if obj:
            return obj.get_included_products()
        return []
    
    def validate_total_pages(self, value):
        """
        Validate total pages is positive and within limits.
        """
        if value <= 0:
            raise serializers.ValidationError("Total pages must be greater than 0.")
        if value > 500:
            raise serializers.ValidationError("Total pages cannot exceed 500.")
        return value
    
    def validate_selected_products(self, value):
        """
        Validate selected products exist and are active.
        """
        if value:
            existing_products = Product.objects.filter(
                id__in=value,
                status='active',
                visibility_status='show'
            ).count()
            if existing_products != len(value):
                raise serializers.ValidationError("One or more selected products are not available.")
        return value


class PDFDownloadListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for PDFDownload model used in list views.
    """
    user = serializers.SerializerMethodField()
    products_count = serializers.ReadOnlyField()
    
    class Meta:
        model = PDFDownload
        fields = [
            'id', 'user', 'download_type', 'status', 'total_pages',
            'total_amount', 'payment_status', 'created_at', 'products_count'
        ]
    
    def get_user(self, obj):
        """
        Get user information via relation system.
        """
        user = obj.get_user()
        if user:
            return UserSerializer(user).data
        return None


class PDFDownloadCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating PDF download requests.
    """
    user_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = PDFDownload
        fields = [
            'download_type', 'total_pages', 'selected_products', 'search_filters',
            'user_id'
        ]
    
    def validate_download_type(self, value):
        """
        Validate download type and check free download eligibility.
        """
        user = self.context.get('request').user if self.context.get('request') else None
        
        if value == 'free' and user:
            # Check if user has already used their free download
            free_downloads = PDFDownload.objects.filter(
                user=user,
                download_type='free',
                status='completed'
            ).count()
            if free_downloads > 0:
                raise serializers.ValidationError("You have already used your free download.")
        
        return value
    
    def validate(self, attrs):
        """
        Validate the entire request.
        """
        download_type = attrs.get('download_type')
        selected_products = attrs.get('selected_products', [])
        total_pages = attrs.get('total_pages')
        
        # For paid downloads, validate payment requirements
        if download_type == 'paid':
            if not selected_products and total_pages > 0:
                # First N products from search - Rs. 2 per design
                attrs['price_per_design'] = 2.00
                attrs['total_amount'] = total_pages * 2.00
            elif selected_products:
                # Specific products selected - Rs. 4 per design
                attrs['price_per_design'] = 4.00
                attrs['total_amount'] = len(selected_products) * 4.00
            else:
                raise serializers.ValidationError("For paid downloads, either select specific products or specify total pages.")
        else:
            # Free download
            attrs['price_per_design'] = 0.00
            attrs['total_amount'] = 0.00
        
        return attrs




class PDFDownloadRequestSerializer(serializers.Serializer):
    """
    Serializer for PDF download request with search filters.
    """
    download_type = serializers.ChoiceField(choices=PDFDownload.DOWNLOAD_TYPE_CHOICES)
    total_pages = serializers.IntegerField(min_value=1, max_value=500)
    selection_type = serializers.ChoiceField(choices=PDFDownload.SELECTION_TYPE_CHOICES, default='search_results')
    selected_products = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )
    search_filters = serializers.DictField(required=False, default=dict)
    use_subscription_mock_pdf = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Whether to use subscription's mock PDF download (only for free downloads)"
    )
    customer_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        help_text="Customer name for mock PDF"
    )
    customer_mobile = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=20,
        help_text="Customer mobile number for mock PDF"
    )
    
    def validate_download_type(self, value):
        """
        Validate download type and check free download eligibility.
        """
        user = self.context.get('request').user if self.context.get('request') else None
        
        if value == 'free' and user:
            use_subscription_mock_pdf = self.initial_data.get('use_subscription_mock_pdf', False)
            
            if not use_subscription_mock_pdf:
                # Regular free download - check if user has already used their one-time free download
                from common.relations import get_related_ids_for_right
                pdf_download_ids = get_related_ids_for_right(user, 'User:PDFDownload')
                free_downloads = PDFDownload.objects.filter(
                    id__in=pdf_download_ids,
                    download_type='free',
                    status='completed'
                ).count()
                
                if free_downloads > 0:
                    raise serializers.ValidationError(
                        "You have already used your free download. "
                        "Please use paid download for additional PDFs or use your subscription mock PDF downloads if available."
                    )
        
        return value
    
    def validate(self, attrs):
        """
        Validate the PDF download request.
        """
        download_type = attrs.get('download_type')
        selected_products = attrs.get('selected_products', [])
        total_pages = attrs.get('total_pages')
        selection_type = attrs.get('selection_type', 'search_results')
        
        # For specific product selection, validate products exist
        if selection_type == 'specific':
            if not selected_products:
                raise serializers.ValidationError("Selected products are required for specific selection.")
            
            existing_products = Product.objects.filter(
                id__in=selected_products,
                status='active',
                visibility_status='show'
            ).count()
            if existing_products != len(selected_products):
                raise serializers.ValidationError("One or more selected products are not available.")
            
            # For specific selection, total_pages should match number of selected products
            if total_pages != len(selected_products):
                raise serializers.ValidationError("Total pages must match the number of selected products.")
        
        # For search results, validate search filters are provided (empty dict is allowed - means "all products")
        elif selection_type == 'search_results':
            search_filters = attrs.get('search_filters')
            if search_filters is None:
                raise serializers.ValidationError("Search filters are required for search results selection.")
            # Empty dict is allowed - it means no filters (all products)
        
        return attrs


class PDFDownloadStatusSerializer(serializers.Serializer):
    """
    Serializer for checking PDF download status.
    """
    download_id = serializers.IntegerField()
    
    def validate_download_id(self, value):
        """
        Validate that download exists.
        """
        try:
            PDFDownload.objects.get(id=value)
        except PDFDownload.DoesNotExist:
            raise serializers.ValidationError("PDF download does not exist.")
        return value


class PDFDownloadPaymentSerializer(serializers.Serializer):
    """
    Serializer for PDF download payment processing.
    """
    download_id = serializers.IntegerField()
    razorpay_payment_id = serializers.CharField(max_length=100)
    
    def validate_download_id(self, value):
        """
        Validate that download exists and is pending payment.
        """
        try:
            download = PDFDownload.objects.get(id=value)
            if download.download_type != 'paid':
                raise serializers.ValidationError("This download is not a paid download.")
            if download.payment_status != 'pending':
                raise serializers.ValidationError("This download is not pending payment.")
        except PDFDownload.DoesNotExist:
            raise serializers.ValidationError("PDF download does not exist.")
        return value
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from datetime import timedelta
from CoreAdmin.models import AdminUserProfile
from Catalog.models import Product, Category, Tags, CollectionBundle
from Profiles.models import DesignerProfile
from MediaFiles.models import Media
from Orders.models import Order, OrderTransaction
from Feedback.models import FeedbackReview, ReportIssue
from common.relations import get_related


class DesignListSerializer(serializers.ModelSerializer):
    """
    Serializer for design list view with basic information.
    """
    designer_name = serializers.SerializerMethodField()
    designer_email = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    product_plan_type_display = serializers.CharField(source='get_product_plan_type_display', read_only=True)
    media_count = serializers.SerializerMethodField()
    media_files = serializers.SerializerMethodField()
    total_views = serializers.SerializerMethodField()
    total_downloads = serializers.SerializerMethodField()
    total_purchases = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    revenue_generated = serializers.SerializerMethodField()
    flagged = serializers.SerializerMethodField()
    flag_reason = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'title', 'description', 'category', 'category_name', 'status', 'status_display',
            'product_plan_type', 'product_plan_type_display', 'product_number', 'studio_design_number',
            'color', 'price', 'visibility_status', 'created_by', 'designer_name', 'designer_email',
            'created_at', 'updated_at', 'media_count', 'media_files', 'total_views', 'total_downloads',
            'total_purchases', 'average_rating', 'revenue_generated', 'flagged', 'flag_reason'
        ]
        read_only_fields = [
            'id', 'title', 'description', 'category', 'category_name', 'status', 'status_display',
            'product_plan_type', 'product_plan_type_display', 'product_number', 'studio_design_number',
            'color', 'price', 'visibility_status', 'created_by', 'designer_name', 'designer_email',
            'created_at', 'updated_at', 'media_count', 'media_files', 'total_views', 'total_downloads',
            'total_purchases', 'average_rating', 'revenue_generated', 'flagged', 'flag_reason'
        ]
    
    def get_designer_name(self, obj):
        """Get designer name safely"""
        try:
            if hasattr(obj, 'created_by') and obj.created_by:
                try:
                    full_name = obj.created_by.get_full_name()
                    if full_name:
                        return full_name
                    first = getattr(obj.created_by, 'first_name', '') or ''
                    last = getattr(obj.created_by, 'last_name', '') or ''
                    combined = f"{first} {last}".strip()
                    if combined:
                        return combined
                    return getattr(obj.created_by, 'username', 'Unknown Designer')
                except (AttributeError, Exception):
                    return getattr(obj.created_by, 'username', 'Unknown Designer')
            return 'Unknown Designer'
        except Exception:
            return 'Unknown Designer'
    
    def get_designer_email(self, obj):
        """Get designer email safely"""
        try:
            if hasattr(obj, 'created_by') and obj.created_by:
                return getattr(obj.created_by, 'email', None)
            return None
        except Exception:
            return None
    
    def get_category_name(self, obj):
        """Get category name safely"""
        try:
            if hasattr(obj, 'category') and obj.category:
                return getattr(obj.category, 'name', None)
            return None
        except Exception:
            return None
    
    def get_media_count(self, obj):
        """Get count of media files"""
        try:
            media = get_related(obj, 'Product:Media', Media)
            if not media:
                return 0
            if hasattr(media, 'count'):
                return media.count()
            if isinstance(media, (list, tuple)):
                return len(media)
            return 0
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error getting media count for product {getattr(obj, "id", "unknown")}: {e}')
            return 0
    
    def get_media_files(self, obj):
        """Get media files for thumbnail/preview with mockup detection and AVIF prioritization"""
        try:
            media = get_related(obj, 'Product:Media', Media)
            # Handle empty QuerySet
            if not media or (hasattr(media, 'exists') and not media.exists()):
                return []
            
            # Convert to list - return all files (not just first 5) to include mockup files
            try:
                media_list = list(media)
            except (TypeError, AttributeError):
                return []
            
            if not media_list:
                return []
            
            result = []
            request = self.context.get('request') if hasattr(self, 'context') and self.context else None
            
            for m in media_list:
                try:
                    # Get file URL safely
                    file_url = None
                    file_name = None
                    if hasattr(m, 'file') and m.file:
                        try:
                            url = m.file.url
                            file_name = m.file.name if hasattr(m.file, 'name') else None
                            # Build absolute URL if we have request context
                            if request and url:
                                if url.startswith('/'):
                                    file_url = request.build_absolute_uri(url)
                                elif url.startswith('http'):
                                    file_url = url
                                else:
                                    file_url = url
                            else:
                                file_url = url
                        except (ValueError, AttributeError):
                            # File might not exist or be accessible
                            file_url = None
                    
                    if not file_url:
                        continue
                    
                    # Get relation metadata once (used for both is_mockup and is_avif)
                    relation_meta = None
                    try:
                        from MediaFiles.models import Relation
                        relation = Relation.objects.filter(
                            relation_type='Product:Media',
                            id_1=obj.pk,
                            id_2=m.pk
                        ).first()
                        if relation and relation.meta:
                            relation_meta = relation.meta
                    except Exception:
                        pass
                    
                    # Check if this is a mockup image
                    is_mockup = False
                    if file_name:
                        file_name_lower = file_name.lower()
                        base_name = os.path.splitext(os.path.basename(file_name_lower))[0]
                        # Check for exact match or _MOCKUP pattern (e.g., WDG00000005_MOCKUP.jpg)
                        is_mockup = base_name == 'mockup' or base_name.endswith('_mockup') or '_mockup' in base_name
                    
                    # Also check metadata if available
                    if not is_mockup and relation_meta:
                        if isinstance(relation_meta, dict):
                            is_mockup = relation_meta.get('is_mockup', False)
                        elif isinstance(relation_meta, str):
                            meta_lower = str(relation_meta).lower()
                            if 'mockup' in meta_lower and 'is_mockup' not in meta_lower:
                                is_mockup = True
                            if 'type' in meta_lower and 'mockup' in meta_lower:
                                is_mockup = True
                    
                    # Check if it's JPG or PNG
                    is_jpg_png = False
                    if file_name:
                        file_name_lower = file_name.lower()
                        is_jpg_png = file_name_lower.endswith(('.jpg', '.jpeg', '.png'))
                    
                    # Check if it's AVIF
                    is_avif = False
                    if file_name:
                        file_name_lower = file_name.lower()
                        is_avif = file_name_lower.endswith('.avif')
                    
                    # Check metadata for AVIF (reuse relation_meta from above)
                    if not is_avif and relation_meta:
                        if isinstance(relation_meta, dict):
                            is_avif = relation_meta.get('is_avif', False)
                        elif isinstance(relation_meta, str):
                            is_avif = 'is_avif' in str(relation_meta).lower()
                    
                    result.append({
                        'id': getattr(m, 'id', None),
                        'file': file_url,
                        'url': file_url,
                        'media_type': getattr(m, 'media_type', 'image'),
                        'is_mockup': is_mockup,
                        'is_jpg_png': is_jpg_png,
                        'is_avif': is_avif,
                        'file_name': file_name,
                        'created_at': m.created_at.isoformat() if hasattr(m, 'created_at') and m.created_at else None
                    })
                except Exception as e:
                    # Skip this media file if there's an error accessing it
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f'Error accessing media file {getattr(m, "id", "unknown")}: {e}')
                    continue
            
            # Sort media: AVIF mockup first, then AVIF JPG/PNG, then mockup, then jpg/png, then others
            result.sort(key=lambda x: (
                0 if (x.get('is_avif') and x.get('is_mockup')) else
                1 if (x.get('is_avif') and x.get('is_jpg_png')) else
                2 if x.get('is_mockup') else
                3 if x.get('is_jpg_png') else 4,
                x.get('created_at', '')
            ))
            
            return result
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error getting media files for product {obj.id}: {e}', exc_info=True)
            return []
    
    def get_total_views(self, obj):
        """Get total views count"""
        # TODO: Implement view tracking
        return 0
    
    def get_total_downloads(self, obj):
        """Get total downloads count"""
        # TODO: Implement download tracking
        return 0
    
    def get_total_purchases(self, obj):
        """Get total purchases count"""
        try:
            # Count orders that include this product
            orders = Order.objects.filter(
                cart_ids__icontains=str(obj.id),
                status='success'
            )
            return orders.count()
        except Exception:
            return 0
    
    def get_average_rating(self, obj):
        """Get average rating"""
        # TODO: Implement rating system
        return 0.0
    
    def get_revenue_generated(self, obj):
        """Get revenue generated from this design"""
        try:
            orders = Order.objects.filter(
                cart_ids__icontains=str(obj.id),
                status='success'
            )
            total_revenue = orders.aggregate(total=Sum('total_amount'))['total']
            return float(total_revenue) if total_revenue else 0.0
        except Exception:
            return 0.0
    
    def get_flagged(self, obj):
        """Get flag status from product_metadata"""
        try:
            if obj.product_metadata and isinstance(obj.product_metadata, dict):
                return obj.product_metadata.get('flagged', False)
            return False
        except Exception:
            return False
    
    def get_flag_reason(self, obj):
        """Get flag reason from product_metadata"""
        try:
            if obj.product_metadata and isinstance(obj.product_metadata, dict):
                return obj.product_metadata.get('flag_reason', None)
            return None
        except Exception:
            return None


class DesignDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed design information.
    """
    designer_name = serializers.SerializerMethodField()
    designer_email = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    parent_category_name = serializers.SerializerMethodField()
    category = CategorySerializer(read_only=True)  # Include full category object with parent info
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    product_plan_type_display = serializers.CharField(source='get_product_plan_type_display', read_only=True)
    media_files = serializers.SerializerMethodField()
    preview_files = serializers.SerializerMethodField()  # JPG, PNG, and mockup files only
    tags = serializers.SerializerMethodField()
    approval_history = serializers.SerializerMethodField()
    analytics = serializers.SerializerMethodField()
    flagged = serializers.SerializerMethodField()
    flag_reason = serializers.SerializerMethodField()
    designer = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'title', 'description', 'category', 'category_name', 'parent_category_name', 'status', 'status_display',
            'product_plan_type', 'product_plan_type_display', 'product_number', 'studio_design_number',
            'color', 'price', 'visibility_status', 'created_by', 'designer_name', 'designer_email',
            'created_at', 'updated_at', 'media_files', 'preview_files', 'tags', 'approval_history', 'analytics',
            'flagged', 'flag_reason', 'designer'
        ]
        read_only_fields = [
            'id', 'title', 'description', 'category', 'category_name', 'parent_category_name', 'status', 'status_display',
            'product_plan_type', 'product_plan_type_display', 'product_number', 'studio_design_number',
            'color', 'price', 'visibility_status', 'created_by', 'designer_name', 'designer_email',
            'created_at', 'updated_at', 'media_files', 'preview_files', 'tags', 'approval_history', 'analytics',
            'flagged', 'flag_reason', 'designer'
        ]
    
    def get_designer_name(self, obj):
        """Get designer name safely"""
        try:
            if obj.created_by:
                return obj.created_by.get_full_name() or f"{obj.created_by.first_name} {obj.created_by.last_name}".strip() or obj.created_by.username
            return None
        except Exception:
            return None
    
    def get_designer_email(self, obj):
        """Get designer email safely"""
        try:
            return obj.created_by.email if obj.created_by else None
        except Exception:
            return None
    
    def get_category_name(self, obj):
        """Get category name safely"""
        try:
            return obj.category.name if obj.category else None
        except Exception:
            return None
    
    def get_parent_category_name(self, obj):
        """Get parent category name if the category is a subcategory"""
        try:
            if obj.category and obj.category.parent:
                return obj.category.parent.name
            return None
        except Exception:
            return None
    
    def get_media_files(self, obj):
        """Get all media files with proper URLs"""
        try:
            media = get_related(obj, 'Product:Media', Media)
            request = self.context.get('request') if hasattr(self, 'context') and self.context else None
            result = []
            for m in media:
                try:
                    file_url = None
                    if m.file:
                        try:
                            url = m.file.url
                            # Build absolute URL if we have request context
                            if request and url:
                                if url.startswith('/'):
                                    file_url = request.build_absolute_uri(url)
                                elif url.startswith('http'):
                                    file_url = url
                                else:
                                    file_url = url
                            else:
                                file_url = url
                        except (ValueError, AttributeError):
                            file_url = None
                    
                    # Get file name to check extension
                    file_name = m.file.name if m.file else ''
                    file_name_lower = file_name.lower()
                    
                    # Get relation metadata if available
                    meta_data = None
                    is_mockup = False
                    try:
                        from MediaFiles.models import Relation
                        relation = Relation.objects.filter(
                            relation_type='Product:Media',
                            id_1=obj.pk,
                            id_2=m.pk
                        ).first()
                        if relation and relation.meta:
                            meta_data = relation.meta
                            # Check if metadata indicates this is a mockup
                            if isinstance(meta_data, dict):
                                is_mockup = meta_data.get('is_mockup', False) or meta_data.get('type') == 'mockup'
                            elif isinstance(meta_data, str):
                                meta_lower = meta_data.lower()
                                is_mockup = 'mockup' in meta_lower or '"is_mockup":true' in meta_lower
                    except Exception:
                        pass
                    
                    # Also check filename for mockup (exact match or _MOCKUP pattern)
                    if not is_mockup and file_name:
                        file_name_lower = file_name.lower()
                        base_name = os.path.splitext(os.path.basename(file_name_lower))[0]
                        # Check for exact match or _MOCKUP pattern (e.g., WDG00000005_MOCKUP.jpg)
                        if base_name == 'mockup' or base_name.endswith('_mockup') or '_mockup' in base_name:
                            is_mockup = True
                    
                    result.append({
                        'id': m.id,
                        'file': file_url,
                        'url': file_url,  # Alias for frontend compatibility
                        'media_type': m.media_type,
                        'file_name': file_name,
                        'created_at': m.created_at.isoformat() if m.created_at else None,
                        'meta': meta_data,  # Include metadata for file type detection
                        'is_mockup': is_mockup  # Explicit flag for mockup detection
                    })
                except Exception:
                    continue
            return result
        except Exception:
            return []
    
    def get_preview_files(self, obj):
        """Get only JPG, PNG, and mockup files for preview"""
        try:
            media = get_related(obj, 'Product:Media', Media)
            request = self.context.get('request') if hasattr(self, 'context') and self.context else None
            result = []
            
            for m in media:
                try:
                    if not m.file:
                        continue
                    
                    file_url = None
                    try:
                        url = m.file.url
                        # Build absolute URL if we have request context
                        if request and url:
                            if url.startswith('/'):
                                file_url = request.build_absolute_uri(url)
                            elif url.startswith('http'):
                                file_url = url
                            else:
                                file_url = url
                        else:
                            file_url = url
                    except (ValueError, AttributeError):
                        continue
                    
                    # Get file name and check if it's JPG, PNG, or mockup
                    file_name = m.file.name if m.file else ''
                    file_name_lower = file_name.lower()
                    
                    # Check if it's JPG or PNG
                    is_jpg_png = any(ext in file_name_lower for ext in ['.jpg', '.jpeg', '.png'])
                    
                    # Check if it's a mockup file (exact match or _MOCKUP pattern)
                    base_name = os.path.splitext(os.path.basename(file_name_lower))[0]
                    # Check for exact match or _MOCKUP pattern (e.g., WDG00000005_MOCKUP.jpg)
                    is_mockup = base_name == 'mockup' or base_name.endswith('_mockup') or '_mockup' in base_name
                    
                    # Also check metadata if available
                    try:
                        from MediaFiles.models import Relation
                        relation = Relation.objects.filter(
                            relation_type='Product:Media',
                            id_1=obj.pk,
                            id_2=m.pk
                        ).first()
                        if relation and relation.meta:
                            meta_lower = str(relation.meta).lower()
                            if 'mockup' in meta_lower:
                                is_mockup = True
                    except Exception:
                        pass
                    
                    # Only include JPG, PNG, or mockup files
                    if is_jpg_png or is_mockup:
                        result.append({
                            'id': m.id,
                            'file': file_url,
                            'url': file_url,
                            'media_type': m.media_type,
                            'file_name': file_name,
                            'is_mockup': is_mockup,
                            'created_at': m.created_at.isoformat() if m.created_at else None
                        })
                except Exception:
                    continue
            
            return result
        except Exception:
            return []
    
    def get_tags(self, obj):
        """Get associated tags"""
        try:
            tags = get_related(obj, 'Product:Tag', Tags)
            return [
                {
                    'id': tag.id,
                    'name': tag.name,
                    'tag_type': tag.tag_type
                } for tag in tags
            ]
        except Exception:
            return []
    
    def get_approval_history(self, obj):
        """Get approval history from DesignApproval"""
        try:
            from CoreAdmin.models import DesignApproval
            from common.relations import get_related
            
            approvals = get_related(obj, 'Product:DesignApproval', DesignApproval)
            history = []
            for approval in approvals.order_by('-created_at'):
                history.append({
                    'id': approval.id,
                    'action': approval.action,
                    'performed_by': approval.approved_by.get_full_name() if approval.approved_by else 'Unknown',
                    'remarks': approval.admin_notes or approval.rejection_reason or '',
                    'timestamp': approval.approved_at.isoformat() if approval.approved_at else approval.created_at.isoformat()
                })
            return history
        except Exception:
            return []
    
    def get_analytics(self, obj):
        """Get design analytics"""
        try:
            from CoreAdmin.models import DesignAnalytics
            from common.relations import get_related
            
            analytics = get_related(obj, 'Product:DesignAnalytics', DesignAnalytics)
            if analytics.exists():
                analytics_obj = analytics.first()
                return {
                    'total_views': analytics_obj.total_views,
                    'total_downloads': analytics_obj.total_downloads,
                    'total_purchases': analytics_obj.total_purchases,
                    'average_rating': analytics_obj.average_rating,
                    'revenue_generated': float(analytics_obj.total_revenue),
                    'trending_score': analytics_obj.trending_score
                }
            return {
                'total_views': 0,
                'total_downloads': 0,
                'total_purchases': 0,
                'average_rating': 0.0,
                'revenue_generated': 0.0,
                'trending_score': 0.0
            }
        except Exception:
            return {
                'total_views': 0,
                'total_downloads': 0,
                'total_purchases': 0,
                'average_rating': 0.0,
                'revenue_generated': 0.0,
                'trending_score': 0.0
            }
    
    def get_flagged(self, obj):
        """Get flag status from product_metadata"""
        try:
            if obj.product_metadata and isinstance(obj.product_metadata, dict):
                return obj.product_metadata.get('flagged', False)
            return False
        except Exception:
            return False
    
    def get_flag_reason(self, obj):
        """Get flag reason from product_metadata"""
        try:
            if obj.product_metadata and isinstance(obj.product_metadata, dict):
                return obj.product_metadata.get('flag_reason', None)
            return None
        except Exception:
            return None
    
    def get_designer(self, obj):
        """Get designer details"""
        try:
            if obj.created_by:
                from Profiles.models import DesignerProfile
                try:
                    designer_profile = DesignerProfile.objects.filter(created_by=obj.created_by).first()
                    return {
                        'id': obj.created_by.id,
                        'name': obj.created_by.get_full_name() or obj.created_by.username,
                        'email': obj.created_by.email,
                        'status': designer_profile.status if designer_profile else 'unknown',
                        'onboardingStatus': designer_profile.onboarding_status if designer_profile else None,
                        'lifetimeEarnings': float(designer_profile.lifetime_earnings) if designer_profile and hasattr(designer_profile, 'lifetime_earnings') else 0,
                        'pendingPayout': float(designer_profile.pending_payout) if designer_profile and hasattr(designer_profile, 'pending_payout') else 0
                    }
                except Exception:
                    return {
                        'id': obj.created_by.id,
                        'name': obj.created_by.get_full_name() or obj.created_by.username,
                        'email': obj.created_by.email,
                        'status': 'unknown',
                        'onboardingStatus': None,
                        'lifetimeEarnings': 0,
                        'pendingPayout': 0
                    }
            return None
        except Exception:
            return None


class BundleListSerializer(serializers.ModelSerializer):
    """
    Serializer for bundle list view.
    """
    designer_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    designer_email = serializers.CharField(source='created_by.email', read_only=True)
    plan_name = serializers.CharField(source='plan.get_plan_name_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    products_count = serializers.SerializerMethodField()
    total_views = serializers.SerializerMethodField()
    total_purchases = serializers.SerializerMethodField()
    revenue_generated = serializers.SerializerMethodField()
    
    class Meta:
        model = CollectionBundle
        fields = [
            'id', 'name', 'product_ids', 'plan', 'plan_name', 'status', 'status_display',
            'created_by', 'designer_name', 'designer_email', 'created_at', 'updated_at',
            'products_count', 'total_views', 'total_purchases', 'revenue_generated'
        ]
        read_only_fields = [
            'id', 'name', 'product_ids', 'plan', 'plan_name', 'status', 'status_display',
            'created_by', 'designer_name', 'designer_email', 'created_at', 'updated_at',
            'products_count', 'total_views', 'total_purchases', 'revenue_generated'
        ]
    
    def get_products_count(self, obj):
        """Get count of products in bundle"""
        if obj.product_ids:
            try:
                product_ids = [int(id) for id in obj.product_ids.split(',') if id.strip()]
                return len(product_ids)
            except (ValueError, TypeError):
                return 0
        return 0
    
    def get_total_views(self, obj):
        """Get total views count"""
        # TODO: Implement view tracking
        return 0
    
    def get_total_purchases(self, obj):
        """Get total purchases count"""
        # TODO: Implement purchase tracking
        return 0
    
    def get_revenue_generated(self, obj):
        """Get revenue generated from this bundle"""
        # TODO: Implement revenue tracking
        return 0.0


class BundleDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed bundle information.
    """
    designer_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    designer_email = serializers.CharField(source='created_by.email', read_only=True)
    plan_name = serializers.CharField(source='plan.get_plan_name_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    products = serializers.SerializerMethodField()
    analytics = serializers.SerializerMethodField()
    
    class Meta:
        model = CollectionBundle
        fields = [
            'id', 'name', 'product_ids', 'plan', 'plan_name', 'status', 'status_display',
            'created_by', 'designer_name', 'designer_email', 'created_at', 'updated_at',
            'products', 'analytics'
        ]
        read_only_fields = [
            'id', 'name', 'product_ids', 'plan', 'plan_name', 'status', 'status_display',
            'created_by', 'designer_name', 'designer_email', 'created_at', 'updated_at',
            'products', 'analytics'
        ]
    
    def get_products(self, obj):
        """Get products in bundle"""
        if obj.product_ids:
            try:
                product_ids = [int(id) for id in obj.product_ids.split(',') if id.strip()]
                products = Product.objects.filter(id__in=product_ids)
                return [
                    {
                        'id': p.id,
                        'title': p.title,
                        'status': p.status,
                        'price': float(p.price) if p.price else 0,
                        'created_at': p.created_at
                    } for p in products
                ]
            except (ValueError, TypeError):
                return []
        return []
    
    def get_analytics(self, obj):
        """Get bundle analytics"""
        # TODO: Implement analytics tracking
        return {
            'total_views': 0,
            'total_purchases': 0,
            'revenue_generated': 0.0,
            'trending_score': 0.0
        }


class DesignActionSerializer(serializers.Serializer):
    """
    Serializer for design approval/rejection/flag actions.
    """
    action = serializers.ChoiceField(choices=[
        ('approve', 'Approve Design'),
        ('reject', 'Reject Design'),
        ('disable', 'Disable Design'),
        ('flag', 'Flag Design'),
        ('resolve_flag', 'Resolve Flag')
    ])
    rejection_reason = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    reason = serializers.CharField(max_length=1000, required=False, allow_blank=True)  # For flag action
    admin_notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    
    def validate(self, data):
        action = data.get('action')
        rejection_reason = data.get('rejection_reason', '')
        reason = data.get('reason', '')
        
        if action == 'reject' and not rejection_reason.strip():
            raise serializers.ValidationError("Rejection reason is required when rejecting design.")
        
        if action == 'flag' and not reason.strip():
            raise serializers.ValidationError("Reason is required when flagging design.")
        
        return data


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for category management.
    """
    parent = serializers.StringRelatedField(read_only=True)
    parent_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    subcategories = serializers.SerializerMethodField()
    subcategories_count = serializers.SerializerMethodField()
    products_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'icon_name', 'parent', 'parent_id', 'parent_name', 'subcategories', 'created_by', 'created_at',
            'updated_by', 'updated_at', 'subcategories_count', 'products_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by', 'updated_by']
    
    def get_subcategories(self, obj):
        """
        Get subcategories for this category.
        """
        if not obj:
            return []
        
        try:
            # Access subcategories - prefetch_related should have loaded them
            if hasattr(obj, 'subcategories'):
                # Use prefetched subcategories if available
                subcategories = obj.subcategories.all()
                # Always return an array, even if empty
                result = CategoryListSerializer(subcategories, many=True).data
                return result if result is not None else []
            return []
        except Exception as e:
            # Log error but return empty array
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting subcategories for category {obj.id if obj else 'unknown'}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def get_subcategories_count(self, obj):
        """Get count of subcategories"""
        return obj.subcategories.count()
    
    def get_products_count(self, obj):
        """Get count of active and visible products in category and its subcategories"""
        from django.db.models import Q
        
        # Get all subcategory IDs (including nested subcategories)
        def get_all_subcategory_ids(category):
            subcategory_ids = [category.id]
            for subcat in category.subcategories.all():
                subcategory_ids.extend(get_all_subcategory_ids(subcat))
            return subcategory_ids
        
        # Get all category IDs (this category + all subcategories)
        all_category_ids = get_all_subcategory_ids(obj)
        
        # Count products in this category and all subcategories
        from .models import Product
        return Product.objects.filter(
            category_id__in=all_category_ids,
            status='active',
            visibility_status='show'
        ).count()
    
    def validate(self, attrs):
        """
        Override validate to ensure created_by is not validated as required.
        It will be set in create() method from context.
        """
        # Don't validate created_by here - it will be set in create()
        return attrs
    
    def create(self, validated_data):
        """
        Create a new category instance.
        If created_by is not in validated_data, it will be set from the context.
        """
        # Remove created_by_id if present (we'll use created_by from context)
        validated_data.pop('created_by_id', None)
        validated_data.pop('updated_by_id', None)
        
        # Get created_by from context if available - this is required for the model
        created_by = self.context.get('created_by')
        if not created_by:
            # If no created_by in context, try to get from request if available
            request = self.context.get('request')
            if request and hasattr(request, 'user'):
                created_by = request.user
        
        if not created_by:
            # This should not happen, but raise an error if it does
            raise serializers.ValidationError({
                'created_by': 'Created by user is required. Please ensure you are authenticated.'
            })
        
        # Create the category instance directly with created_by
        from .models import Category
        category = Category.objects.create(
            **validated_data,
            created_by=created_by
        )
        
        return category


class TagSerializer(serializers.ModelSerializer):
    """
    Serializer for tag management.
    """
    products_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Tags
        fields = [
            'id', 'name', 'tag_type', 'created_by', 'created_at',
            'updated_by', 'updated_at', 'products_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_products_count(self, obj):
        """Get count of products with this tag"""
        products = get_related(obj, 'Product:Tag', Product)
        return products.count()


class CopyrightReportSerializer(serializers.ModelSerializer):
    """
    Serializer for copyright violation reports.
    """
    reporter_name = serializers.CharField(source='user.get_full_name', read_only=True)
    reporter_email = serializers.CharField(source='user.email', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.get_full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    media_files = serializers.SerializerMethodField()
    
    class Meta:
        model = ReportIssue
        fields = [
            'id', 'user', 'reporter_name', 'reporter_email', 'title', 'description',
            'priority', 'priority_display', 'status', 'status_display', 'resolution',
            'resolved_by', 'resolved_by_name', 'resolved_at', 'created_by', 'created_by_name',
            'created_at', 'updated_at', 'media_files'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_media_files(self, obj):
        """Get media files attached to report"""
        media = get_related(obj, 'ReportIssue:Media', Media)
        return [
            {
                'id': m.id,
                'file': m.file.url if m.file else None,
                'media_type': m.media_type,
                'created_at': m.created_at
            } for m in media
        ]


class CopyrightReportActionSerializer(serializers.Serializer):
    """
    Serializer for copyright report actions.
    """
    action = serializers.ChoiceField(choices=[
        ('resolve', 'Resolve Report'),
        ('reject', 'Reject Report'),
        ('disable_design', 'Disable Design')
    ])
    resolution = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    admin_notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    
    def validate(self, data):
        action = data.get('action')
        resolution = data.get('resolution', '')
        
        if action in ['resolve', 'disable_design'] and not resolution.strip():
            raise serializers.ValidationError("Resolution is required when resolving or disabling design.")
        
        return data


class DesignAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for design analytics.
    """
    design_id = serializers.IntegerField()
    design_title = serializers.CharField()
    designer_name = serializers.CharField()
    category_name = serializers.CharField()
    status = serializers.CharField()
    total_views = serializers.IntegerField()
    total_downloads = serializers.IntegerField()
    total_purchases = serializers.IntegerField()
    average_rating = serializers.FloatField()
    revenue_generated = serializers.DecimalField(max_digits=10, decimal_places=2)
    trending_score = serializers.FloatField()
    created_at = serializers.DateTimeField()
    last_activity = serializers.DateTimeField()


class DesignAnalyticsFilterSerializer(serializers.Serializer):
    """
    Serializer for design analytics filtering.
    """
    designer_id = serializers.IntegerField(required=False)
    category_id = serializers.IntegerField(required=False)
    status = serializers.CharField(required=False)
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)
    sort_by = serializers.ChoiceField(choices=[
        ('total_views', 'Total Views'),
        ('total_downloads', 'Total Downloads'),
        ('total_purchases', 'Total Purchases'),
        ('revenue_generated', 'Revenue Generated'),
        ('trending_score', 'Trending Score'),
        ('created_at', 'Created Date')
    ], required=False)
    sort_order = serializers.ChoiceField(choices=[
        ('asc', 'Ascending'),
        ('desc', 'Descending')
    ], required=False)
    page = serializers.IntegerField(min_value=1, required=False)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False)


class DesignSearchSerializer(serializers.Serializer):
    """
    Serializer for design search functionality.
    """
    query = serializers.CharField(max_length=255)
    status = serializers.ChoiceField(choices=[
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('draft', 'Draft'),
        ('deleted', 'Deleted')
    ], required=False)
    category_id = serializers.IntegerField(required=False)
    designer_id = serializers.IntegerField(required=False)
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)
    sort_by = serializers.ChoiceField(choices=[
        ('created_at', 'Created Date'),
        ('updated_at', 'Updated Date'),
        ('title', 'Title'),
        ('price', 'Price')
    ], required=False)
    sort_order = serializers.ChoiceField(choices=[
        ('asc', 'Ascending'),
        ('desc', 'Descending')
    ], required=False)
    page = serializers.IntegerField(min_value=1, required=False)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False)
