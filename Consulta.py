import requests

# URL de la API (puede ser local o en producción, como Render)
url = "http://127.0.0.1:5000/consultar_ruc"  # Cambia esto por tu URL en Render si ya la tienes desplegada

# Parámetros de la solicitud (el RUC que quieres consultar)
params = {
    'ruc': '20467534026'  # Reemplaza con el número de RUC que deseas consultar
}

try:
    # Realiza la solicitud GET a la API
    response = requests.get(url, params=params)

    # Verifica si la respuesta es exitosa (código 200)
    if response.status_code == 200:
        # Muestra la respuesta en formato JSON
        data = response.json()
        print("Datos del RUC consultado:")
        print(data)
    else:
        print(f"Error en la consulta. Código de estado: {response.status_code}")

except requests.exceptions.RequestException as e:
    print(f"Error al realizar la solicitud: {e}")
