/** Escape HTML special characters to prevent XSS in tooltip formatters. */
export function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

const COLOR_RE = /^(#[0-9a-fA-F]{3,8}|rgb\(\d{1,3},\s*\d{1,3},\s*\d{1,3}\)|rgba\(\d{1,3},\s*\d{1,3},\s*\d{1,3},\s*[\d.]+\)|hsl\(\d{1,3},\s*\d{1,3}%,\s*\d{1,3}%\)|[a-zA-Z]+)$/;

/** Whitelist color values to prevent injection via color strings. */
export function sanitizeColor(color: string): string {
  return COLOR_RE.test(color.trim()) ? color.trim() : '#999';
}
