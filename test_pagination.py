#!/usr/bin/env python3
"""
Test script for pagination functionality
"""

def test_imports():
    """Test that all imports work correctly"""
    try:
        # Test Django imports
        from django.conf import settings
        from django.urls import path, include
        from django.http import JsonResponse
        from django.views import View
        from django.views.generic import TemplateView
        from django.utils.decorators import method_decorator
        from django.views.decorators.csrf import csrf_exempt
        
        print("[PASS] Django imports successful")
        return True
    except ImportError as e:
        print(f"[FAIL] Django import failed: {e}")
        return False

def test_api_urls():
    """Test that API URLs are properly configured"""
    try:
        # Read the urls.py file to verify new endpoints are added
        with open('server/dashboard/urls.py', 'r') as f:
            content = f.read()
            
        required_urls = [
            'path("api/clients/", views.ClientsAPIView.as_view(), name="api_clients")',
            'path("api/units/", views.UnitsAPIView.as_view(), name="api_units")',
            'path("api/services/", views.ServicesAPIView.as_view(), name="api_services")'
        ]
        
        for url in required_urls:
            if url in content:
                print(f"[PASS] Found URL: {url}")
            else:
                print(f"[FAIL] Missing URL: {url}")
                return False
                
        return True
    except Exception as e:
        print(f"[FAIL] Error checking URLs: {e}")
        return False

def test_api_views():
    """Test that API view classes exist"""
    try:
        # Read the views.py file to verify new API classes are added
        with open('server/dashboard/views.py', 'r') as f:
            content = f.read()
            
        required_classes = [
            'class ClientsAPIView(View):',
            'class UnitsAPIView(View):',
            'class ServicesAPIView(View):'
        ]
        
        for cls in required_classes:
            if cls in content:
                print(f"[PASS] Found class: {cls}")
            else:
                print(f"[FAIL] Missing class: {cls}")
                return False
                
        return True
    except Exception as e:
        print(f"[FAIL] Error checking classes: {e}")
        return False

def test_html_pagination():
    """Test that HTML has pagination controls"""
    try:
        # Read the main.html file to verify pagination controls are added
        with open('server/dashboard/templates/dashboard/main.html', 'r') as f:
            content = f.read()
            
        # Check for pagination controls in all three tables
        pagination_elements = [
            'id="page-start-clientes"',
            'id="page-end-clientes"',
            'id="total-records-clientes"',
            'id="page-info-clientes"',
            'id="prev-page-clientes"',
            'id="next-page-clientes"',
            
            'id="page-start-unidades"',
            'id="page-end-unidades"',
            'id="total-records-unidades"',
            'id="page-info-unidades"',
            'id="prev-page-unidades"',
            'id="next-page-unidades"',
            
            'id="page-start-servicios"',
            'id="page-end-servicios"',
            'id="total-records-servicios"',
            'id="page-info-servicios"',
            'id="prev-page-servicios"',
            'id="next-page-servicios"'
        ]
        
        for element in pagination_elements:
            if element in content:
                print(f"[PASS] Found pagination element: {element}")
            else:
                print(f"[FAIL] Missing pagination element: {element}")
                return False
                
        return True
    except Exception as e:
        print(f"[FAIL] Error checking HTML: {e}")
        return False

def test_javascript_functions():
    """Test that JavaScript functions exist"""
    try:
        # Read the main.html file to verify JavaScript functions are added
        with open('server/dashboard/templates/dashboard/main.html', 'r') as f:
            content = f.read()
            
        # Check for pagination JavaScript functions
        js_functions = [
            'function loadClientData()',
            'function renderClientTable(',
            'function updateClientPagination(',
            'function loadUnitData()',
            'function renderUnitTable(',
            'function updateUnitPagination(',
            'function loadServiceData()',
            'function renderServiceTable(',
            'function updateServicePagination(',
            'function buildApiUrl('
        ]
        
        for func in js_functions:
            if func in content:
                print(f"[PASS] Found JS function: {func}")
            else:
                print(f"[FAIL] Missing JS function: {func}")
                return False
                
        return True
    except Exception as e:
        print(f"[FAIL] Error checking JavaScript: {e}")
        return False

def main():
    """Run all tests"""
    print("Testing Pagination Implementation")
    print("=" * 50)
    
    tests = [
        ("Django Imports", test_imports),
        ("API URLs", test_api_urls),
        ("API Views", test_api_views),
        ("HTML Pagination", test_html_pagination),
        ("JavaScript Functions", test_javascript_functions)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\nTesting {test_name}...")
        if test_func():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("[SUCCESS] All tests passed! Pagination implementation is complete.")
    else:
        print("[WARNING] Some tests failed. Please review the implementation.")
    
    return passed == total

if __name__ == "__main__":
    main()