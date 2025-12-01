from django.urls import path
from . import views

urlpatterns = [
    # Plans
    path('plans/', views.plans_list, name='plans_list'),
    path('plans/<int:plan_id>/', views.plan_detail, name='plan_detail'),
    path('plans/compare/', views.plan_comparison, name='plan_comparison'),
    
    # Subscriptions
    path('subscription/', views.my_subscription, name='my_subscription'),
    path('subscription/subscribe/', views.subscribe_to_plan, name='subscribe_to_plan'),
    path('subscription/cancel/', views.cancel_subscription, name='cancel_subscription'),
    path('subscription/update/', views.update_subscription, name='update_subscription'),
    path('subscription/history/', views.subscription_history, name='subscription_history'),
    path('subscription/benefits/', views.subscription_benefits, name='subscription_benefits'),
    path('subscription/usage/', views.subscription_usage, name='subscription_usage'),
    path('subscription/expiry/', views.subscription_expiry, name='subscription_expiry'),
]
