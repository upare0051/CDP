import React, { useCallback, useMemo, useRef } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community';

import { buildColumnDefs } from '@/components/DataGrid/columnDetector';
import { cellRendererRegistry } from '@/components/DataGrid/cellRenderers';

import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';

ModuleRegistry.registerModules([AllCommunityModule]);

export default function DataGrid({
  rows,
  columnDefs: columnDefsProp,
  height,
  showToolbar = true,
  title,
  compact = false,
  className = '',
  domLayout,
  onGridReady,
  ...restProps
}: any) {
  const gridRef = useRef<any>(null);
  const rowData = useMemo(() => rows || [], [rows]);

  const colDefs = useMemo(() => {
    if (columnDefsProp) return columnDefsProp;
    return buildColumnDefs(rowData);
  }, [columnDefsProp, rowData]);

  const defaultColDef = useMemo(
    () => ({
      sortable: true,
      resizable: true,
      filter: true,
      suppressMovable: false,
      wrapHeaderText: true,
      autoHeaderHeight: true,
    }),
    []
  );

  const rowHeight = compact ? 32 : 38;
  const headerHeight = compact ? 36 : 42;

  const computedHeight = useMemo(() => {
    if (height) return height;
    if (rowData.length <= 15) return undefined;
    return '520px';
  }, [height, rowData.length]);

  const computedLayout = domLayout || (rowData.length <= 15 ? 'autoHeight' : 'normal');

  const handleGridReady = useCallback(
    (params: any) => {
      params.api.sizeColumnsToFit();
      if (onGridReady) onGridReady(params);
    },
    [onGridReady]
  );

  const handleExport = useCallback(() => {
    if (gridRef.current?.api) {
      gridRef.current.api.exportDataAsCsv({
        fileName: `c360_export_${new Date().toISOString().slice(0, 10)}.csv`,
      });
    }
  }, []);

  if (!rows || rows.length === 0) return null;

  return (
    <div className={`c360-datagrid-wrapper ${className}`}>
      {showToolbar && (
        <div className="c360-datagrid-toolbar">
          <span className="c360-datagrid-info">
            {title && (
              <>
                <strong>{title}&nbsp;&nbsp;</strong>
              </>
            )}
            {rowData.length.toLocaleString()} row{rowData.length !== 1 ? 's' : ''} · {colDefs.length} col
            {colDefs.length !== 1 ? 's' : ''}
          </span>
          <div className="c360-datagrid-actions">
            <button className="c360-grid-btn" onClick={handleExport} title="Export CSV">
              ⬇ Export
            </button>
          </div>
        </div>
      )}
      <div className="ag-theme-alpine c360-datagrid" style={computedHeight ? { height: computedHeight, width: '100%' } : { width: '100%' }}>
        <AgGridReact
          ref={gridRef}
          rowData={rowData}
          columnDefs={colDefs}
          defaultColDef={defaultColDef}
          domLayout={computedLayout}
          rowHeight={rowHeight}
          headerHeight={headerHeight}
          components={cellRendererRegistry as any}
          animateRows={true}
          enableCellTextSelection={true}
          suppressRowHoverHighlight={false}
          pagination={rowData.length > 100}
          paginationPageSize={100}
          paginationPageSizeSelector={[50, 100, 250, 500]}
          onGridReady={handleGridReady}
          {...restProps}
        />
      </div>
    </div>
  );
}

