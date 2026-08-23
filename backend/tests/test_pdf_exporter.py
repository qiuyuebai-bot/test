from app.services.pdf_exporter import PDFExporter


def test_missing_metric_is_labeled_as_pending():
    assert PDFExporter._percent(None) == "待计算"


def test_zero_metric_remains_zero():
    assert PDFExporter._percent(0) == "0.0%"
