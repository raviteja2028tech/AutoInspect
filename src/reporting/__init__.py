"""PDF reporting for serialized vehicle-damage assessments.

ReportLab is imported lazily inside :func:`generate_pdf_report`, so importing this
package never fails just because ReportLab is missing.
"""
from .pdf_report import DISCLAIMER, generate_pdf_report

__all__ = ["generate_pdf_report", "DISCLAIMER"]
