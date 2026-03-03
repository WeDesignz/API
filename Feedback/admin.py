from django.contrib import admin
from .models import FeedbackQuestion, FeedbackReview, ReportIssue, SupportThread, SupportMessage, FAQ, FAQTag


@admin.register(FeedbackQuestion)
class FeedbackQuestionAdmin(admin.ModelAdmin):
    """
    Admin interface for FeedbackQuestion model.
    Manages feedback questions for different user types.
    """
    list_display = ['question', 'feedback_question_type', 'status', 'for_whom', 'created_by', 'created_at']
    list_filter = ['feedback_question_type', 'status', 'for_whom', 'created_at', 'updated_at']
    search_fields = ['question', 'created_by__username', 'created_by__email']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['status']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Question Information', {
            'fields': ('question', 'feedback_question_type', 'status', 'for_whom')
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
        return super().get_queryset(request).select_related('created_by', 'updated_by')


@admin.register(FeedbackReview)
class FeedbackReviewAdmin(admin.ModelAdmin):
    """
    Admin interface for FeedbackReview model.
    Manages feedback reviews and ratings from users.
    """
    list_display = ['feedback_question', 'rating', 'created_by', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['feedback_question__question', 'created_by__username', 'created_by__email', 'review']
    readonly_fields = ['created_at']
    list_editable = ['rating']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Review Information', {
            'fields': ('feedback_question', 'review', 'rating')
        }),
        ('User Information', {
            'fields': ('created_by',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('feedback_question', 'created_by')


@admin.register(ReportIssue)
class ReportIssueAdmin(admin.ModelAdmin):
    """
    Admin interface for ReportIssue model.
    Manages issue reports and their resolution status.
    """
    list_display = ['title', 'user', 'priority', 'status', 'resolved_by', 'created_at']
    list_filter = ['priority', 'status', 'created_at', 'updated_at', 'resolved_at']
    search_fields = ['title', 'description', 'user__username', 'user__email', 'resolution']
    readonly_fields = ['created_at', 'updated_at', 'resolved_at']
    list_editable = ['priority', 'status']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Issue Information', {
            'fields': ('user', 'title', 'description', 'priority', 'status')
        }),
        ('Resolution', {
            'fields': ('resolution', 'resolved_by', 'resolved_at'),
            'classes': ('collapse',)
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
        return super().get_queryset(request).select_related('user', 'resolved_by', 'created_by', 'updated_by')


class SupportMessageInline(admin.TabularInline):
    """Inline admin for SupportMessage."""
    model = SupportMessage
    extra = 0
    readonly_fields = ['sender', 'created_at', 'read_at', 'read_by']
    fields = ['sender', 'message', 'created_at', 'read_at', 'read_by']
    ordering = ['created_at']
    can_delete = False


@admin.register(SupportThread)
class SupportThreadAdmin(admin.ModelAdmin):
    """
    Admin interface for SupportThread model.
    Manages support tickets and threads.
    """
    list_display = ['id', 'subject', 'category', 'priority', 'status', 'created_by', 'assigned_to', 'created_at', 'updated_at']
    list_filter = ['status', 'priority', 'category', 'created_at', 'updated_at']
    search_fields = ['subject', 'created_by__username', 'created_by__email', 'assigned_to__username']
    readonly_fields = ['created_at', 'updated_at', 'resolved_at']
    list_editable = ['status', 'priority', 'assigned_to']
    ordering = ['-updated_at', '-created_at']
    list_per_page = 25
    inlines = [SupportMessageInline]
    
    fieldsets = (
        ('Thread Information', {
            'fields': ('subject', 'category', 'thread_type', 'priority', 'status')
        }),
        ('Assignment', {
            'fields': ('created_by', 'assigned_to')
        }),
        ('Resolution', {
            'fields': ('resolution', 'resolved_by', 'resolved_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by', 'assigned_to', 'resolved_by').prefetch_related('messages__sender')
    
    def get_fieldsets(self, request, obj=None):
        """Customize fieldsets based on object state."""
        fieldsets = super().get_fieldsets(request, obj)
        if obj and obj.status in ['resolved', 'closed']:
            # Show resolution fields expanded when resolved
            return (
                fieldsets[0],  # Thread Information
                fieldsets[1],  # Assignment
                ('Resolution', {
                    'fields': ('resolution', 'resolved_by', 'resolved_at')
                }),
                fieldsets[3],  # Timestamps
            )
        return fieldsets


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    """
    Admin interface for SupportMessage model.
    Manages individual messages within support threads.
    """
    list_display = ['id', 'thread', 'sender', 'message_preview', 'read_at', 'created_at']
    list_filter = ['read_at', 'created_at', 'thread__status']
    search_fields = ['message', 'thread__subject', 'sender__username', 'sender__email']
    readonly_fields = ['created_at', 'updated_at', 'read_at', 'read_by']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Message Information', {
            'fields': ('thread', 'sender', 'message')
        }),
        ('Read Status', {
            'fields': ('read_at', 'read_by'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('thread', 'sender', 'read_by')
    
    def message_preview(self, obj):
        """Show preview of message."""
        if len(obj.message) > 100:
            return obj.message[:100] + '...'
        return obj.message
    message_preview.short_description = 'Message'


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    """
    Admin interface for FAQ model.
    Manages frequently asked questions.
    """
    list_display = ['question', 'display_locations_display', 'tags_display', 'is_active', 'view_count', 'sort_order', 'created_by', 'created_at']
    list_filter = ['is_active', 'created_at', 'updated_at']
    search_fields = ['question', 'answer', 'slug', 'created_by__username', 'created_by__email']
    readonly_fields = ['slug', 'view_count', 'created_at', 'updated_at', 'tags_display']
    list_editable = ['is_active', 'sort_order']
    ordering = ['sort_order', 'id']
    list_per_page = 25
    
    fieldsets = (
        ('FAQ Information', {
            'fields': ('question', 'answer', 'slug', 'is_active', 'sort_order', 'view_count')
        }),
        ('Display Settings', {
            'fields': ('display_locations',),
            'description': 'Select where this FAQ should be displayed. Options: landing_page, customer_dashboard, designer_console, all'
        }),
        ('Tags', {
            'fields': ('tags_display',),
            'classes': ('collapse',),
            'description': 'Tags are managed through FAQ Tags. Use the FAQ Tags admin to assign tags to FAQs.'
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
        return super().get_queryset(request).select_related('created_by', 'updated_by').prefetch_related('tags')
    
    def display_locations_display(self, obj):
        """Display display_locations as a readable string."""
        if not obj.display_locations:
            return 'None'
        locations = obj.display_locations
        if isinstance(locations, list):
            if 'all' in locations:
                return 'All Locations'
            return ', '.join(location.replace('_', ' ').title() for location in locations)
        return str(locations)
    display_locations_display.short_description = 'Display Locations'
    
    def tags_display(self, obj):
        """Display tags as a readable string."""
        tags = obj.tags.all()
        if not tags:
            return 'No tags'
        return ', '.join(tag.name for tag in tags)
    tags_display.short_description = 'Tags'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(FAQTag)
class FAQTagAdmin(admin.ModelAdmin):
    """
    Admin interface for FAQTag model.
    Manages tags for FAQs.
    """
    list_display = ['name', 'faqs_count', 'created_by', 'created_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['name', 'created_by__username', 'created_by__email']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']
    list_per_page = 25
    
    fieldsets = (
        ('Tag Information', {
            'fields': ('name',)
        }),
        ('FAQs', {
            'fields': ('faqs',),
            'classes': ('collapse',)
        }),
        ('User Information', {
            'fields': ('created_by', 'updated_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    filter_horizontal = ['faqs']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by', 'updated_by').prefetch_related('faqs')
    
    def faqs_count(self, obj):
        """Show count of FAQs with this tag."""
        return obj.faqs.count()
    faqs_count.short_description = 'FAQs Count'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)