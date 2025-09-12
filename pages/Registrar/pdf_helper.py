# utils/pdf_generator.py
import io
import tempfile
import plotly.io as pio
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

def generate_pdf(title, summary_metrics=None, dataframes=None, charts=None):
    """
    Generate a PDF report with title, summary metrics, tables, and optional charts.
    Formatted for Letter landscape with wrapped text for wide tables.

    Args:
        title (str): Title of the report
        summary_metrics (dict): Summary data to display as key-value
        dataframes (list): List of tuples (table_title, dataframe)
        charts (list): List of tuples (chart_title, fig) where fig is a Plotly figure

    Returns:
        BytesIO buffer containing the generated PDF.
    """
    buffer = io.BytesIO()

    # Letter landscape page
    page_width, page_height = landscape(letter)

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=30,
        rightMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()
    normal_style = styles["Normal"]
    elements = []

    # Title
    elements.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
    elements.append(Spacer(1, 20))

    # Summary metrics
    if summary_metrics:
        for key, value in summary_metrics.items():
            elements.append(Paragraph(f"<b>{key}:</b> {value}", normal_style))
        elements.append(Spacer(1, 15))

    # Charts (optional)
    if charts:
        for chart_title, fig in charts:
            elements.append(Paragraph(f"<b>{chart_title}</b>", styles["Heading2"]))
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                pio.write_image(fig, tmp.name, format="png", width=900, height=500, scale=2)
                img = Image(tmp.name, width=500, height=280)
                img.hAlign = "CENTER"
                elements.append(img)
                elements.append(Spacer(1, 20))

    # Tables
    if dataframes:
        for table_title, df in dataframes:
            elements.append(Paragraph(f"<b>{table_title}</b>", styles["Heading2"]))
            elements.append(Spacer(1, 10))

            if not df.empty:
                # Convert all cells to Paragraph for wrapping long text
                table_data = []
                # Header
                header_row = [Paragraph(str(col), normal_style) for col in df.columns]
                table_data.append(header_row)
                # Rows
                for row in df.values.tolist():
                    table_data.append([Paragraph(str(cell), normal_style) for cell in row])

                # Auto-scale columns to fit page width
                col_count = len(df.columns)
                col_width = (page_width - 60) / col_count  # 30 margin each side
                table = Table(table_data, colWidths=[col_width] * col_count, repeatRows=1)
                table.hAlign = "CENTER"

                # Style
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F81BD")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),  # smaller font for wide tables
                    ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
                ]))
                elements.append(table)
                elements.append(Spacer(1, 20))
            else:
                elements.append(Paragraph("No data available.", normal_style))
                elements.append(Spacer(1, 20))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer
