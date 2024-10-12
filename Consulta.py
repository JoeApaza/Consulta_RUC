import requests

# URL de la API que ya has desplegado en Render
api_url = "https://consulta-ruc-87rm.onrender.com/consultar_ruc"

# Número de RUC que quieres consultar
ruc = "20467534026"  # Reemplaza este valor por el RUC que quieras consultar

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
