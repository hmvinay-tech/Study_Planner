from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', RedirectView.as_view(pattern_name='home', permanent=False)),
    path('complete/<int:pk>/', views.complete_topic, name='complete'),
    path('edit/<int:pk>/', views.edit_topic, name='edit_topic'),
    path('delete/<int:pk>/', views.delete_topic, name='delete'),
    path('tags/', views.tag_list, name='tag_list'),
    path('tags/delete/<int:pk>/', views.delete_tag, name='delete_tag'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Study Sessions
    path('sessions/', views.session_list, name='session_list'),
    path('sessions/stop/<int:pk>/', views.stop_session, name='stop_session'),
    path('sessions/<int:pk>/', views.session_detail, name='session_detail'),

    # Notifications
    path('notifications/', views.notification_settings, name='notification_settings'),

    # Recurring Topics
    path('recurring/', views.recurring_list, name='recurring_list'),
    path('recurring/toggle/<int:pk>/', views.toggle_recurring, name='toggle_recurring'),
    path('recurring/delete/<int:pk>/', views.delete_recurring, name='delete_recurring'),
    path('recurring/generate/<int:pk>/', views.generate_recurring, name='generate_recurring'),

    # Topic Templates
    path('templates/', views.template_list, name='template_list'),
    path('templates/delete/<int:pk>/', views.delete_template, name='delete_template'),
    path('templates/create/<int:pk>/', views.create_from_template, name='create_from_template'),
]
