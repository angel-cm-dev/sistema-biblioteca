export type QueryValue = string | number | boolean | null | undefined;

/** Construye "?a=1&b=x" omitiendo valores vacíos (undefined, null, ""). */
export function buildQuery(params: Record<string, QueryValue>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    search.append(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}

/** Alterna el orden de una columna: campo -> -campo -> campo. */
export function toggleSort(current: string | undefined, field: string): string {
  if (current === field) return `-${field}`;
  return field;
}
