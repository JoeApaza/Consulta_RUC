import requests

# Definir si estamos en el entorno local o de producción
entorno_local = True  # Cambia esto a False cuando quieras apuntar a la API en Render

# URL de la API que ya has desplegado en Render o en tu entorno local
if entorno_local:
    api_url = "http://127.0.0.1:5000/consultar_ruc"  # URL de la API en el entorno local
else:
    #api_url = "https://consulta-ruc-87rm.onrender.com"  # URL de la API en Render
    print("")
# Número de RUC que quieres consultar
ruc = "20100039207"  # Reemplaza este valor por el RUC que quieras consultar

# Parámetros de la solicitud GET
params = {
    'ruc': ruc
}

try:
    # Realizar la solicitud GET a la API
    response = requests.get(api_url, params=params)

    # Verificar si la solicitud fue exitosa
    if response.status_code == 200:
        # Mostrar los datos de la API en formato JSON
        data = response.json()
        print("Datos del RUC consultado:")
        print(data)
    else:
        print(f"Error en la consulta. Código de estado: {response.status_code}")

except requests.exceptions.RequestException as e:
    print(f"Error al realizar la solicitud: {e}")
