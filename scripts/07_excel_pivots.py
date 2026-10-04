"""Step 7 - Add pivot tables, a pivot chart and a slicer to the Excel workbook (needs MS Excel)."""
import win32com.client as win32

from config import EXCEL_FILE

XL_UP, XL_DATABASE, XL_ROW, XL_COLUMN = -4162, 1, 1, 2
XL_SUM, XL_COUNT, XL_AVERAGE = -4157, -4112, -4106
XL_DESCENDING, XL_PERCENT_OF_ROW, XL_LINE = 2, 6, 4
PIVOT_SHEETS = ["Pivot_Monthly", "Pivot_Category", "Pivot_Delivery"]


def add_pivot(wb, cache, sheet, rows, values, column=None):
    ws = wb.Worksheets.Add(After=wb.Worksheets(wb.Worksheets.Count))
    ws.Name = sheet
    pt = cache.CreatePivotTable(TableDestination=f"'{sheet}'!R3C1", TableName=sheet)
    pt.PivotFields(rows).Orientation = XL_ROW
    if column:
        pt.PivotFields(column).Orientation = XL_COLUMN
    for field, func, caption, fmt in values:
        data_field = pt.AddDataField(pt.PivotFields(field), caption, func)
        data_field.NumberFormat = fmt
    return ws, pt


def main():
    xl = win32.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    try:
        wb = xl.Workbooks.Open(str(EXCEL_FILE))
        for name in PIVOT_SHEETS:  # make the script safe to re-run
            if name in [s.Name for s in wb.Worksheets]:
                wb.Worksheets(name).Delete()
        src = wb.Worksheets("Orders")
        last = src.Cells(src.Rows.Count, 1).End(XL_UP).Row
        cache = wb.PivotCaches().Create(SourceType=XL_DATABASE, SourceData=f"Orders!R1C1:R{last}C13")

        ws1, pt1 = add_pivot(wb, cache, "Pivot_Monthly", "order_month", [
            ("order_value", XL_SUM, "Revenue", "#,##0"),
            ("order_id", XL_COUNT, "Orders", "#,##0"),
        ])
        chart = ws1.Shapes.AddChart2(227, XL_LINE, 320, 20, 520, 280).Chart
        chart.SetSourceData(pt1.TableRange1)
        chart.HasTitle = True
        chart.ChartTitle.Text = "Monthly revenue and orders"

        ws2, pt2 = add_pivot(wb, cache, "Pivot_Category", "main_category", [
            ("order_value", XL_SUM, "Revenue", "#,##0"),
            ("review_score", XL_AVERAGE, "Avg review", "0.00"),
        ])
        pt2.PivotFields("main_category").AutoSort(XL_DESCENDING, "Revenue")

        ws3, pt3 = add_pivot(wb, cache, "Pivot_Delivery", "delivery_status", [
            ("order_id", XL_COUNT, "Share of orders", "0.0%"),
        ], column="review_score")
        pt3.DataFields("Share of orders").Calculation = XL_PERCENT_OF_ROW

        # one slicer on state, connected to all three pivot tables
        slicer_cache = wb.SlicerCaches.Add2(pt1, "customer_state")
        slicer_cache.Slicers.Add(ws1, Name="State", Caption="State", Top=320, Left=860, Width=150, Height=300)
        slicer_cache.PivotTables.AddPivotTable(pt2)
        slicer_cache.PivotTables.AddPivotTable(pt3)

        wb.Worksheets("KPI_Summary").Activate()
        wb.Save()
        print(f"Added pivot tables, pivot chart and slicer to {EXCEL_FILE}")
    finally:
        xl.Quit()


if __name__ == "__main__":
    main()
