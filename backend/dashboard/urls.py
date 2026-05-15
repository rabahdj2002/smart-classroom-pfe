from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('personal-info/', views.personal_info, name='personal_info'),
    path('', views.dash, name='dashboard'),
    path('mqtt-docs/', views.mqtt_docs, name='mqtt_docs'),
    path('settings/', views.temperature_settings, name='temperature_settings'),
    path('classes/', views.classes, name='classes'),
    path('classes/add/', views.add_class, name='add_class'),
    path('classes/export/<str:export_format>/', views.export_classes, name='export_classes'),
    path('classes/restore/', views.restore_classes, name='restore_classes'),
    path('classes/bulk-delete/', views.bulk_delete_classes, name='bulk_delete_classes'),
    path('classes/<int:id>/', views.classroom_detail, name='classroom_detail'),
    path('classes/<int:id>/timetable/', views.classroom_timetable, name='classroom_timetable'),
    path('classes/<int:id>/command/', views.classroom_command, name='classroom_command'),
    path('sessions/', views.sessions, name='sessions'),
    path('sessions/add/', views.add_session, name='add_session'),
    path('sessions/export/<str:export_format>/', views.export_sessions, name='export_sessions'),
    path('sessions/restore/', views.restore_sessions, name='restore_sessions'),
    path('sessions/<int:id>/edit/', views.edit_session, name='edit_session'),
    path('sessions/<int:id>/end/', views.end_session, name='end_session'),
    path('sessions/<int:id>/delete/', views.delete_session, name='delete_session'),
    path('sessions/bulk-delete/', views.bulk_delete_sessions, name='bulk_delete_sessions'),
    path('sessions/<int:id>/', views.session_detail, name='session_detail'),
    path('attendance/reports/<int:id>/download/', views.download_report_pdf, name='download_report_pdf'),
    path('attendance/reports/<int:id>/email/', views.email_report, name='email_report'),
    path('students/', views.students, name='students'),
    path('students/add/', views.add_student, name='add_student'),
    path('students/export/<str:export_format>/', views.export_students, name='export_students'),
    path('students/restore/', views.restore_students, name='restore_students'),
    path('students/bulk-delete/', views.bulk_delete_students, name='bulk_delete_students'),
    path('students/<int:id>/', views.student_detail, name='student_detail'),
    path('staff/', views.staff, name='staff'),
    path('staff/add/', views.add_staff, name='add_staff'),
    path('staff/export/<str:export_format>/', views.export_staff, name='export_staff'),
    path('staff/restore/', views.restore_staff, name='restore_staff'),
    path('staff/bulk-delete/', views.bulk_delete_staff, name='bulk_delete_staff'),
    path('staff/<int:id>/edit/', views.edit_staff, name='edit_staff'),
    path('staff/<int:id>/delete/', views.delete_staff, name='delete_staff'),
]



urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)