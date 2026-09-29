"""Frontend routes for the maintenance MVP."""

from django.urls import path

from apps.maintenance import views

app_name = 'maintenance'

urlpatterns = [
    path('', views.maintenance_dashboard_view, name='maintenance-dashboard'),
    path('work-to-do/', views.maintenance_work_to_do_view, name='maintenance-work-to-do'),
    path('work-orders/new/', views.maintenance_work_order_new_view, name='maintenance-work-order-new'),
    path('planned/', views.maintenance_planned_view, name='maintenance-planned'),
    path('planned/calendar/', views.maintenance_calendar_preview_view, name='maintenance-calendar-preview'),
    path('rooms/', views.maintenance_rooms_view, name='maintenance-rooms'),
]
