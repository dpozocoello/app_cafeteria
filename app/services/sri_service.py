import xml.etree.ElementTree as ET
from datetime import datetime
from ..models.sales import Sale, SaleDetail
from ..models.core import Branch

class SRIService:
    """
    Servicio encargado de la integración con el Servicio de Rentas Internas (SRI) de Ecuador.
    
    Gestiona la lógica técnica requerida para la facturación electrónica:
    1. Generación de claves de acceso estructuradas de 49 dígitos.
    2. Cálculo de dígito verificador usando el algoritmo matemático Módulo 11.
    3. Construcción del comprobante electrónico en formato XML (versión 1.1.0).
    4. Firma digital del comprobante XML usando esquemas XAdES-BES.
    """

    @staticmethod
    def generate_access_key(sale: Sale, branch: Branch) -> str:
        """
        Genera la clave de acceso oficial de 49 dígitos requerida por el SRI para comprobantes electrónicos.
        
        Estructura de la clave de acceso de 49 dígitos:
        - [0-7]   Fecha de Emisión (8 dígitos): ddmmaaaa (Ej: 01062026)
        - [8-9]   Tipo de Comprobante (2 dígitos): "01" representa Factura
        - [10-22] Número de RUC de la Empresa (13 dígitos): Ej: "1790011001001"
        - [23]    Tipo de Ambiente (1 dígito): "1" Pruebas, "2" Producción
        - [24-29] Serie del Comprobante (6 dígitos): Código de Establecimiento (3) + Punto de Emisión (3) (Ej: "001001")
        - [30-38] Secuencial del Comprobante (9 dígitos): Correlativo autoincremental de factura relleno de ceros
        - [39-46] Código Numérico (8 dígitos): Número aleatorio para evitar colisiones
        - [47]    Tipo de Emisión (1 dígito): "1" Emisión Normal
        - [48]    Dígito Verificador (1 dígito): Calculado mediante algoritmo Módulo 11 sobre los primeros 48 dígitos
        
        :param sale: Objeto de la venta (Sale) con datos de timestamp y ambiente
        :param branch: Sucursal (Branch) con el código de establecimiento del SRI
        :return: Clave de acceso de 49 dígitos como string
        """
        fecha = sale.timestamp.strftime("%d%m%Y")
        tipo_comprobante = "01" # 01 representa Factura en el catálogo del SRI
        ruc = "1790011001001" # TODO: En producción, obtener este valor de la configuración global de la empresa
        ambiente = str(sale.environment)
        serie = branch.sri_establishment_code + "001" # Código del establecimiento + Punto de emisión por defecto
        secuencial = str(sale.id).zfill(9) # Representación a 9 dígitos rellena con ceros a la izquierda
        codigo_numerico = "12345678" # Código numérico fijo/aleatorio para el resguardo de la unicidad del documento
        tipo_emision = "1" # "1" representa Emisión Normal
        
        # Concatenación de los primeros 48 dígitos para el cálculo del chequeador
        clave_parcial = f"{fecha}{tipo_comprobante}{ruc}{ambiente}{serie}{secuencial}{codigo_numerico}{tipo_emision}"
        
        # Obtener el dígito verificador matemático mediante Módulo 11
        verificador = SRIService._calculate_modulo11(clave_parcial)
        
        # Retornar la clave de acceso definitiva de 49 dígitos
        return f"{clave_parcial}{verificador}"

    @staticmethod
    def _calculate_modulo11(cadena: str) -> int:
        """
        Implementa el algoritmo Módulo 11 (con pivote 2-7) requerido por el SRI de Ecuador.
        
        Paso a paso del algoritmo:
        1. Multiplicar cada dígito de la derecha a la izquierda por factores secuenciales del 2 al 7 (el factor vuelve a ser 2 si supera el 7).
        2. Sumar todos los resultados de los productos de cada dígito.
        3. Calcular el residuo de la suma dividida para 11 (suma % 11).
        4. Restar el residuo de 11 (11 - residuo).
        5. Casos especiales de resultados:
           - Si el resultado es 11, el dígito verificador es 0.
           - Si el resultado es 10, el dígito verificador es 1.
           - En cualquier otro caso, el dígito verificador es el resultado directo de la resta.
           
        :param cadena: Clave parcial de 48 dígitos
        :return: Dígito verificador entero (0-9)
        """
        pivot = 2
        suma = 0
        # Iterar de derecha a izquierda multiplicando por el pivote rotativo
        for i in range(len(cadena) - 1, -1, -1):
            suma += int(cadena[i]) * pivot
            pivot += 1
            if pivot > 7:
                pivot = 2
        
        residuo = suma % 11
        resultado = 11 - residuo
        
        # Reglas específicas de normalización de salida del SRI
        if resultado == 11:
            return 0
        if resultado == 10:
            return 1
        return resultado

    @staticmethod
    def create_invoice_xml(sale: Sale, branch: Branch) -> str:
        """
        Construye la estructura de datos XML de la factura según la ficha técnica de comprobantes electrónicos v1.1.0 del SRI.
        
        Genera nodos estándar de:
        - infoTributaria: RUC, Razón Social, Clave de Acceso de 49 dígitos, Tipo de Documento, Establecimiento, etc.
        - infoFactura: Fecha de emisión, tipo de identificación del comprador, totales, descuentos, e impuestos globales.
        - detalles: Desglose de cada producto vendido (cantidad, precio unitario, descuentos e IVA individualizado).
        - pagos: Detalle de formas de pago declaradas bajo la codificación oficial del SRI.
        
        :param sale: Entidad Sale con el estado completo de la venta
        :param branch: Establecimiento donde se emitió el documento
        :return: Cadena XML formateada sin firmar
        """
        # Elemento raíz de la factura
        factura = ET.Element("factura", id="comprobante", version="1.1.0")
        
        # 1. Bloque de Información Tributaria (Común para todos los documentos electrónicos)
        info_tributaria = ET.SubElement(factura, "infoTributaria")
        ET.SubElement(info_tributaria, "ambiente").text = str(sale.environment)
        ET.SubElement(info_tributaria, "tipoEmision").text = "1"
        ET.SubElement(info_tributaria, "razonSocial").text = "COFFEE APP S.A."
        ET.SubElement(info_tributaria, "ruc").text = "1790011001001"
        ET.SubElement(info_tributaria, "claveAcceso").text = sale.access_key
        ET.SubElement(info_tributaria, "codDoc").text = "01" # "01" = Factura
        ET.SubElement(info_tributaria, "estab").text = branch.sri_establishment_code
        ET.SubElement(info_tributaria, "ptoEmi").text = "001"
        ET.SubElement(info_tributaria, "secuencial").text = str(sale.id).zfill(9)
        ET.SubElement(info_tributaria, "dirMatriz").text = "QUITO - ECUADOR"

        # 2. Bloque de Información Comercial y Datos de la Transacción
        info_factura = ET.SubElement(factura, "infoFactura")
        ET.SubElement(info_factura, "fechaEmision").text = sale.timestamp.strftime("%d/%m/%Y")
        ET.SubElement(info_factura, "dirEstablecimiento").text = branch.address or "QUITO"
        ET.SubElement(info_factura, "obligadoContabilidad").text = "SI"
        ET.SubElement(info_factura, "tipoIdentificacionComprador").text = sale.customer_id_type
        ET.SubElement(info_factura, "razonSocialComprador").text = sale.customer_name
        ET.SubElement(info_factura, "identificacionComprador").text = sale.customer_id
        ET.SubElement(info_factura, "totalSinImpuestos").text = f"{sale.subtotal_0 + sale.subtotal_tax:.2f}"
        ET.SubElement(info_factura, "totalDescuento").text = f"{sale.discount:.2f}"

        # 2.1 Detalle de Impuestos Consolidados
        total_con_impuestos = ET.SubElement(info_factura, "totalConImpuestos")
        total_impuesto = ET.SubElement(total_con_impuestos, "totalImpuesto")
        ET.SubElement(total_impuesto, "codigo").text = "2" # "2" representa Impuesto al Valor Agregado (IVA)
        ET.SubElement(total_impuesto, "codigoPorcentaje").text = "2" # Código del porcentaje según tarifa (e.g. 2 para 12%, o según tarifa vigente)
        ET.SubElement(total_impuesto, "baseImponible").text = f"{sale.subtotal_tax:.2f}"
        ET.SubElement(total_impuesto, "valor").text = f"{sale.tax_amount:.2f}"

        ET.SubElement(info_factura, "importeTotal").text = f"{sale.total:.2f}"
        ET.SubElement(info_factura, "moneda").text = "DOLAR"

        # 3. Bloque de Detalles (Ítems individuales facturados)
        detalles = ET.SubElement(factura, "detalles")
        for detail in sale.details:
            detalle = ET.SubElement(detalles, "detalle")
            ET.SubElement(detalle, "codigoPrincipal").text = str(detail.product_id)
            ET.SubElement(detalle, "descripcion").text = "PRODUCTO" # TODO: Resolver el nombre real del producto en consulta
            ET.SubElement(detalle, "cantidad").text = f"{detail.quantity:.2f}"
            ET.SubElement(detalle, "precioUnitario").text = f"{detail.unit_price:.2f}"
            ET.SubElement(detalle, "descuento").text = f"{detail.discount:.2f}"
            ET.SubElement(detalle, "precioTotalSinImpuesto").text = f"{detail.total - detail.tax_percentage:.2f}"
            
            # Impuestos aplicados por ítem
            impuestos = ET.SubElement(detalle, "impuestos")
            impuesto = ET.SubElement(impuestos, "impuesto")
            ET.SubElement(impuesto, "codigo").text = "2"
            ET.SubElement(impuesto, "codigoPorcentaje").text = "2"
            ET.SubElement(impuesto, "tarifa").text = str(detail.tax_percentage)
            ET.SubElement(impuesto, "baseImponible").text = f"{detail.total - detail.tax_percentage:.2f}"
            ET.SubElement(impuesto, "valor").text = f"{detail.tax_percentage:.2f}"

        # 4. Bloque de Formas de Pago
        pagos = ET.SubElement(info_factura, "pagos")
        for p in sale.payments:
            pago = ET.SubElement(pagos, "pago")
            # "01" representa Efectivo en la tabla oficial de métodos de pago del SRI
            ET.SubElement(pago, "formaPago").text = "01" 
            ET.SubElement(pago, "total").text = f"{p.amount:.2f}"

        return ET.tostring(factura, encoding="unicode")

    @staticmethod
    def sign_xml(xml_content: str, p12_path: str, password: str) -> str:
        """
        Simula (Mock) el firmado digital del comprobante XML usando la norma XAdES-BES.
        
        En un entorno productivo, esta firma digital requiere:
        1. Lectura del certificado de firma electrónica en formato PKCS#12 (.p12) usando la librería 'cryptography'.
        2. Extracción de la llave privada y el certificado X.509.
        3. Envolvimiento XML firmas (nodo ds:Signature) con algoritmos de canonicalización (C14N) y hash (SHA-256).
        
        :param xml_content: Cadena del XML original de la factura
        :param p12_path: Ruta absoluta al archivo del certificado .p12
        :param password: Contraseña asociada a la firma electrónica
        :return: XML firmado digitalmente listo para transmisión
        """
        # TODO: Implementar el proceso real de firmado digital XAdES-BES en producción
        return f"<!-- SIGNED XML MOCK -->\n{xml_content}"
