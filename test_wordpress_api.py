"""
Script para explorar la API REST de WordPress y Booknetic
Detecta automáticamente los endpoints disponibles
"""
import os
import sys
import requests
from typing import Optional, Dict, Any, List
import json

# Agregar la raíz del proyecto al path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configuración
BASE_URL = os.getenv("BOOKNETIC_URL", "https://hotboatchile.com")
# Limpiar la URL si tiene /wp-login.php al final
if BASE_URL.endswith('/wp-login.php'):
    BASE_URL = BASE_URL.replace('/wp-login.php', '')
USERNAME = os.getenv("BOOKNETIC_USERNAME", "")
PASSWORD = os.getenv("BOOKNETIC_PASSWORD", "")

# WordPress REST API base
WP_API_BASE = f"{BASE_URL}/wp-json"


def discover_api_endpoints() -> Optional[Dict[str, Any]]:
    """
    Descubre todos los endpoints disponibles en la API REST de WordPress
    """
    print("=" * 60)
    print("🔍 DESCUBRIENDO ENDPOINTS DE API REST")
    print("=" * 60)
    print(f"🌐 URL Base: {WP_API_BASE}")
    print()
    
    try:
        # La ruta raíz de wp-json devuelve todos los endpoints disponibles
        response = requests.get(WP_API_BASE, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            print("✅ API REST de WordPress detectada")
            print()
            
            # Mostrar información general
            if 'name' in data:
                print(f"📝 Sitio: {data.get('name')}")
            if 'description' in data:
                print(f"📄 Descripción: {data.get('description')}")
            if 'url' in data:
                print(f"🌐 URL: {data.get('url')}")
            
            print()
            print("=" * 60)
            print("📚 NAMESPACES DISPONIBLES:")
            print("=" * 60)
            
            namespaces = data.get('namespaces', [])
            for ns in namespaces:
                print(f"  • {ns}")
                
                # Buscar si hay endpoints de Booknetic
                if 'booknetic' in ns.lower():
                    print(f"    ⭐ ¡BOOKNETIC ENCONTRADO!")
            
            print()
            print("=" * 60)
            print("🔗 ROUTES DISPONIBLES:")
            print("=" * 60)
            
            routes = data.get('routes', {})
            
            # Filtrar y mostrar rutas de Booknetic
            booknetic_routes = {k: v for k, v in routes.items() if 'booknetic' in k.lower()}
            
            if booknetic_routes:
                print("\n⭐ ENDPOINTS DE BOOKNETIC:")
                for route, info in booknetic_routes.items():
                    print(f"\n  📍 {route}")
                    if isinstance(info, dict):
                        methods = info.get('methods', [])
                        if methods:
                            print(f"     Métodos: {', '.join(methods)}")
            else:
                print("\n⚠️  No se encontraron endpoints específicos de Booknetic")
                print("    (Puede que requiera autenticación para verlos)")
            
            print()
            return data
            
        else:
            print(f"❌ Error: Status {response.status_code}")
            print(f"   Respuesta: {response.text[:200]}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_authenticated_access() -> None:
    """
    Prueba acceso autenticado usando Application Password
    """
    print("\n" + "=" * 60)
    print("🔐 PROBANDO ACCESO AUTENTICADO")
    print("=" * 60)
    
    if not USERNAME or not PASSWORD:
        print("⚠️  No hay credenciales configuradas")
        print("    Para usar Application Passwords:")
        print("    1. Ve a WordPress → Usuarios → Tu Perfil")
        print("    2. Sección 'Application Passwords'")
        print("    3. Crea un nuevo password para esta app")
        print("    4. Agrégalo a tu .env como BOOKNETIC_PASSWORD")
        return
    
    print(f"👤 Usuario: {USERNAME}")
    print()
    
    # Probar endpoint que requiere autenticación
    auth_url = f"{WP_API_BASE}/wp/v2/users/me"
    
    try:
        # Autenticación básica
        response = requests.get(
            auth_url,
            auth=(USERNAME, PASSWORD),
            timeout=30
        )
        
        if response.status_code == 200:
            user_data = response.json()
            print("✅ Autenticación exitosa!")
            print(f"   ID: {user_data.get('id')}")
            print(f"   Nombre: {user_data.get('name')}")
            print(f"   Email: {user_data.get('email')}")
            print(f"   Roles: {user_data.get('roles', [])}")
            print()
            
            # Ahora intentar acceder a endpoints de Booknetic si existen
            test_booknetic_endpoints(USERNAME, PASSWORD)
            
        elif response.status_code == 401:
            print("❌ Autenticación falló")
            print("   ¿Estás usando un Application Password?")
            print("   (No funciona con el password normal de WordPress)")
        else:
            print(f"❌ Error: Status {response.status_code}")
            print(f"   Respuesta: {response.text[:300]}")
            
    except Exception as e:
        print(f"❌ Error: {e}")


def test_booknetic_endpoints(username: str, password: str) -> None:
    """
    Intenta acceder a posibles endpoints de Booknetic
    """
    print("=" * 60)
    print("🎯 PROBANDO ENDPOINTS DE BOOKNETIC")
    print("=" * 60)
    
    # Posibles rutas de API que Booknetic podría usar
    possible_endpoints = [
        "/booknetic/v1/appointments",
        "/booknetic/v1/customers",
        "/booknetic/v1/payments",
        "/booknetic/appointments",
        "/booknetic/customers",
        "/booknetic/payments",
        "/bkntc/v1/appointments",
        "/bkntc/v1/customers",
        "/bkntc/v1/payments",
    ]
    
    for endpoint in possible_endpoints:
        url = f"{WP_API_BASE}{endpoint}"
        
        try:
            response = requests.get(
                url,
                auth=(username, password),
                timeout=15
            )
            
            if response.status_code == 200:
                print(f"\n✅ ENCONTRADO: {endpoint}")
                data = response.json()
                if isinstance(data, list):
                    print(f"   Registros: {len(data)}")
                    if data:
                        print(f"   Ejemplo: {json.dumps(data[0], indent=2)[:200]}...")
                else:
                    print(f"   Respuesta: {str(data)[:200]}")
            elif response.status_code == 404:
                print(f"❌ {endpoint} - No existe")
            elif response.status_code == 401:
                print(f"🔒 {endpoint} - Requiere permisos")
            else:
                print(f"⚠️  {endpoint} - Status {response.status_code}")
                
        except Exception as e:
            print(f"❌ {endpoint} - Error: {e}")


def check_custom_endpoints() -> None:
    """
    Intenta acceder a la interfaz de administración de Booknetic
    """
    print("\n" + "=" * 60)
    print("🔧 VERIFICANDO INTERFAZ DE ADMIN")
    print("=" * 60)
    
    # URL típica del admin de Booknetic
    admin_url = f"{BASE_URL}/wp-admin/admin.php?page=booknetic"
    
    print(f"📍 URL Admin: {admin_url}")
    print()
    print("💡 ALTERNATIVA: Usar la interfaz de exportación existente")
    print("   El método actual (scraping de CSVs) funciona porque:")
    print("   - Booknetic ya tiene exportación CSV nativa")
    print("   - No requiere API REST adicional")
    print("   - Es compatible con Railway")
    print()


def main():
    """Main function"""
    print("\n" + "=" * 60)
    print("🚀 EXPLORADOR DE API REST DE WORDPRESS + BOOKNETIC")
    print("=" * 60)
    print()
    
    # 1. Descubrir endpoints públicos
    discover_api_endpoints()
    
    # 2. Probar acceso autenticado
    test_authenticated_access()
    
    # 3. Verificar alternativas
    check_custom_endpoints()
    
    print("\n" + "=" * 60)
    print("📋 RECOMENDACIONES")
    print("=" * 60)
    print()
    print("1. Si Booknetic NO expone API REST:")
    print("   → Continuar con el método de exportación CSV (actual)")
    print("   → Es confiable y funciona en Railway")
    print()
    print("2. Si Booknetic SÍ expone API REST:")
    print("   → Implementar cliente REST API (mucho más rápido)")
    print("   → Usar Application Passwords para auth")
    print()
    print("3. Alternativa: Consultar directo a la base de datos")
    print("   → Si tienes acceso a la BD de WordPress")
    print("   → Más directo pero requiere conocer estructura")
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()

