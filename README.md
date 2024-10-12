# Consulta de RUC SUNAT - Scraping y API

## Descripción

Este proyecto es una API basada en **Flask** que permite consultar información de un RUC en la plataforma de la SUNAT mediante **scraping** con Selenium. La API responde con los datos obtenidos del RUC en el formato JSON, estructurado y ordenado de manera específica.

El objetivo es ofrecer una herramienta sencilla para obtener información detallada de contribuyentes peruanos utilizando su número de RUC.

## Características

- Scraping de datos en **SUNAT** utilizando **Selenium** en modo headless (sin interfaz gráfica).
- API basada en **Flask** para consultas de RUC.
- Almacenamiento en caché para optimizar consultas repetidas.
- Límite de solicitudes por minuto mediante **Flask Limiter**.
- Métricas de rendimiento expuestas mediante **Prometheus**.
- Uso de **OrderedDict** para mantener el orden deseado de los datos.

## Estructura del proyecto

```
.
├── app.py                 # Código principal de la API y lógica de scraping
├── requirements.txt       # Dependencias del proyecto
├── README.md              # Archivo de documentación del proyecto
└── venv/                  # Entorno virtual de Python (ignorar en producción)
```

## Requisitos del sistema

- **Python 3.8+**
- **Google Chrome** o **Mozilla Firefox**
- **Chromedriver** o **Geckodriver** instalado y en el PATH del sistema.

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/JoeApaza/Consulta_RUC.git
cd Consulta_RUC
```

### 2. Crear un entorno virtual

Es recomendable utilizar un entorno virtual para gestionar las dependencias del proyecto:

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scriptsctivate
```

### 3. Instalar las dependencias

Instala las dependencias necesarias listadas en el archivo `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 4. Configurar Geckodriver (para Firefox)

Asegúrate de tener **Geckodriver** instalado en tu sistema. Puedes descargarlo [aquí](https://github.com/mozilla/geckodriver/releases). Luego, agrega el **Geckodriver** a tu `PATH`:

```bash
# En Linux/Mac
export PATH=$PATH:/ruta/a/geckodriver

# En Windows (PowerShell)
$env:Path += ";C:\ruta\a\geckodriver"
```

### 5. Ejecutar la aplicación

Una vez que las dependencias estén instaladas y configuradas, puedes ejecutar la aplicación:

```bash
python app.py
```

La aplicación estará disponible en `http://127.0.0.1:5000`.

## Endpoints

### 1. Consultar un RUC

```http
GET /consultar_ruc?ruc={RUC}
```

**Parámetros**:

- `ruc`: El número de RUC a consultar. Debe ser un RUC válido de 11 dígitos.

**Ejemplo de solicitud**:

```bash
curl "http://127.0.0.1:5000/consultar_ruc?ruc=20106897914"
```

**Respuesta exitosa**:

```json
{
  "Número de RUC": "20106897914",
  "Razón Social": "ENTEL PERU S.A.",
  "Tipo Contribuyente": "SOCIEDAD ANONIMA",
  "Nombre Comercial": "ENTEL S.A.",
  "Fecha de Inscripción": "21/04/1993",
  "Fecha de Inicio de Actividades": "15/08/1988",
  "Estado del Contribuyente": "ACTIVO",
  "Condición del Contribuyente": "HABIDO",
  "Domicilio Fiscal": "AV. REPUBLICA DE COLOMBIA NRO. 791...",
  "Sistema Emisión de Comprobante": "MANUAL/MECANIZADO/COMPUTARIZADO",
  "Actividad Comercio Exterior": "EXPORTADOR",
  "Sistema Contabilidad": "MANUAL/COMPUTARIZADO",
  "Actividad Principal": "ACTIVIDADES DE TELECOMUNICACIONES INALÁMBRICAS"
}
```

### 2. Métricas de Prometheus

```http
GET /metrics
```

Este endpoint expone las métricas de rendimiento de la API en formato compatible con **Prometheus**.

## Cacheo

Para optimizar el rendimiento de la aplicación, se implementa un sistema de caché con un **Time To Live (TTL)** configurable. Cada consulta de RUC se almacena en el caché durante un tiempo definido (por defecto 300 segundos) para evitar consultas repetidas a la SUNAT.

## Límite de Solicitudes

Para evitar el abuso, la API tiene un límite de **60 solicitudes por minuto** por IP, configurable en el archivo de configuración. Si se supera este límite, la API devolverá un error de límite excedido.

## Monitorización con Prometheus

La API expone métricas que pueden ser recolectadas por **Prometheus**, como el número total de solicitudes y la latencia de las respuestas.

## Manejo de Errores

La API está diseñada para manejar los siguientes errores:

- **RUC no válido**: Si el número de RUC no tiene el formato correcto, se devuelve un error.
- **Error de scraping**: Si ocurre un error durante la consulta a la SUNAT, se captura y se devuelve un mensaje de error detallado.

## Ejemplo de Uso - Script de Consulta de RUCs

También puedes realizar consultas de varios RUCs utilizando el siguiente script:

```python
import requests
import pandas as pd

# Definir si estamos en el entorno local o de producción
entorno_local = True  # Cambia esto a False cuando quieras apuntar a la API en Render

# URL de la API que ya has desplegado en Render o en tu entorno local
if entorno_local:
    api_url = "http://127.0.0.1:5000/consultar_ruc"  # URL de la API en el entorno local
else:
    api_url = "https://consulta-ruc-87rm.onrender.com"  # URL de la API en Render

# Lista de RUCs que quieres consultar
lista_rucs = ["20106897914", "20467534026", "20467534026"]  # Reemplaza con los RUCs que desees consultar

# Inicializar una lista vacía para almacenar los resultados
resultados = []

# Iterar sobre la lista de RUCs y realizar la consulta para cada uno
for ruc in lista_rucs:
    # Parámetros de la solicitud GET
    params = {'ruc': ruc}

    try:
        # Realizar la solicitud GET a la API
        response = requests.get(api_url, params=params)

        # Verificar si la solicitud fue exitosa
        if response.status_code == 200:
            # Obtener los datos en formato JSON
            data = response.json()
            print(f"Datos del RUC {ruc}:")
            print(data)
            # Añadir los datos al listado de resultados
            resultados.append(data)
        else:
            print(f"Error en la consulta del RUC {ruc}. Código de estado: {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"Error al realizar la solicitud para el RUC {ruc}: {e}")

# Crear un DataFrame a partir de los resultados obtenidos
if resultados:
    df = pd.DataFrame(resultados)

    # Reorganizar las columnas en el orden deseado
    columnas_ordenadas = [
        "Número de RUC",
        "Razón Social",
        "Tipo Contribuyente",
        "Nombre Comercial",
        "Fecha de Inscripción",
        "Fecha de Inicio de Actividades",
        "Estado del Contribuyente",
        "Condición del Contribuyente",
        "Domicilio Fiscal",
        "Sistema Emisión de Comprobante",
        "Actividad Comercio Exterior",
        "Sistema Contabilidad",
        "Actividad Principal"
    ]

    # Asegurarse de que todas las columnas existen antes de reordenarlas
    df = df[columnas_ordenadas]

    # Mostrar el DataFrame reorganizado
    print("DataFrame con los resultados de los RUCs consultados en el orden correcto:")
    display(df)
else:
    print("No se encontraron resultados para los RUCs consultados.")
```

## Contacto

Si tienes alguna pregunta o sugerencia, siéntete libre de crear un [issue](https://github.com/JoeApaza/Consulta_RUC/issues) en el repositorio o contactarme directamente en:

- **Email**: joemapaza97@gmail.com
