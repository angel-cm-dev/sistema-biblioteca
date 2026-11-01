import { useState } from 'react';
import { Pagination } from '@/components/Pagination';
import { StatusBadge } from '@/components/StatusBadge';
import { Alert, Button, Card, EmptyState, ErrorState, LoadingState, PageHeader, SelectField, Table, Td, Th } from '@/components/ui';
import { useAuth } from '@/context/AuthContext';
import { useToast } from '@/context/ToastContext';
import { useFetch } from '@/hooks/useFetch';
import { api, ApiError } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import { buildQuery } from '@/lib/query';
import type { Page, Reservation } from '@/types';

export function ReservationsPage() {
  const { isStaff } = useAuth();
  const { notify } = useToast();
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const reservations = useFetch<Page<Reservation>>(`/reservations${buildQuery({ status, page, size: 10 })}`);

  const cancel = async (r: Reservation) => {
    if (!window.confirm(`¿Cancelar la reserva de "${r.book.title}"?`)) return;
    try {
      await api.post(`/reservations/${r.id}/cancel`);
      notify('Reserva cancelada');
      reservations.reload();
    } catch (err) {
      notify(err instanceof ApiError ? err.message : 'Error', 'error');
    }
  };

  const expire = async () => {
    try {
      const r = await api.post<{ expired: number }>('/reservations/expire-holds');
      notify(r.expired ? `${r.expired} apartado(s) expirado(s) y reasignado(s)` : 'No hay apartados vencidos', 'info');
      reservations.reload();
    } catch (err) {
      notify(err instanceof ApiError ? err.message : 'Error', 'error');
    }
  };

  return (
    <>
      <PageHeader
        title={isStaff ? 'Reservas' : 'Mis reservas'}
        subtitle="Cola FIFO: al devolverse un ejemplar se aparta para el primero de la cola"
        actions={isStaff && <Button variant="secondary" onClick={expire}>Procesar apartados vencidos</Button>}
      />
      {!isStaff && (
        <div className="mb-4">
          <Alert kind="info">
            Cuando su reserva esté <strong>lista</strong>, acérquese al mostrador antes de la fecha límite; de lo contrario
            pasará al siguiente socio de la cola.
          </Alert>
        </div>
      )}
      <Card>
        <div className="p-4 sm:w-60">
          <SelectField aria-label="Estado" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">Todos los estados</option>
            <option value="pendiente">Pendientes</option>
            <option value="lista">Listas para recoger</option>
            <option value="atendida">Atendidas</option>
            <option value="cancelada">Canceladas</option>
            <option value="expirada">Expiradas</option>
          </SelectField>
        </div>
        {reservations.loading && !reservations.data ? (
          <LoadingState />
        ) : reservations.error ? (
          <ErrorState message={reservations.error.message} onRetry={reservations.reload} />
        ) : !reservations.data?.items.length ? (
          <EmptyState title="No hay reservas" description="Puede reservar libros sin ejemplares disponibles desde el catálogo." />
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  <Th>Libro</Th>
                  {isStaff && <Th>Socio</Th>}
                  <Th>Fecha</Th>
                  <Th>Estado</Th>
                  <Th>Detalle</Th>
                  <Th className="text-right">Acciones</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {reservations.data.items.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <Td className="max-w-[16rem] truncate font-medium">{r.book.title}</Td>
                    {isStaff && <Td>{r.member.full_name}<p className="text-xs text-slate-500">{r.member.card_number}</p></Td>}
                    <Td>{formatDateTime(r.created_at)}</Td>
                    <Td><StatusBadge status={r.status} /></Td>
                    <Td className="text-xs text-slate-600 dark:text-slate-300">
                      {r.status === 'pendiente' && r.queue_position && `Posición ${r.queue_position} en la cola`}
                      {r.status === 'lista' && (
                        <>Ejemplar {r.physical_copy?.inventory_code} · recoger hasta {formatDateTime(r.expires_at)}</>
                      )}
                    </Td>
                    <Td className="text-right">
                      {(r.status === 'pendiente' || r.status === 'lista') && (
                        <Button size="sm" variant="ghost" onClick={() => cancel(r)}>Cancelar</Button>
                      )}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <Pagination page={reservations.data.page} pages={reservations.data.pages} total={reservations.data.total} size={reservations.data.size} onChange={setPage} />
          </>
        )}
      </Card>
    </>
  );
}
