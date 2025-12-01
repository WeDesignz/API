from django.contrib import admin
from django.utils.html import format_html
from common.admin import PaginatedAdminMixin
from .models import Category, Product, ProductCounter, CollectionBundle, Tags, PDFDownload


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """
    Admin interface for Category model.
    Manages product categories with hierarchical structure.
    """
    list_display = ['name', 'parent', 'created_by', 'created_at']
    list_filter = ['parent', 'created_at', 'updated_at']
    search_fields = ['name', 'parent__name', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']
    list_per_page = 25
    
    fieldsets = (
        ('Category Information', {
            'fields': ('name', 'parent', 'created_by')
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
        return super().get_queryset(request).select_related('parent', 'created_by', 'updated_by')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """
    Admin interface for Product model.
    Manages products with pricing, colors, and visibility settings.
    """
    list_display = ['id', 'title', 'category', 'status', 'product_plan_type', 'price', 'color', 'visibility_status', 'created_by', 'created_at']
    list_filter = ['status', 'product_plan_type', 'category', 'visibility_status', 'created_at', 'updated_at']
    search_fields = ['title', 'description', 'category__name', 'product_number', 'studio_design_number', 'color', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['status', 'product_plan_type', 'visibility_status']
    ordering = ['-created_at']
    list_per_page = 25
    filter_horizontal = []
    
    fieldsets = (
        ('Product Information', {
            'fields': ('title', 'description', 'category', 'status', 'product_plan_type', 'product_metadata')
        }),
        ('Product Details', {
            'fields': ('product_number', 'studio_design_number', 'color', 'price', 'visibility_status', 'rejection_reason')
        }),
        ('User Information', {
            'fields': ('created_by', 'updated_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category', 'created_by', 'updated_by')


@admin.register(ProductCounter)
class ProductCounterAdmin(admin.ModelAdmin):
    """
    Admin interface for ProductCounter model.
    Manages product interaction counters like views, purchases, and downloads.
    """
    list_display = ['product_counter_type', 'created_by', 'created_at']
    list_filter = ['product_counter_type', 'created_at']
    search_fields = ['created_by__username', 'created_by__email']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Counter Information', {
            'fields': ('product_counter_type', 'created_by')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by')


@admin.register(CollectionBundle)
class CollectionBundleAdmin(admin.ModelAdmin):
    """
    Admin interface for CollectionBundle model.
    Manages product collection bundles with plan associations.
    """
    list_display = ['name', 'plan', 'status', 'created_by', 'created_at']
    list_filter = ['status', 'plan', 'created_at', 'updated_at']
    search_fields = ['name', 'plan__plan_name', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['status']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Bundle Information', {
            'fields': ('name', 'product_ids', 'plan', 'status')
        }),
        ('User Information', {
            'fields': ('created_by', 'updated_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('plan', 'created_by', 'updated_by')


@admin.register(Tags)
class TagsAdmin(admin.ModelAdmin):
    """
    Admin interface for Tags model.
    Manages product tags with different types (AI-generated, metadata, manual).
    """
    list_display = ['name', 'tags_type', 'created_by', 'created_at']
    list_filter = ['tags_type', 'created_at', 'updated_at']
    search_fields = ['name', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['tags_type']
    ordering = ['name']
    list_per_page = 25
    
    fieldsets = (
        ('Tag Information', {
            'fields': ('name', 'tags_type', 'created_by')
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


@admin.register(PDFDownload)
class PDFDownloadAdmin(admin.ModelAdmin):
    """
    Admin interface for PDFDownload model.
    Manages PDF download requests with free and paid options.
    One user can have multiple PDF downloads.
    """
    list_display = ['get_user_display', 'download_type', 'status', 'total_pages', 'products_count', 'total_amount', 'payment_status', 'created_at']
    list_filter = ['download_type', 'status', 'payment_status', 'selection_type', 'created_at', 'completed_at']
    search_fields = ['pdf_file_path']
    readonly_fields = ['created_at', 'updated_at', 'completed_at', 'products_count']
    list_editable = ['status', 'payment_status']
    ordering = ['-created_at']
    list_per_page = 25
    
    def get_user_display(self, obj):
        """Display user information via relation system"""
        user = obj.get_user()
        return user.username if user else "No User"
    get_user_display.short_description = 'User'
    
    fieldsets = (
        ('Download Information', {
            'fields': ('download_type', 'status', 'total_pages', 'selection_type')
        }),
        ('PDF Configuration', {
            'fields': ('selected_products', 'search_filters', 'included_products', 'products_count')
        }),
        ('Pricing Information', {
            'fields': ('price_per_design', 'total_amount')
        }),
        ('Payment Information', {
            'fields': ('razorpay_payment', 'payment_status'),
            'classes': ('collapse',)
        }),
        ('File Information', {
            'fields': ('pdf_file_path', 'file_size'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('razorpay_payment')