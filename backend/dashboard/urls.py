from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('personal-info/', views.personal_info, name='personal_info'),
    path('', views.dash, name='dashboard'),
    path('settings/', views.temperature_settings, name='temperature_settings'),
    path('classes/', views.classes, name='classes'),
    path('classes/add/', views.add_class, name='add_class'),
    path('classes/<int:id>/', views.classroom_detail, name='classroom_detail'),
    path('students/', views.students, name='students'),
    path('students/add/', views.add_student, name='add_student'),
    path('students/<int:id>/', views.student_detail, name='student_detail'),
    path('staff/', views.staff, name='staff'),
    path('staff/add/', views.add_staff, name='add_staff'),
    path('staff/<int:id>/edit/', views.edit_staff, name='edit_staff'),
    path('staff/<int:id>/delete/', views.delete_staff, name='delete_staff'),
]



urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)