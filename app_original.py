import logging
import os
import re
import sys
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any

from bs4 import BeautifulSoup
from flask import Flask, jsonify, request, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

app = Flask(__name__)

# Configuración básica del logging
if os.getenv('FLASK_ENV') == 'production':
    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
else:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
logger = logging.getLogger(__name__)

# Limitar el número de solicitudes por IP para seguridad adicional
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["60 per minute"]  # Ajusta el límite según tus necesidades
)

# Monitoreo con Prometheus
REQUEST_COUNT = Counter(
    'request_count',
    'Total de solicitudes al endpoint',
    ['endpoint', 'method', 'status']
)
REQUEST_LATENCY = Histogram(
    'request_latency_seconds',
    'Latencia de las solicitudes al endpoint',
    ['endpoint']
)

# Definir un semáforo para limitar el número de sesiones simultáneas de Selenium
MAX_CONCURRENT_REQUESTS = int(os.getenv('MAX_CONCURRENT_REQUESTS', '5'))
semaforo = threading.Semaphore(MAX_CONCURRENT_REQUESTS)

# Implementación de un caché simple con TTL (Time To Live)
CACHE_TTL = int(os.getenv('CACHE_TTL', '300'))  # Tiempo en segundos que un resultado permanece en caché
MAX_CACHE_SIZE = int(os.getenv('MAX_CACHE_SIZE', '1000'))  # Tamaño máximo del caché
cache_ruc = {}
cache_lock = threading.Lock()  # Para asegurar el acceso seguro al caché en entornos concurrentes

def limpiar_cache():
    """Limpia las entradas expiradas del caché periódicamente."""
    while True:
        time.sleep(CACHE_TTL)
        with cache_lock:
            keys_a_eliminar = [key for key, value in cache_ruc.items()
                               if datetime.now() - value['timestamp'] > timedelta(seconds=CACHE_TTL)]
            for key in keys_a_eliminar:
                del cache_ruc[key]
                logger.info(f"Entrada de caché eliminada para el RUC: {key}")

