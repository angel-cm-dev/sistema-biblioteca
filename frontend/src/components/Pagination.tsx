interface Props {
  page: number;
  pages: number;
  total: number;
  size: number;
  onChange: (page: number) => void;
}

/** Paginación con resumen "Mostrando X–Y de N". Se oculta si no hay resultados. */
export function Pagination({ page, pages, total, size, onChange }: Props) {
  if (total === 0) return null;
  const from = (page - 1) * size + 1;
  const to = Math.min(page * size, total);
  return (
    <nav
      aria-label="Paginación"
      className="flex flex-col items-center justify-between gap-3 border-t border-slate-200 px-4 py-3 text-sm sm:flex-row dark:border-slate-800"
    >
      <p className="text-slate-500 dark:text-slate-400">
        Mostrando <span className="font-medium">{from}</span>–<span className="font-medium">{to}</span> de{' '}
        <span className="font-medium">{total}</span>
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          className="rounded-lg border border-slate-300 px-3 py-1.5 disabled:opacity-40 dark:border-slate-700"
          onClick={() => onChange(page - 1)}
          disabled={page <= 1}
        >
          Anterior
        </button>
        <span className="tabular-nums text-slate-600 dark:text-slate-300">
          Página {page} de {Math.max(pages, 1)}
        </span>
        <button
          type="button"
          className="rounded-lg border border-slate-300 px-3 py-1.5 disabled:opacity-40 dark:border-slate-700"
          onClick={() => onChange(page + 1)}
          disabled={page >= pages}
        >
          Siguiente
        </button>
      </div>
    </nav>
  );
}
