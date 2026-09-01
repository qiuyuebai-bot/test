"""通过标准刷新路径为今天生成一条每日指标快照。"""
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///C:/Users/22602/Desktop/test/data/app.db"
sys.path.insert(0, r"C:\Users\22602\Desktop\test\backend")

from app.services.report_service import ReportService

ReportService.update_metrics_periodically()
print("daily snapshot refreshed for today")
