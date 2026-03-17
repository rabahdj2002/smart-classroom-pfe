from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.dash, name='dashboard'),
    path('classes/', views.classes, name='classes'),
    path('classes/add/', views.add_class, name='add_class'),
    path('classes/<int:id>/', views.classroom_detail, name='classroom_detail'),
    path('students/', views.students, name='students'),
    path('students/add/', views.add_student, name='add_student'),
    path('students/<int:id>/', views.student_detail, name='student_detail'),
]



urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)