"""
Servicio de correo electrónico SMTP.
Soporta Gmail (App Passwords) y Outlook/Office365.
Cumplimiento LOPDP Ecuador / GDPR para notificaciones de consentimiento.
"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Optional


# Plantilla HTML predeterminada para el correo de consentimiento GDPR
DEFAULT_GDPR_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; background: #f8f9fa; padding: 30px;">
  <div style="max-width: 600px; margin: 0 auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
    <!-- Header -->
    <div style="background: linear-gradient(135deg, #1e293b, #334155); padding: 30px; text-align: center;">
      <h1 style="color: #fbbf24; margin: 0; font-size: 1.6rem;">{{negocio}}</h1>
      <p style="color: #94a3b8; margin: 5px 0 0;">Protección de Datos Personales</p>
    </div>

    <!-- Body -->
    <div style="padding: 35px 40px;">
      <p style="color: #374151; font-size: 1rem;">Estimado/a <strong>{{nombre}}</strong>,</p>

      <p style="color: #6b7280; line-height: 1.7;">
        En cumplimiento de la <strong>Ley Orgánica de Protección de Datos Personales (LOPDP)</strong>
        del Ecuador y normativas internacionales aplicables, le informamos que sus datos personales
        han sido registrados en nuestro sistema el día <strong>{{fecha}}</strong>.
      </p>

      <div style="background: #f0fdf4; border-left: 4px solid #10b981; padding: 15px 20px; border-radius: 0 8px 8px 0; margin: 20px 0;">
        <p style="margin: 0; color: #065f46; font-weight: 600;">Datos registrados:</p>
        <ul style="color: #047857; margin: 8px 0 0; padding-left: 20px;">
          <li>Nombre: {{nombre}}</li>
          <li>Tipo de servicio: {{tipo_servicio}}</li>
          {{codigo_delivery}}
        </ul>
      </div>

      <p style="color: #6b7280; line-height: 1.7;">
        <strong>Finalidad del tratamiento:</strong> Sus datos serán utilizados exclusivamente para
        la gestión de su pedido, facturación y comunicaciones relacionadas con el servicio
        prestado. No serán cedidos a terceros sin su consentimiento previo.
      </p>

      <p style="color: #6b7280; line-height: 1.7;">
        <strong>Sus derechos:</strong> Puede ejercer sus derechos de acceso, rectificación,
        supresión, oposición y portabilidad contactándonos en <a href="mailto:{{email_negocio}}" style="color: #fbbf24;">{{email_negocio}}</a>.
      </p>

      <div style="text-align: center; margin: 30px 0;">
        <p style="color: #374151; font-weight: 600;">¿Autoriza el tratamiento de sus datos personales?</p>
        <a href="{{link_aceptar}}" style="display: inline-block; background: #10b981; color: white; padding: 12px 28px; border-radius: 8px; text-decoration: none; font-weight: 700; margin: 5px;">
          ✅ Sí, autorizo
        </a>
        &nbsp;
        <a href="{{link_rechazar}}" style="display: inline-block; background: #ef4444; color: white; padding: 12px 28px; border-radius: 8px; text-decoration: none; font-weight: 700; margin: 5px;">
          ❌ No autorizo
        </a>
      </div>

      <p style="color: #9ca3af; font-size: 0.85rem; text-align: center; margin-top: 20px;">
        Si no solicitó este correo o tiene alguna consulta, contáctenos en {{email_negocio}}.
      </p>
    </div>

    <!-- Footer -->
    <div style="background: #f1f5f9; padding: 20px 40px; text-align: center; border-top: 1px solid #e2e8f0;">
      <p style="color: #94a3b8; font-size: 0.8rem; margin: 0;">
        {{negocio}} · Cumplimiento LOPDP Ecuador · {{fecha}}
      </p>
    </div>
  </div>
</body>
</html>
"""


def _render_template(template: str, variables: dict) -> str:
    """Reemplaza variables {{clave}} en la plantilla HTML."""
    for key, value in variables.items():
        template = template.replace(f"{{{{{key}}}}}", str(value or ""))
    return template


def send_gdpr_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    smtp_use_tls: bool,
    from_name: str,
    from_email: str,
    to_email: str,
    subject: str,
    body_html: str,
) -> tuple[bool, str]:
    """
    Envía un correo vía SMTP.
    Retorna (True, "") si éxito, (False, "mensaje de error") si falla.
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to_email
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        context = ssl.create_default_context()

        if smtp_use_tls:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(smtp_user, smtp_password)
                server.sendmail(from_email, to_email, msg.as_string())
        else:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=15) as server:
                server.login(smtp_user, smtp_password)
                server.sendmail(from_email, to_email, msg.as_string())

        return True, ""

    except smtplib.SMTPAuthenticationError:
        return False, "Error de autenticación SMTP. Verifique usuario y contraseña/app-password."
    except smtplib.SMTPConnectError:
        return False, f"No se pudo conectar a {smtp_host}:{smtp_port}. Verifique host y puerto."
    except smtplib.SMTPException as e:
        return False, f"Error SMTP: {str(e)}"
    except Exception as e:
        return False, f"Error inesperado: {str(e)}"


def generate_gdpr_email(
    template_html: Optional[str],
    customer_name: str,
    service_type: str,
    delivery_code: Optional[str],
    business_name: str,
    business_email: str,
    base_url: str = "http://localhost:8000",
) -> str:
    """Genera el HTML del correo GDPR con variables reemplazadas."""
    html = template_html or DEFAULT_GDPR_TEMPLATE
    tipo_map = {"MESA": "Consumo en Mesa", "LLEVAR": "Para Llevar", "DOMICILIO": "Delivery a Domicilio"}
    delivery_line = f"<li>Código Delivery: {delivery_code}</li>" if delivery_code else ""
    variables = {
        "nombre": customer_name,
        "negocio": business_name,
        "email_negocio": business_email,
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "tipo_servicio": tipo_map.get(service_type, service_type),
        "codigo_delivery": delivery_line,
        "link_aceptar": f"{base_url}/api/customers/gdpr/accept?name={customer_name}",
        "link_rechazar": f"{base_url}/api/customers/gdpr/reject?name={customer_name}",
    }
    return _render_template(html, variables)
