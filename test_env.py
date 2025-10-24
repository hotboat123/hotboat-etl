import os

print("=" * 60)
print("TEST DE VARIABLES DE ENTORNO")
print("=" * 60)

# Configurar variables
os.environ["BOOKNETIC_USERNAME"] = "hotboatvillarrica@gmail.com"
os.environ["BOOKNETIC_PASSWORD"] = "Hotboat777"

print(f"Variable configurada: {os.environ.get('BOOKNETIC_USERNAME')}")
print(f"Variable password: {os.environ.get('BOOKNETIC_PASSWORD')}")

# Ahora probar os.getenv
username = os.getenv("BOOKNETIC_USERNAME", "default_user")
password = os.getenv("BOOKNETIC_PASSWORD", "default_pass")

print(f"\nUsando os.getenv:")
print(f"Username: {username}")
print(f"Password: {password}")

