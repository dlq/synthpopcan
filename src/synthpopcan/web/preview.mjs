export function previewCsv(text, { maxRows = 5, maxColumns = 6 } = {}) {
  const records = readPreviewRecords(text, maxRows + 1);
  if (records.length === 0) {
    return {
      columns: [],
      hiddenColumnCount: 0,
      rows: [],
      rowLimit: maxRows,
      hasMoreRows: false,
    };
  }
  const headers = records[0];
  const columns = headers.slice(0, maxColumns);
  return {
    columns,
    hiddenColumnCount: Math.max(headers.length - columns.length, 0),
    rows: records.slice(1, maxRows + 1).map((record) => rowObject(headers, record)),
    rowLimit: maxRows,
    hasMoreRows: records.length > maxRows + 1,
  };
}

function rowObject(headers, record) {
  return Object.fromEntries(
    headers.map((header, index) => [header, record[index] ?? ""]),
  );
}

function readPreviewRecords(text, maxRecords) {
  const records = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (inQuotes) {
      if (char === '"' && text[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (char === '"') {
        inQuotes = false;
      } else {
        field += char;
      }
    } else if (char === '"') {
      inQuotes = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n" || char === "\r") {
      if (char === "\r" && text[index + 1] === "\n") {
        index += 1;
      }
      row.push(field);
      pushRecord(records, row);
      if (records.length > maxRecords) {
        return records;
      }
      row = [];
      field = "";
    } else {
      field += char;
    }
  }

  if (field !== "" || row.length > 0) {
    row.push(field);
    pushRecord(records, row);
  }
  return records;
}

function pushRecord(records, row) {
  if (row.length === 1 && row[0] === "") {
    return;
  }
  records.push(row);
}
