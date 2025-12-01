from django.urls import path
from . import views

urlpatterns = [
    # Dashboard and Summary
    path('dashboard/', views.dashboard_summary, name='dashboard_summary'),
    
    # Revenue Analytics
    path('revenue/', views.revenue_analytics, name='revenue_analytics'),
    
    # Top Performers
    path('top-designs/', views.top_designs_analytics, name='top_designs_analytics'),
    path('top-designers/', views.top_designers_analytics, name='top_designers_analytics'),
    
    # User Statistics
    path('user-stats/', views.user_statistics, name='user_statistics'),
    
    # Growth Charts
    path('growth-charts/', views.growth_charts, name='growth_charts'),
    
    # Export Reports
    path('export/', views.export_report, name='export_report'),
    path('export/<int:export_id>/status/', views.export_status, name='export_status'),
]
