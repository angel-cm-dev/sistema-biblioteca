import { useState } from 'react';
import { Pagination } from '@/components/Pagination';
import { StatusBadge } from '@/components/StatusBadge';
import { Button, Card, EmptyState, ErrorState, LoadingState, PageHeader, SelectField, Table, Td, Th } from '@/components/ui';
import { useAuth } from '@/context/AuthContext';
import { useToast } from '@/context/ToastContext';
import { useFetch } from '@/hooks/useFetch';
import { api, ApiError } from '@/lib/api';
import { formatDate, formatMoney } from '@/lib/format';
import { buildQuery, toggleSort } from '@/lib/query';
import type { Fine, Page } from '@/types';

export function FinesPage() {
  const { isStaff } = useAuth();
  const { notify } = useToast();
  const [status, setStatus] = useState('pendiente');
  const [sort, setSort] = useState('-created_at');
  const [page, setPage] = useState(1);
  const fines = useFetch<Page<Fine>>(`/fines${buildQuery({ status, sort, page, size: 10 })}`);

  const pay = async (fine: Fine) => {
    if (!window.confirm(`¿Registrar el pago de ${formatMoney(fine.amount)} de ${fine.member.full_name}?`)) return;
    try {
      await api.post(`/fines/${fine.id}/pay`);
      notify('Pago registrado');
      fines.reload();
    } catch (err) {
      notify(err instanceof ApiError ? err.message : 'Error', 'error');
    }
  };

  return (
    <>
      <PageHeader
        title={isStaff ? 'Multas' : 'Mis multas'}
        subtitle="Se generan al devolver con retraso: monto por día de atraso"
      />
      <Card>
        <div className="p-4 sm:w-60">
          <SelectField aria-label="Estado" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="pendiente">Pendientes</option>
            <option value="pagada">Pagadas</option>
            <option value="">Todas</option>
          </SelectField>
        </div>
        {fines.loading && !fines.data ? (
          <LoadingState />
        ) : fines.error ? (
          <ErrorState message={fines.error.message} onRetry={fines.reload} />
        ) : !fines.data?.items.length ? (
          <EmptyState title="No hay multas" description="¡Excelente! No hay deudas registradas con este filtro." />
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  {isStaff && <Th>Socio</Th>}
                  <Th>Libro</Th>
                  <Th>Días de retraso</Th>
                  <Th sortKey="amount" sort={sort} onSort={(k) => setSort(toggleSort(sort, k))}>Monto</Th>
                  <Th sortKey="created_at" sort={sort} onSort={(k) => setSort(toggleSort(sort, k))}>Fecha</Th>
                  <Th>Estado</Th>
                  {isStaff && <Th className="text-right">Acciones</Th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {fines.data.items.map((f) => (
                  <tr key={f.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    {isStaff && <Td>{f.member.full_name}<p className="text-xs text-slate-500">{f.member.card_number}</p></Td>}
                    <Td className="max-w-[16rem] truncate">{f.book_title}</Td>
                    <Td className="tabular-nums">{f.days_late}</Td>
                    <Td className="font-medium tabular-nums">{formatMoney(f.amount)}</Td>
                    <Td>{formatDate(f.created_at)}</Td>
                    <Td><StatusBadge status={f.status} /></Td>
                    {isStaff && (
                      <Td className="text-right">
                        {f.status === 'pendiente' && <Button size="sm" onClick={() => pay(f)}>Registrar pago</Button>}
                      </Td>
                    )}
                  </tr>
                ))}
              </tbody>
            </Table>
            <Pagination page={fines.data.page} pages={fines.data.pages} total={fines.data.total} size={fines.data.size} onChange={setPage} />
          </>
        )}
      </Card>
    </>
  );
}
