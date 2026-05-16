from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib import colors
import os
from datetime import datetime

# Language dictionary for manual content (subset of LANGUAGES from FFApp.py, focused on manual sections)
import json as _json_for_manual
import sys as _sys

def _manual_resource(name):
    if hasattr(_sys, "_MEIPASS"):
        cand = os.path.join(_sys._MEIPASS, name)
        if os.path.exists(cand):
            return cand
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.join(here, name)
    return cand if os.path.exists(cand) else name

with open(_manual_resource("manual_translations.json"), 'r', encoding='utf-8') as _fh:
    LANGUAGES = _json_for_manual.load(_fh)


def generate_manual_pdf(language, output_filename):
    """Generate a PDF manual for the specified language."""
    try:
        doc = SimpleDocTemplate(output_filename, pagesize=letter)
        styles = getSampleStyleSheet()
        title_style = styles["Title"]
        heading_style = styles["Heading2"]
        normal_style = styles["Normal"]
        story = []

        # Add logo if available
        logo_path = "logo.png"
        if os.path.exists(logo_path):
            logo = Image(logo_path, width=1*inch, height=1*inch)
            logo.hAlign = "LEFT"
            story.append(logo)
            story.append(Spacer(1, 12))

        # Title
        story.append(Paragraph(LANGUAGES[language]["title"], title_style))
        story.append(Spacer(1, 24))

        # Sections
        sections = [
            ("intro", "intro"),
            ("start", "start_text"),
            ("event", "event_text"),
            ("participants", "participants_text"),
            ("catches", "catches_text"),
            ("reports", "reports_text"),
            ("export_import", "export_import_text"),
            ("reset", "reset_text"),
            ("troubleshoot", "troubleshoot_text"),
            ("contact", "contact_text")
        ]

        for section_key, text_key in sections:
            story.append(Paragraph(LANGUAGES[language][section_key], heading_style))
            story.append(Spacer(1, 12))
            story.append(Paragraph(LANGUAGES[language][text_key], normal_style))
            story.append(Spacer(1, 24))

        # Footer with copyright
        def add_footer(canvas, doc):
            canvas.saveState()
            canvas.setFont("Helvetica", 10)
            canvas.drawString(0.75*inch, 0.5*inch, LANGUAGES[language]["copyright"])
            canvas.restoreState()

        doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
        print(f"Generated manual: {output_filename}")
    except Exception as e:
        print(f"Failed to generate manual for {language}: {str(e)}")

def main():
    # Create output directory
    output_dir = "Fescherfrenn_Manuals"
    os.makedirs(output_dir, exist_ok=True)

    # Generate manuals for all languages
    for lang in LANGUAGES:
        filename = os.path.join(output_dir, f"Fescherfrenn_Manual_{lang}.pdf")
        generate_manual_pdf(lang, filename)

if __name__ == "__main__":
    main()
