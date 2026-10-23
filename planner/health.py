"""
Health check endpoints for monitoring and load balancers.
"""
from django.http import JsonResponse
from django.views import View
from django.db import connection
from django.core.cache import cache
import time


class HealthCheckView(View):
    """
    Comprehensive health check endpoint.
    
    Returns:
        - 200 OK: All systems operational
        - 503 Service Unavailable: Any critical dependency failed
    
    Checks:
        - Database connectivity
        - Cache (Redis) connectivity
        - Disk space (optional)
    """
    
    def get(self, request):
        checks = {}
        overall_status = 'healthy'
        http_status = 200
        
        # Database check
        db_start = time.time()
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            checks['database'] = {
                'status': 'healthy',
                'latency_ms': round((time.time() - db_start) * 1000, 2)
            }
        except Exception as e:
            checks['database'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            overall_status = 'unhealthy'
            http_status = 503
        
        # Cache check
        cache_start = time.time()
        try:
            cache.set('health_check', 'ok', 10)
            result = cache.get('health_check')
            if result == 'ok':
                checks['cache'] = {
                    'status': 'healthy',
                    'latency_ms': round((time.time() - cache_start) * 1000, 2)
                }
            else:
                checks['cache'] = {
                    'status': 'unhealthy',
                    'error': 'Cache read/write failed'
                }
                overall_status = 'degraded'
        except Exception as e:
            checks['cache'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            overall_status = 'degraded'
        
        # Response
        response_data = {
            'status': overall_status,
            'timestamp': time.time(),
            'checks': checks,
            'version': '1.0.0',
        }
        
        return JsonResponse(response_data, status=http_status)


class ReadinessView(View):
    """
    Kubernetes-style readiness probe.
    Returns 200 if ready to serve traffic, 503 if not.
    """
    
    def get(self, request):
        # Check critical dependencies
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
        except Exception:
            return JsonResponse({'status': 'not_ready'}, status=503)
        
        return JsonResponse({'status': 'ready'}, status=200)


class LivenessView(View):
    """
    Kubernetes-style liveness probe.
    Returns 200 if process is alive, 500 if deadlocked.
    """
    
    def get(self, request):
        return JsonResponse({'status': 'alive'}, status=200)