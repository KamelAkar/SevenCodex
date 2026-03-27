export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function escapeHtmlWithBreaks(value) {
  return escapeHtml(value).replace(/\n/g, "<br />");
}

export function formatCount(value) {
  const number = Number(value) || 0;
  return new Intl.NumberFormat(undefined).format(number);
}

export function titleCase(value) {
  return String(value || "")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function compactList(values = []) {
  return [...new Set((values || []).filter(Boolean))];
}

export function normalizeText(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function chip(text, tone = "") {
  const className = ["tag", tone].filter(Boolean).join(" ");
  return `<span class="${className}">${escapeHtml(text)}</span>`;
}

export function joinChips(values = [], tone = "") {
  return compactList(values)
    .map((value) => `<span class="${["tag", tone].filter(Boolean).join(" ")}">${escapeHtml(value)}</span>`)
    .join("");
}

export function kvRows(fields = {}) {
  return Object.entries(fields)
    .filter(([, value]) => value !== null && value !== undefined && value !== "" && !(Array.isArray(value) && value.length === 0))
    .map(([label, value]) => {
      const rendered = Array.isArray(value)
        ? escapeHtml(value.join(", "))
        : typeof value === "object"
        ? escapeHtml(JSON.stringify(value))
        : escapeHtml(value);
      return `<div class="detail-row"><span>${escapeHtml(label)}</span><span>${rendered}</span></div>`;
    })
    .join("");
}

export function formatDateTime(value, language = "en") {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(language === "fr" ? "fr-FR" : "en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
