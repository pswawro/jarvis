/** Escape HTML special characters to prevent XSS in tooltip formatters. */
export function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

const NAMED_COLORS = new Set([
  "black","silver","gray","white","maroon","red","purple","fuchsia",
  "green","lime","olive","yellow","navy","blue","teal","aqua","orange",
  "transparent","currentcolor","inherit",
]);

const COLOR_RE = /^(#[0-9a-fA-F]{3,8}|rgb\(\d{1,3},\s*\d{1,3},\s*\d{1,3}\)|rgba\(\d{1,3},\s*\d{1,3},\s*\d{1,3},\s*[\d.]+\)|hsl\(\d{1,3},\s*\d{1,3}%,\s*\d{1,3}%\))$/;

/** Whitelist color values to prevent injection via color strings. */
export function sanitizeColor(color: string): string {
  const trimmed = color.trim();
  if (COLOR_RE.test(trimmed)) return trimmed;
  if (NAMED_COLORS.has(trimmed.toLowerCase())) return trimmed;
  return '#999';
}
