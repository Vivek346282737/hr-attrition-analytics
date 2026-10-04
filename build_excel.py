"""Build the HR attrition Excel workbook: data, KPI formulas, pivot tables, pivot chart, slicer."""
from pathlib import Path

import pandas as pd
import win32com.client as win32
from openpyxl.styles import Font

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "hr_attrition_tableau.csv"
OUT = ROOT / "excel" / "hr_attrition_analysis.xlsx"
XL_DATABASE, XL_ROW, XL_COLUMN = 1, 1, 2
XL_COUNT, XL_AVERAGE, XL_DESCENDING, XL_BAR = -4112, -4106, 2, 57


def write_base():
    df = pd.read_csv(DATA)
    last = len(df) + 1
    OUT.parent.mkdir(exist_ok=True)
    with pd.ExcelWriter(OUT, engine="openpyxl") as xl:
        df.to_excel(xl, sheet_name="Employees", index=False)
        ws = xl.book["Employees"]
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        k = xl.book.create_sheet("KPI_Summary", 0)
        k["A1"] = "HR Attrition KPI Summary (live formulas)"
        k["A1"].font = Font(bold=True, size=14)
        rng = lambda c: f"Employees!${c}$2:${c}${last}"
        rows = [
            ("Total employees", f"=COUNTA({rng('A')})", "#,##0"),
            ("Employees left", f"=SUM({rng('I')})", "#,##0"),
            ("Attrition rate", f"=SUM({rng('I')})/COUNTA({rng('A')})", "0.0%"),
            ("Attrition rate - overtime", f'=AVERAGEIFS({rng("I")},{rng("G")},"Overtime")', "0.0%"),
            ("Attrition rate - no overtime", f'=AVERAGEIFS({rng("I")},{rng("G")},"No Overtime")', "0.0%"),
            ("Avg monthly income - left", f'=AVERAGEIFS({rng("J")},{rng("B")},"Left")', "#,##0"),
            ("Avg monthly income - stayed", f'=AVERAGEIFS({rng("J")},{rng("B")},"Stayed")', "#,##0"),
            ("Employees left in Sales", f'=COUNTIFS({rng("C")},"Sales",{rng("B")},"Left")', "#,##0"),
        ]
        for i, (label, formula, fmt) in enumerate(rows, start=3):
            k[f"A{i}"], k[f"B{i}"] = label, formula
            k[f"B{i}"].number_format = fmt
        k.column_dimensions["A"].width = 32
        k.column_dimensions["B"].width = 14
    return last


def add_pivot(wb, cache, sheet, rows, values, column=None):
    ws = wb.Worksheets.Add(After=wb.Worksheets(wb.Worksheets.Count))
    ws.Name = sheet
    pt = cache.CreatePivotTable(TableDestination=f"'{sheet}'!R3C1", TableName=sheet)
    pt.PivotFields(rows).Orientation = XL_ROW
    if column:
        pt.PivotFields(column).Orientation = XL_COLUMN
    for field, func, caption, fmt in values:
        pt.AddDataField(pt.PivotFields(field), caption, func).NumberFormat = fmt
    return ws, pt


def add_pivots(last):
    xl = win32.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    try:
        wb = xl.Workbooks.Open(str(OUT))
        cache = wb.PivotCaches().Create(SourceType=XL_DATABASE, SourceData=f"Employees!R1C1:R{last}C11")
        rate = [("Attrition Flag", XL_AVERAGE, "Attrition rate", "0.0%"),
                ("Attrition", XL_COUNT, "Employees", "#,##0")]
        ws1, pt1 = add_pivot(wb, cache, "Pivot_Department", "Department", rate)
        ws2, pt2 = add_pivot(wb, cache, "Pivot_JobRole", "Job Role", rate)
        pt2.PivotFields("Job Role").AutoSort(XL_DESCENDING, "Attrition rate")
        chart = ws2.Shapes.AddChart2(216, XL_BAR, 330, 20, 480, 300).Chart
        chart.SetSourceData(pt2.TableRange1)
        ws3, pt3 = add_pivot(wb, cache, "Pivot_Overtime", "Overtime",
                             [("Attrition Flag", XL_COUNT, "Employees", "#,##0")], column="Attrition")
        slicer = wb.SlicerCaches.Add2(pt1, "Gender")
        slicer.Slicers.Add(ws1, Name="Gender", Caption="Gender", Top=20, Left=330, Width=140, Height=110)
        slicer.PivotTables.AddPivotTable(pt2)
        slicer.PivotTables.AddPivotTable(pt3)
        wb.Worksheets("KPI_Summary").Activate()
        wb.Save()
    finally:
        xl.Quit()


if __name__ == "__main__":
    add_pivots(write_base())
    print(f"Excel workbook ready: {OUT}")
