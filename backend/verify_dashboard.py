#!/usr/bin/env python
"""
Dashboard Verification Script
Checks that all dashboard components are working correctly
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartclass.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from dashboard.models import Classroom, Student, Staff, Attendance
from django.utils import timezone

def check_dashboard():
    """Test dashboard endpoint and verify context variables"""
    print("=" * 70)
    print("SMART CLASSROOM DASHBOARD VERIFICATION")
    print("=" * 70)
    
    # Create test client
    client = Client()
    
    # Check database connection
    print("\n✓ Database Connection: OK")
    print(f"  - Classrooms: {Classroom.objects.count()}")
    print(f"  - Students: {Student.objects.count()}")
    print(f"  - Staff: {Staff.objects.count()}")
    print(f"  - Attendance Records: {Attendance.objects.count()}")
    
    # Test dashboard view
    print("\n✓ Testing Dashboard View...")
    try:
        response = client.get(reverse('dashboard'))
        print(f"  - Response Status: {response.status_code}")
        
        if response.status_code == 200:
            context = response.context
            
            # Verify required context variables
            required_vars = [
                'total_students',
                'total_staff',
                'total_classrooms',
                'total_attendance_today',
                'classroom_status',
                'danger_classrooms',
                'warning_classrooms',
                'has_warnings',
                'used_classrooms',
                'unused_classrooms',
                'avg_occupancy',
                'peak_hour_label',
                'peak_hour_sessions',
                'hourly_labels_json',
                'hourly_attendance_json',
                'weekly_labels_json',
                'weekly_attendance_json',
                'weekly_classrooms_json',
                'today',
            ]
            
            print("\n✓ Context Variables:")
            all_present = True
            for var in required_vars:
                if var in context:
                    print(f"  ✓ {var}")
                else:
                    print(f"  ✗ {var} - MISSING!")
                    all_present = False
            
            if all_present:
                print("\n✓ All required context variables present!")
            else:
                print("\n✗ Some context variables missing!")
                return False
            
            # Display sample data
            print("\n✓ Sample Data:")
            print(f"  - Students: {context['total_students']}")
            print(f"  - Staff: {context['total_staff']}")
            print(f"  - Classrooms: {context['total_classrooms']}")
            print(f"  - Today's Sessions: {context['total_attendance_today']}")
            print(f"  - Average Occupancy: {context['avg_occupancy']}%")
            print(f"  - Used Classrooms: {context['used_classrooms']}")
            print(f"  - Unused Classrooms: {context['unused_classrooms']}")
            print(f"  - Peak Hours: {context['peak_hour_label']} ({context['peak_hour_sessions']} sessions)")
            print(f"  - Date: {context['today']}")
            
            # Check for warnings/dangers
            if context['danger_classrooms']:
                print(f"\n⚠️  Danger Classrooms: {len(context['danger_classrooms'])}")
                for room in context['danger_classrooms']:
                    print(f"    - {room.name}")
            else:
                print("\n✓ No danger alerts")
            
            if context['warning_classrooms']:
                print(f"\n⚠️  Warning Classrooms: {len(context['warning_classrooms'])}")
                for room in context['warning_classrooms']:
                    print(f"    - {room.name} ({room.temperature}°C)")
            else:
                print("✓ No temperature warnings")
            
            return True
        else:
            print(f"  ✗ Unexpected status code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"  ✗ Error accessing dashboard: {str(e)}")
        return False


def check_template():
    """Verify template file exists and contains required elements"""
    print("\n" + "=" * 70)
    print("TEMPLATE VERIFICATION")
    print("=" * 70)
    
    template_path = 'dashboard/templates/dashboard.html'
    if os.path.exists(template_path):
        print(f"\n✓ Template file exists: {template_path}")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        required_elements = [
            'danger_classrooms',
            'warning_classrooms',
            'classroom_status',
            'hourlyActivityChart',
            'weeklyTrendChart',
            'ApexCharts',
        ]
        
        print("\n✓ Template Elements:")
        all_present = True
        for elem in required_elements:
            if elem in content:
                print(f"  ✓ {elem}")
            else:
                print(f"  ✗ {elem} - MISSING!")
                all_present = False
        
        if all_present:
            print("\n✓ All required template elements present!")
            return True
        else:
            print("\n✗ Some template elements missing!")
            return False
    else:
        print(f"\n✗ Template file not found: {template_path}")
        return False


def check_css():
    """Verify enhanced CSS is in place"""
    print("\n" + "=" * 70)
    print("CSS VERIFICATION")
    print("=" * 70)
    
    css_path = 'static/dashboard/css/demo.css'
    if os.path.exists(css_path):
        print(f"\n✓ CSS file exists: {css_path}")
        
        with open(css_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        required_styles = [
            'ENHANCED DASHBOARD STYLES',
            'alert-danger',
            'alert-warning',
            'classroom-status',
            'progress-bar',
            'pulse',
        ]
        
        print("\n✓ CSS Styles:")
        all_present = True
        for style in required_styles:
            if style in content:
                print(f"  ✓ {style}")
            else:
                print(f"  ✗ {style} - MISSING!")
                all_present = False
        
        if all_present:
            print("\n✓ All required CSS styles present!")
            return True
        else:
            print("\n✗ Some CSS styles missing!")
            return False
    else:
        print(f"\n✗ CSS file not found: {css_path}")
        return False


if __name__ == '__main__':
    results = {
        'Dashboard View': check_dashboard(),
        'Template': check_template(),
        'CSS Styles': check_css(),
    }
    
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    
    for check_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {check_name}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ ALL CHECKS PASSED - Dashboard is ready for production!")
    else:
        print("✗ SOME CHECKS FAILED - Please review the output above")
    print("=" * 70)
    
    sys.exit(0 if all_passed else 1)
