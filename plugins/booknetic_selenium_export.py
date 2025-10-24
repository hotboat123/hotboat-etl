"""
Plugin booknetic_selenium_export.py
ACTUALIZADO para usar REQUESTS en lugar de Selenium
Mucho más rápido y confiable para Railway
"""
from typing import Any, Dict

def fetch() -> Dict[str, Any]:
    """
    Fetch all Booknetic data using requests (no Selenium)
    Returns: dict with lists of customers, appointments, payments
    """
    try:
        # Usar la versión optimizada con requests
        from jobs.booknetic_export_requests import fetch as export_fetch
        
        print("[booknetic_selenium_export] ACTUALIZADO: Usando REQUESTS (rápido)")
        result = export_fetch()
        
        print(f"[booknetic_selenium_export] Completado: {len(result.get('customers', []))} customers, {len(result.get('appointments', []))} appointments, {len(result.get('payments', []))} payments")
        return result
        
    except Exception as e:
        print(f"[booknetic_selenium_export] Error: {e}")
        import traceback
        traceback.print_exc()
        return {"customers": [], "appointments": [], "payments": []}