def configurar_driver() -> webdriver.Firefox:
    """
    Configura y devuelve una instancia de WebDriver para Firefox en modo headless.

    Returns:
        webdriver.Firefox: Instancia configurada del WebDriver.
    """
    firefox_options = FirefoxOptions()
    firefox_options.add_argument("--headless")
    firefox_options.add_argument("--no-sandbox")
    firefox_options.add_argument("--disable-dev-shm-usage")
    firefox_options.add_argument("--disable-gpu")
    firefox_options.add_argument("--window-size=1920,1080")
    # Agregar más opciones si es necesario

    user_agent = os.getenv('USER_AGENT', "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                                         "Firefox/92.0")
    firefox_options.set_preference("general.useragent.override", user_agent)

    # Inicializar el servicio de Firefox
    firefox_service = FirefoxService()

    try:
        driver = webdriver.Firefox(options=firefox_options, service=firefox_service)
        logger.info("WebDriver de Firefox inicializado correctamente en modo headless.")
    except WebDriverException as e:
        logger.error(f"Error al inicializar el WebDriver: {e}")
        raise e

    return driver

def validar_ruc(ruc: str) -> bool:
    """
    Valida que el RUC tenga el formato correcto.
    Un RUC válido en Perú tiene 11 dígitos numéricos y cumple con un algoritmo de verificación.

    Args:
        ruc (str): Número de RUC a validar.

    Returns:
        bool: True si el RUC es válido, False en caso contrario.
    """
    if not re.match(r'^\d{11}$', ruc):
        return False

    # Implementación del algoritmo de validación de RUC
    multiplicadores = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = sum(int(digito) * mult for digito, mult in zip(ruc[:10], multiplicadores))
    resto = suma % 11
    digito_verificador = 11 - resto
    if digito_verificador == 10:
        digito_verificador = 0
    elif digito_verificador == 11:
        digito_verificador = 1

    return digito_verificador == int(ruc[-1])

def consultar_ruc(ruc: str) -> Dict[str, Any]:
    """
    Realiza la consulta de un RUC en la página de SUNAT y devuelve los datos obtenidos.
    Implementa un sistema de caché para evitar consultas repetidas al mismo RUC.

    Args:
        ruc (str): Número de RUC a consultar.

    Returns:
        Dict[str, Any]: Datos obtenidos o mensaje de error.
    """
    logger.info(f"Iniciando consulta para el RUC: {ruc}")

    # Validar el RUC antes de procesarlo
    if not validar_ruc(ruc):
        logger.warning(f"El RUC proporcionado no es válido: {ruc}")
        return {"error": f"El RUC proporcionado no es válido: {ruc}"}

    # Sanitizar la entrada (aunque en este caso solo son dígitos)
    ruc = re.sub(r'\D', '', ruc)

    # Verificar si el RUC está en caché y no ha expirado
    with cache_lock:
        if ruc in cache_ruc:
            cache_entry = cache_ruc[ruc]
            if datetime.now() - cache_entry['timestamp'] < timedelta(seconds=CACHE_TTL):
                logger.info(f"Resultado obtenido del caché para el RUC: {ruc}")
                return cache_entry['data']
            else:
                # Eliminar entrada de caché expirada
                del cache_ruc[ruc]
                logger.info(f"Entrada de caché expirada eliminada para el RUC: {ruc}")

    # Adquirir el semáforo para limitar concurrencia
    logger.info("Esperando disponibilidad para iniciar una nueva sesión de Selenium...")
    with semaforo:
        logger.info("Semáforo adquirido. Iniciando nueva sesión de Selenium.")
        driver = configurar_driver()

        url = 'https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/FrameCriterioBusquedaWeb.jsp'
        resultado = {}

        try:
            logger.info(f"Accediendo a la URL: {url}")
            driver.get(url)

            # Esperar a que el campo de búsqueda esté presente
            input_element = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.NAME, "search1"))
            )
            input_element.clear()
            input_element.send_keys(ruc)
            logger.info("Número de RUC ingresado en el campo de búsqueda.")

            # Esperar a que el botón de búsqueda esté clickeable
            boton_buscar = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.ID, "btnAceptar"))
            )
            boton_buscar.click()
            logger.info("Botón de búsqueda clickeado.")

            # Esperar a que los resultados estén presentes
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CLASS_NAME, "list-group"))
            )
            logger.info("Resultados cargados correctamente.")

            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')

            # Extracción de información
            ruc_y_razon_social_element = soup.find('h4', string=re.compile("Número de RUC:"))
            if ruc_y_razon_social_element:
                ruc_y_razon_social = ruc_y_razon_social_element.find_next('h4').text.strip()
                ruc_extracted, razon_social = ruc_y_razon_social.split(' - ', 1)
                logger.info(f"RUC encontrado: {ruc_extracted}, Razón Social: {razon_social}")
            else:
                ruc_extracted = razon_social = ""
                logger.warning("No se encontró el elemento con el Número de RUC.")

            def get_info(label: str) -> str:
                element = soup.find('h4', string=re.compile(label))
                if element:
                    next_element = element.find_next('p')
                    if next_element:
                        return next_element.text.strip()
                return ""

            # Extracción de datos
            tipo_contribuyente = get_info("Tipo Contribuyente:")
            nombre_comercial = get_info("Nombre Comercial:")
            fecha_inscripcion = get_info("Fecha de Inscripción:")
            fecha_inicio_actividades = get_info("Fecha de Inicio de Actividades:")
            estado_contribuyente = get_info("Estado del Contribuyente:")
            condicion_contribuyente = get_info("Condición del Contribuyente:")
            domicilio_fiscal = get_info("Domicilio Fiscal:")
            domicilio_fiscal = re.sub(r'\s+', ' ', domicilio_fiscal)
            sistema_emision_comprobante = get_info("Sistema Emisión de Comprobante:")
            actividad_comercio_exterior = get_info("Actividad Comercio Exterior:")
            sistema_contabilidad = get_info("Sistema Contabilidad:")

            # Actividad económica principal
            actividades_economicas_element = soup.find('h4', string=re.compile("Actividad\(es\) Económica\(s\):"))
            actividad_principal = ""
            if actividades_economicas_element:
                actividades_economicas = actividades_economicas_element.find_next('table')
                if actividades_economicas:
                    for row_act in actividades_economicas.find_all('tr'):
                        if 'Principal' in row_act.text:
                            actividad_principal = row_act.text.strip().split(' - ')[-1]
                            break

            resultado = {
                "Número de RUC": ruc_extracted,
                "Razón Social": razon_social,
                "Tipo Contribuyente": tipo_contribuyente,
                "Nombre Comercial": nombre_comercial,
                "Fecha de Inscripción": fecha_inscripcion,
                "Fecha de Inicio de Actividades": fecha_inicio_actividades,
                "Estado del Contribuyente": estado_contribuyente,
                "Condición del Contribuyente": condicion_contribuyente,
                "Domicilio Fiscal": domicilio_fiscal,
                "Sistema Emisión de Comprobante": sistema_emision_comprobante,
                "Actividad Comercio Exterior": actividad_comercio_exterior,
                "Sistema Contabilidad": sistema_contabilidad,
                "Actividad Principal": actividad_principal
            }

            logger.info("Extracción de datos completada exitosamente.")

            # Almacenar en caché con límite de tamaño
            with cache_lock:
                if len(cache_ruc) >= MAX_CACHE_SIZE:
                    oldest_ruc = min(cache_ruc.items(), key=lambda x: x[1]['timestamp'])[0]
                    del cache_ruc[oldest_ruc]
                    logger.info(f"Entrada de caché eliminada para el RUC más antiguo: {oldest_ruc}")
                cache_ruc[ruc] = {
                    'data': resultado,
                    'timestamp': datetime.now()
                }
                logger.info(f"Resultado almacenado en caché para el RUC: {ruc}")

        except (TimeoutException, NoSuchElementException) as e:
            logger.error(f"Error al procesar el RUC {ruc}: {e}")
            resultado = {"error": f"Error al procesar el RUC {ruc}: {str(e)}"}
        except Exception as e:
            logger.error(f"Error inesperado al procesar el RUC {ruc}: {e}")
            resultado = {"error": f"Error inesperado al procesar el RUC {ruc}: {str(e)}"}
        finally:
            driver.quit()
            logger.info("WebDriver cerrado.")

    return resultado

