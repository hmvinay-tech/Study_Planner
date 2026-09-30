from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('complete/<int:pk>/', views.complete_topic, name='complete'),
    path('delete/<int:pk>/', views.delete_topic, name='delete'),
]
