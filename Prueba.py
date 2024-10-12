from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
import pandas as pd
import time

# Función que realiza la consulta para un solo RUC
def consultar_ruc(ruc):
    # Configuración del navegador en modo headless
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920x1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.5938.132 Safari/537.36"
    )

    driver = webdriver.Chrome(options=chrome_options)

    # URL de la página a consultar
    url = 'https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/FrameCriterioBusquedaWeb.jsp'

    # Lista para almacenar el resultado de este RUC
    resultado = {}

    try:
        driver.get(url)
        
        # Espera a que el campo de entrada esté presente
        input_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "search1"))
        )
        
        # Envía el valor al campo de entrada (Número de RUC)
        input_element.clear()
        input_element.send_keys(ruc)
        
        # Espera hasta que el botón esté presente y haz clic
        boton_buscar = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "btnAceptar"))
        )
        boton_buscar.click()
        
        # Espera a que los resultados se carguen y analiza el HTML resultante
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "list-group"))
        )
        
        # Obtén el contenido de la página
        html = driver.page_source
        
        # Usa BeautifulSoup para analizar el HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extrae el número de RUC y la razón social
        ruc_y_razon_social_element = soup.find('h4', string=re.compile("Número de RUC:"))
        if ruc_y_razon_social_element:
            ruc_y_razon_social = ruc_y_razon_social_element.find_next('h4').text.strip()
            ruc_extracted, razon_social = ruc_y_razon_social.split(' - ', 1)  # Separar en RUC y Razón Social
        else:
            ruc_extracted = razon_social = ""

        # Función auxiliar para extraer información
        def get_info(label):
            element = soup.find('h4', string=re.compile(label))
            if element:
                next_element = element.find_next('p')
                if next_element:
                    return next_element.text.strip()
            return ""

        # Extraer los demás datos del RUC
        tipo_contribuyente = get_info("Tipo Contribuyente:")
        nombre_comercial = get_info("Nombre Comercial:")
        fecha_inscripcion = get_info("Fecha de Inscripción:")
        fecha_inicio_actividades = get_info("Fecha de Inicio de Actividades:")
        estado_contribuyente = get_info("Estado del Contribuyente:")
        condicion_contribuyente = get_info("Condición del Contribuyente:")
        domicilio_fiscal = get_info("Domicilio Fiscal:")
        domicilio_fiscal = re.sub(r'\s+', ' ', domicilio_fiscal)  # Reemplaza múltiples espacios por uno solo
        sistema_emision_comprobante = get_info("Sistema Emisión de Comprobante:")
        actividad_comercio_exterior = get_info("Actividad Comercio Exterior:")
        sistema_contabilidad = get_info("Sistema Contabilidad:")

        # Extraer la actividad económica principal
        actividades_economicas_element = soup.find('h4', string=re.compile("Actividad\(es\) Económica\(s\):"))
        actividad_principal = ""
        if actividades_economicas_element:
            actividades_economicas = actividades_economicas_element.find_next('table')
            if actividades_economicas:
                for row_act in actividades_economicas.find_all('tr'):
                    if 'Principal' in row_act.text:
                        actividad_principal = row_act.text.strip().split(' - ')[-1]
                        break
        
        # Agregar los resultados a un diccionario
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
        print(resultado)
    except Exception as e:
        resultado = {"error": f"Error al procesar el RUC {ruc}: {str(e)}"}
    finally:
        driver.quit()

    return resultado

consultar_ruc('20324562274')