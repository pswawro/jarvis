import type { JSX } from "react";

export function parseBold(text: string, keyBase: number, dark = false) {
  const parts: (string | JSX.Element)[] = [];
  const re = /\*\*(.+?)\*\*/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let key = keyBase;
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    parts.push(
      <strong key={key++} className={`font-semibold ${dark ? "text-white/90" : "text-gray-800"}`}>
        {match[1]}
      </strong>,
    );
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export function parseMarkdown(text: string, dark = false) {
  const lines = text.split("\n");
  const result: JSX.Element[] = [];
  let bullets: string[] = [];
  let tableRows: string[][] = [];
  let key = 0;

  const flushBullets = () => {
    if (bullets.length === 0) return;
    result.push(
      <ul key={key++} className="list-disc list-inside space-y-0.5">
        {bullets.map((b, i) => (
          <li key={i}>{parseBold(b, key + i * 100, dark)}</li>
        ))}
      </ul>,
    );
    bullets = [];
  };

  const flushTable = () => {
    if (tableRows.length === 0) return;
    const header = tableRows[0];
    const body = tableRows.slice(1);
    result.push(
      <div key={key++} className="overflow-x-auto my-1">
        <table className="w-full text-[12px] border-collapse">
          <thead>
            <tr className={`border-b ${dark ? "border-white/10" : "border-gray-200"}`}>
              {header.map((h, i) => (
                <th key={i} className={`text-left py-1.5 px-2 font-semibold whitespace-nowrap ${dark ? "text-white/50" : "text-gray-600"}`}>{parseBold(h.trim(), key + i * 100, dark)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {body.map((row, ri) => (
              <tr key={ri} className={`border-b ${dark ? "border-white/5" : "border-gray-50"}`}>
                {row.map((cell, ci) => (
                  <td key={ci} className={`py-1 px-2 whitespace-nowrap ${dark ? "text-white/60" : "text-gray-700"}`}>{parseBold(cell.trim(), key + ri * 100 + ci, dark)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>,
    );
    tableRows = [];
  };

  const isTableRow = (line: string) => line.trim().startsWith("|") && line.trim().endsWith("|");
  const isSeparator = (line: string) => /^\|[\s:-]+(\|[\s:-]+)*\|$/.test(line.trim());
  const parseTableRow = (line: string) => line.trim().slice(1, -1).split("|");

  for (const line of lines) {
    if (isTableRow(line)) {
      flushBullets();
      if (isSeparator(line)) continue; // skip --- separator rows
      tableRows.push(parseTableRow(line));
    } else {
      flushTable();
      const bullet = line.match(/^[-\u2022]\s+(.*)/);
      if (bullet) {
        bullets.push(bullet[1]);
      } else {
        flushBullets();
        result.push(<span key={key++}>{parseBold(line, key * 100, dark)}{"\n"}</span>);
      }
    }
  }
  flushBullets();
  flushTable();
  return result;
}
