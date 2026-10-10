Option Explicit

' Sample workbook only: Data column B, numeric rows 2 onward.
' Writes only Summary!A1:B3. Does not send, save, delete, or alter source data.
Public Sub SummarizeSample()
    Dim sourceSheet As Worksheet, resultSheet As Worksheet, sheetItem As Worksheet
    Dim lastRow As Long, rowIndex As Long, numericCount As Long
    Dim total As Double, cellValue As Variant
    For Each sheetItem In ThisWorkbook.Worksheets
        If sheetItem.Name = "Data" Then Set sourceSheet = sheetItem
        If sheetItem.Name = "Summary" Then Set resultSheet = sheetItem
    Next sheetItem
    If sourceSheet Is Nothing Then
        MsgBox "Create a Data sheet before running.", vbInformation
        Exit Sub
    End If
    If resultSheet Is Nothing Then
        Set resultSheet = ThisWorkbook.Worksheets.Add(After:=sourceSheet)
        resultSheet.Name = "Summary"
    End If
    lastRow = sourceSheet.Cells(sourceSheet.Rows.Count, "B").End(xlUp).Row
    For rowIndex = 2 To lastRow
        cellValue = sourceSheet.Cells(rowIndex, "B").Value2
        If Not IsError(cellValue) Then
            If Len(CStr(cellValue)) > 0 And IsNumeric(cellValue) Then
                total = total + CDbl(cellValue)
                numericCount = numericCount + 1
            End If
        End If
    Next rowIndex
    resultSheet.Range("A1:B3").Value = Empty
    resultSheet.Range("A1").Value = "Metric"
    resultSheet.Range("B1").Value = "Value"
    resultSheet.Range("A2").Value = "Total"
    resultSheet.Range("B2").Value = total
    resultSheet.Range("A3").Value = "Numeric count"
    resultSheet.Range("B3").Value = numericCount
End Sub