@app.before_request
def start_timer():
    """Inicia el temporizador antes de manejar una solicitud."""
    g.start = time.time()

@app.after_request
def record_metrics(response):
    """Registra las métricas de Prometheus después de manejar una solicitud."""
    resp_time = time.time() - g.start
    REQUEST_LATENCY.labels(request.path).observe(resp_time)
    REQUEST_COUNT.labels(request.path, request.method, response.status_code).inc()
    return response

@app.route('/consultar_ruc', methods=['GET'])
@limiter.limit("10 per minute")  # Limitar solicitudes a este endpoint
def api_consultar_ruc():
    """
    Endpoint para consultar información de un RUC específico.

    Returns:
        JSON: Datos del RUC consultado o mensaje de error.
    """
    ruc = request.args.get('ruc', None)
    if not ruc:
        logger.warning("Solicitud sin parámetro 'ruc'.")
        return jsonify({"error": "Se requiere el parámetro 'ruc'."}), 400

    try:
        resultado = consultar_ruc(ruc)
        # Manejar errores específicos
        if 'error' in resultado:
            return jsonify(resultado), 400
        return jsonify(resultado), 200
    except Exception as e:
        logger.error(f"Error al procesar la solicitud: {e}")
        return jsonify({"error": f"Error al procesar el RUC {ruc}: {str(e)}"}), 500

@app.route('/metrics')
def metrics():
    """
    Endpoint para exponer métricas de Prometheus.

    Returns:
        Response: Métricas en formato Prometheus.
    """
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

if __name__ == '__main__':
    # Iniciar el hilo de limpieza del caché
    hilo_cache = threading.Thread(target=limpiar_cache, daemon=True)
    hilo_cache.start()

    # Ejecutar la aplicación Flask
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

