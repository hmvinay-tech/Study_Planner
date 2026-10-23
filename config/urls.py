"""
Root URL configuration for Study Planner.
"""
from django.urls import include, path
from django.contrib import admin
from planner.health import HealthCheckView, ReadinessView, LivenessView

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Health checks (for load balancers, Kubernetes)
    path('health/', HealthCheckView.as_view(), name='health'),
    path('health/ready/', ReadinessView.as_view(), name='health_ready'),
    path('health/live/', LivenessView.as_view(), name='health_live'),
    
    # Main application
    path('', include('planner.urls')),
    
    # API
    path('api/', include('planner.api_urls')),
]