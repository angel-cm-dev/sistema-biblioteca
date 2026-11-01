import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { StatusBadge } from '@/components/StatusBadge';
import { Button, Card, ErrorState, Field, LoadingState, PageHeader, SelectField, Table, Td, Th } from '@/components/ui';
import { useAuth } from '@/context/AuthContext';
import { useToast } from '@/context/ToastContext';
import { useFetch } from '@/hooks/useFetch';
import { api, ApiError } from '@/lib/api';
import type { BookDetail, CopyStatus } from '@/types';

const MANUAL_STATES: CopyStatus[] = ['disponible', 'mantenimiento', 'perdido'];

export function BookDetailPage() {
  const { id } = useParams();
  const { isStaff } = useAuth();
  const { notify } = useToast();
  const book = useFetch<BookDetail>(`/books/${id}`);
  const [location, setLocation] = useState('');
  const [adding, setAdding] = useState(false);

  const run = async (action: () => Promise<unknown>, ok: string) => {
    try {
      await action();
      notify(ok);
      book.reload();
    } catch (err) {
      notify(err instanceof ApiError ? err.message : 'Operación fallida', 'error');
    }
  };

  if (book.loading && !book.data) return <LoadingState />;
  if (book.error || !book.data) return <ErrorState message={book.error?.message ?? 'No encontrado'} onRetry={book.reload} />;
  const b = book.data;

  return (
    <>
      <Link to="/libros" className="mb-3 inline-block text-sm text-slate-500 hover:underline">← Volver al catálogo</Link>
      <PageHeader
        title={b.title}
        subtitle={`${b.authors.map((a) => a.name).join(', ')} · ISBN ${b.isbn}`}
        actions={
          !isStaff &&
          b.available_copies === 0 &&
          b.total_copies > 0 && (
            <Button onClick={() => run(() => api.post('/reservations', { book_id: b.id }), 'Reserva registrada')}>
              Reservar
            </Button>
          )
        }
      />
      <div className="mb-6 grid gap-4 sm:grid-cols-4">
        {[
          ['Categoría', b.category?.name ?? '—'],
          ['Editorial', b.publisher ?? '—'],
          ['Año', b.publication_year ?? '—'],
          ['En cola de reserva', b.queue_length],
        ].map(([label, value]) => (
          <Card key={String(label)} className="p-4">
            <p className="text-xs text-slate-500">{label}</p>
            <p className="mt-1 font-medium">{value}</p>
          </Card>
        ))}
      </div>

      <Card>
        <div className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row sm:items-end sm:justify-between dark:border-slate-800">
          <h2 className="font-semibold">
            Ejemplares ({b.available_copies} de {b.total_copies} disponibles)
          </h2>
          {isStaff && (
            <div className="flex items-end gap-2">
              <Field label="Ubicación" placeholder="Estante A-3" value={location} onChange={(e) => setLocation(e.target.value)} />
              <Button
                loading={adding}
                onClick={async () => {
                  setAdding(true);
                  await run(() => api.post(`/books/${b.id}/copies`, { location: location || null }), 'Ejemplar agregado');
                  setLocation('');
                  setAdding(false);
                }}
              >
                Agregar ejemplar
              </Button>
            </div>
          )}
        </div>
        <Table>
          <thead>
            <tr>
              <Th>Código de inventario</Th>
              <Th>Ubicación</Th>
              <Th>Estado</Th>
              {isStaff && <Th className="text-right">Cambiar estado</Th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {b.copies.map((c) => (
              <tr key={c.id}>
                <Td className="font-mono text-xs">{c.inventory_code}</Td>
                <Td>{c.location ?? '—'}</Td>
                <Td><StatusBadge status={c.status} /></Td>
                {isStaff && (
                  <Td className="text-right">
                    {c.status === 'prestado' || c.status === 'apartado' ? (
                      <span className="text-xs text-slate-400">En circulación</span>
                    ) : (
                      <div className="ml-auto w-40">
                        <SelectField
                          aria-label={`Estado de ${c.inventory_code}`}
                          value={c.status}
                          onChange={(e) =>
                            run(() => api.patch(`/copies/${c.id}/status`, { status: e.target.value }), 'Estado actualizado')
                          }
                        >
                          {MANUAL_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
                        </SelectField>
                      </div>
                    )}
                  </Td>
                )}
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
    </>
  );
}
