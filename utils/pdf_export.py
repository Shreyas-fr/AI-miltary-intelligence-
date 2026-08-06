import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generate_mission_brief_pdf(country, lat, lon, radius, threat_score, threat_level, incident_count, dominant_attack, recommendations):
    """
    Generates a Mission Brief PDF and returns it as a bytes buffer.
    """
    buffer = io.BytesIO()
    
    # Setup document
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=40, leftMargin=40,
                            topMargin=40, bottomMargin=40)
                            
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=15,
        textColor=colors.HexColor("#0f3460")
    )
    
    h2_style = ParagraphStyle(
        'H2Style',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=10,
        textColor=colors.HexColor("#e94560")
    )
    
    normal_style = styles['Normal']
    normal_style.fontSize = 11
    normal_style.leading = 14
    
    bold_style = ParagraphStyle(
        'BoldStyle',
        parent=normal_style,
        fontName='Helvetica-Bold'
    )

    story = []
    
    # Title
    story.append(Paragraph("AI Military Intelligence: Mission Brief", title_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#0f3460"), spaceAfter=15))
    
    # Mission Parameters
    story.append(Paragraph("Operational Parameters", h2_style))
    story.append(Paragraph(f"<b>Target Country:</b> {country}", normal_style))
    story.append(Paragraph(f"<b>Mission Center Coordinates:</b> {lat:.4f}, {lon:.4f}", normal_style))
    story.append(Paragraph(f"<b>Operational Radius:</b> {radius} km", normal_style))
    story.append(Spacer(1, 15))
    
    # Risk Assessment
    story.append(Paragraph("Threat Assessment", h2_style))
    story.append(Paragraph(f"<b>National Threat Score:</b> {threat_score} / 100", normal_style))
    story.append(Paragraph(f"<b>Localized Threat Level:</b> {threat_level}", normal_style))
    story.append(Paragraph(f"<b>Historical Incidents within {radius}km:</b> {incident_count}", normal_style))
    
    if dominant_attack:
        story.append(Paragraph(f"<b>Dominant Historical Attack Vector:</b> {dominant_attack}", normal_style))
        
    story.append(Spacer(1, 15))
    
    # Recommendations
    story.append(Paragraph("Tactical Resource Recommendations", h2_style))
    
    if recommendations:
        for rec in recommendations:
            story.append(Paragraph(f"<b>[{rec.priority.upper()}] {rec.category}</b>", bold_style))
            story.append(Paragraph(f"<i>Action:</i> {rec.action}", normal_style))
            story.append(Paragraph(f"<i>Rationale:</i> {rec.rationale}", normal_style))
            story.append(Spacer(1, 10))
    else:
        story.append(Paragraph("No specific resource recommendations generated for this threat level.", normal_style))
    
    # Build PDF
    doc.build(story)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
