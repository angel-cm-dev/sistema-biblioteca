type Tone = 'green' | 'amber' | 'red' | 'blue' | 'slate' | 'violet';

const tones: Record<Tone, string> = {
  green: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300',
  amber: 'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-300',
  red: 'bg-rose-100 text-rose-800 dark:bg-rose-900/50 dark:text-rose-300',
  blue: 'bg-brand-100 text-brand-800 dark:bg-brand-900/50 dark:text-brand-300',
  violet: 'bg-violet-100 text-violet-800 dark:bg-violet-900/50 dark:text-violet-300',
  slate: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
};

/** Color por estado: cada estado del dominio tiene un significado visual consistente. */
const STATUS_TONE: Record<string, Tone> = {
  disponible: 'green',
  prestado: 'blue',
  apartado: 'violet',
  mantenimiento: 'amber',
  perdido: 'red',
  activo: 'blue',
  devuelto: 'slate',
  vencido: 'red',
  pendiente: 'amber',
  lista: 'violet',
  atendida: 'green',
  cancelada: 'slate',
  expirada: 'slate',
  pagada: 'green',
  bloqueado: 'red',
};

export function statusTone(status: string): Tone {
  return STATUS_TONE[status] ?? 'slate';
}

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const text = label ?? status;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${tones[statusTone(status)]}`}
    >
      {text}
    </span>
  );
}
