from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import inch
from datetime import datetime
import io

class ReportService:
    @staticmethod
    def generate_daily_close_pdf(metrics: dict, top_products: list):
        """
        Genera un PDF con el resumen del cierre diario.
        """
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Encabezado
        c.setFont("Helvetica-Bold", 20)
        c.drawCentredString(width/2, height - 1*inch, "COFFEE APP - CIERRE DIARIO")
        
        c.setFont("Helvetica", 12)
        c.drawCentredString(width/2, height - 1.3*inch, f"Fecha: {metrics['date']}")
        c.drawCentredString(width/2, height - 1.5*inch, f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Linea divisoria
        c.setStrokeColor(colors.black)
        c.line(0.5*inch, height - 1.8*inch, width - 0.5*inch, height - 1.8*inch)

        # Resumen Financiero
        c.setFont("Helvetica-Bold", 14)
        c.drawString(1*inch, height - 2.2*inch, "Resumen Financiero")
        
        c.setFont("Helvetica", 12)
        y = height - 2.5*inch
        metrics_labels = [
            ("Ventas Brutas", f"${metrics['brute_sales']}"),
            ("IVA Recaudado", f"${metrics['tax_collected']}"),
            ("Ventas Netas", f"${metrics['net_sales']}"),
            ("Costos (Recetas)", f"- ${metrics['cogs']}"),
            ("Gastos Operativos", f("- ${metrics['expenses']}")),
            ("UTILIDAD NETA", f"${metrics['estimated_profit']}")
        ]

        for label, val in metrics_labels:
            c.drawString(1.2*inch, y, label)
            c.drawRightString(width - 1.2*inch, y, val)
            y -= 0.3*inch

        # Top Productos
        y -= 0.4*inch
        c.setFont("Helvetica-Bold", 14)
        c.drawString(1*inch, y, "Top Productos Vendidos")
        y -= 0.3*inch
        
        c.setFont("Helvetica", 12)
        for p in top_products:
            c.drawString(1.2*inch, y, p['name'])
            c.drawRightString(width - 1.2*inch, y, f"{p['quantity']} unidades")
            y -= 0.25*inch

        # Pie de pagina
        c.setFont("Helvetica-Oblique", 9)
        c.drawCentredString(width/2, 0.5*inch, "Documento de uso interno - Auditoria CoffeeApp")

        c.showPage()
        c.save()
        
        buffer.seek(0)
        return buffer
