export function parseCsv(text) {
  const records = parseCsvRecords(text);
  if (records.length === 0) {
    return [];
  }
  const headers = records[0];
  return records
    .slice(1)
    .filter(hasAnyValue)
    .map((record) => {
      const row = {};
      headers.forEach((header, index) => {
        row[header] = record[index] ?? "";
      });
      return row;
    });
}

export function stringifyCsv(rows, columns = null) {
  if (rows.length === 0) {
    return "";
  }
  const outputColumns = columns ?? Object.keys(rows[0]);
  const lines = [
    outputColumns.map(escapeCsvValue).join(","),
    ...rows.map((row) =>
      outputColumns.map((column) => escapeCsvValue(row[column] ?? "")).join(","),
    ),
  ];
  return `${lines.join("\n")}\n`;
}

function parseCsvRecords(text) {
  const records = [];
  let record = [];
  let field = "";
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];

    if (quoted) {
      if (char === '"' && next === '"') {
        field += '"';
        index += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        field += char;
      }
      continue;
    }

    if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      record.push(field);
      field = "";
    } else if (char === "\n") {
      record.push(field);
      records.push(record);
      record = [];
      field = "";
    } else if (char !== "\r") {
      field += char;
    }
  }

  if (field !== "" || record.length > 0) {
    record.push(field);
    records.push(record);
  }
  return records;
}

function hasAnyValue(record) {
  return record.some((value) => value !== "");
}

function escapeCsvValue(value) {
  const text = String(value);
  if (/[",\n\r]/.test(text)) {
    return `"${text.replaceAll('"', '""')}"`;
  }
  return text;
}
