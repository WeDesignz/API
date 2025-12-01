from django.contrib import admin
from .models import CustomOrderRequest


@admin.register(CustomOrderRequest)
class CustomOrderRequestAdmin(admin.ModelAdmin):
    """
    Admin interface for CustomOrderRequest model.
    Manages custom design requests from customers.
    """
    list_display = ['title', 'status', 'budget', 'created_by', 'created_at']
    list_filter = ['status', 'created_at', 'updated_at']
    search_fields = ['title', 'description', 'created_by__username', 'created_by__email']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['status']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Request Information', {
            'fields': ('title', 'description', 'status', 'budget')
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