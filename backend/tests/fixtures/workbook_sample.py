"""P5.14 — sample workbook fixture (xlsx).

Built on import using openpyxl. Two sheets:

  • "Revenue": date, region, units, price (12 monthly rows)
  • "Costs":   category, q1, q2, q3, q4 (5 rows; one with an outlier)

Used by `tests/test_phase_p5_14_workbook_analyze.py` and by the
Playwright trace for the live E2E pass.
"""
from __future__ import annotations

import io
from datetime import date
from openpyxl import Workbook


def build_sample_xlsx() -> bytes:
    wb = Workbook()
    revenue = wb.active
    revenue.title = "Revenue"
    revenue.append(["date", "region", "units", "price"])
    base_units = 100
    for i in range(12):
        d = date(2026, (i % 12) + 1, 1)
        # Linear trend + small noise; row 7 is the outlier.
        units = base_units + 8 * i + (140 if i == 7 else 0)
        price = 9.5 + 0.05 * i
        region = "EMEA" if i % 2 == 0 else "APAC"
        revenue.append([d, region, units, price])

    costs = wb.create_sheet("Costs")
    costs.append(["category", "q1", "q2", "q3", "q4"])
    costs.append(["payroll", 120, 122, 125, 128])
    costs.append(["rent",     32,  32,  32,  32])
    costs.append(["cloud",    18,  21,  24,  220])  # q4 outlier
    costs.append(["travel",   10,   8,  12,   9])
    costs.append(["misc",      4,   5,   6,   7])

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def build_sample_csv() -> bytes:
    rows = [
        "date,region,units,price",
    ]
    base_units = 100
    for i in range(12):
        d = f"2026-{(i % 12) + 1:02d}-01"
        units = base_units + 8 * i + (140 if i == 7 else 0)
        price = 9.5 + 0.05 * i
        region = "EMEA" if i % 2 == 0 else "APAC"
        rows.append(f"{d},{region},{units},{price:.2f}")
    return ("\n".join(rows) + "\n").encode("utf-8")
