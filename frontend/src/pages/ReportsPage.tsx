import { useState } from 'react';
import { StatusBadge } from '@/components/StatusBadge';
import { Card, EmptyState, ErrorState, Field, LoadingState, PageHeader, Table, Td, Th } from '@/components/ui';
import { useFetch } from '@/hooks/useFetch';
import { formatMoney } from '@/lib/format';
import { buildQuery } from '@/lib/query';
import type { Delinquent, TopBook } from '@/types';

export function ReportsPage() {
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const invalidRange = Boolean(from && to && from > to);
  const top = useFetch<TopBook[]>(
    invalidRange ? null : `/reports/most-borrowed${buildQuery({ limit: 10, date_from: from, date_to: to })}`,
  );
  const late = useFetch<Delinquent[]>('/reports/delinquency');

  return (
    <>
      <PageHeader title="Reportes" subtitle="Circulación y morosidad" />
      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <div className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row sm:items-end sm:justify-between dark:border-slate-800">
            <h2 className="font-semibold">Libros más prestados</h2>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Desde" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
              <Field label="Hasta" type="date" value={to} error={invalidRange ? 'Rango inválido' : undefined} onChange={(e) => setTo(e.target.value)} />
            </div>
          </div>
          {top.loading ? (
            <LoadingState />
          ) : top.error ? (
            <ErrorState message={top.error.message} onRetry={top.reload} />
          ) : !top.data?.length ? (
            <EmptyState title="Sin préstamos en el periodo" />
          ) : (
            <Table>
              <thead>
                <tr><Th>#</Th><Th>Título</Th><Th>ISBN</Th><Th className="text-right">Préstamos</Th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {top.data.map((b, i) => (
                  <tr key={b.book_id}>
                    <Td className="text-slate-500">{i + 1}</Td>
                    <Td className="max-w-[18rem] truncate font-medium">{b.title}</Td>
                    <Td className="font-mono text-xs">{b.isbn}</Td>
                    <Td className="text-right tabular-nums">{b.loans}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>

        <Card>
          <div className="border-b border-slate-200 p-4 dark:border-slate-800">
            <h2 className="font-semibold">Morosidad</h2>
            <p className="text-xs text-slate-500">Socios con deuda pendiente o préstamos vencidos</p>
          </div>
          {late.loading ? (
            <LoadingState />
          ) : late.error ? (
            <ErrorState message={late.error.message} onRetry={late.reload} />
          ) : !late.data?.length ? (
            <EmptyState title="No hay socios morosos" />
          ) : (
            <Table>
              <thead>
                <tr><Th>Socio</Th><Th>Deuda</Th><Th>Vencidos</Th><Th>Máx. días</Th><Th>Estado</Th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {late.data.map((d) => (
                  <tr key={d.member.id}>
                    <Td>
                      <p className="font-medium">{d.member.full_name}</p>
                      <p className="text-xs capitalize text-slate-500">{d.member.card_number} · {d.member.member_type}</p>
                    </Td>
                    <Td className="tabular-nums">{formatMoney(d.pending_debt)}</Td>
                    <Td className="tabular-nums">{d.overdue_loans}</Td>
                    <Td className="tabular-nums">{d.max_days_overdue}</Td>
                    <Td><StatusBadge status={d.is_blocked ? 'bloqueado' : 'pendiente'} label={d.is_blocked ? 'bloqueado' : 'en riesgo'} /></Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
      </div>
    </>
  );
}
