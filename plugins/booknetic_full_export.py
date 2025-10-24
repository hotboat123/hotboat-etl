"""
Plugin para exportar datos completos de Booknetic (customers, appointments, payments)
USANDO REQUESTS - Mucho más rápido y confiable que Selenium
Compatible con Railway
"""
from typing import Any, Dict

def fetch() -> Dict[str, Any]:
    """
    Fetch all Booknetic data using requests (no Selenium)
    Returns: dict with counts of customers, appointments, payments
    """
    try:
        from jobs.booknetic_export_requests import fetch as export_fetch
        
        print("[booknetic_full_export] Usando versión REQUESTS (rápida y confiable)")
        result = export_fetch()
        
        print(f"[booknetic_full_export] Completado: {result}")
        return result
        
    except Exception as e:
        print(f"[booknetic_full_export] Error: {e}")
        import traceback
        traceback.print_exc()
        return {"customers": 0, "appointments": 0, "payments": 0}
