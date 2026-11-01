const money = new Intl.NumberFormat('es-PE', { style: 'currency', currency: 'PEN' });

/** Formatea montos que el backend envía como string decimal ("12.50"). */
export function formatMoney(value: string | number | null | undefined): string {
  const n = typeof value === 'string' ? Number.parseFloat(value) : (value ?? 0);
  return money.format(Number.isFinite(n) ? n : 0);
}

/** Fecha "YYYY-MM-DD" o ISO -> "dd/mm/aaaa" sin desfases de zona horaria. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return value;
  if (value.length === 10) return `${match[3]}/${match[2]}/${match[1]}`;
  const date = new Date(value);
  return date.toLocaleDateString('es-PE', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  return new Date(value).toLocaleString('es-PE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function pluralize(n: number, singular: string, plural = `${singular}s`): string {
  return `${n} ${n === 1 ? singular : plural}`;
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join('');
}
