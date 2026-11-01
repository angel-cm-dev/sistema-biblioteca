import { Link } from 'react-router-dom';
import { StatusBadge } from '@/components/StatusBadge';
import { Alert, Card, EmptyState, ErrorState, KpiCard, LoadingState, PageHeader } from '@/components/ui';
import { useAuth } from '@/context/AuthContext';
import { useFetch } from '@/hooks/useFetch';
import { formatDate, formatMoney } from '@/lib/format';
import type { Delinquent, Loan, MemberStatus, Page, Summary, TopBook } from '@/types';

function StaffDashboard() {
  const summary = useFetch<Summary>('/reports/summary');
  const top = useFetch<TopBook[]>('/reports/most-borrowed?limit=5');
  const late = useFetch<Delinquent[]>('/reports/delinquency');

  if (summary.loading) return <LoadingState />;
  if (summary.error || !summary.data)
    return <ErrorState message={summary.error?.message ?? 'Sin datos'} onRetry={summary.reload} />;
  const s = summary.data;
  const maxLoans = Math.max(1, ...(top.data ?? []).map((b) => b.loans));

  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Títulos en catálogo" value={s.books} hint={`${s.copies} ejemplares físicos`} />
        <KpiCard
          label="Ejemplares disponibles"
          value={s.available_copies}
          tone="success"
          hint={`${Math.round((s.available_copies / Math.max(s.copies, 1)) * 100)}% del total`}
        />
        <KpiCard label="Préstamos activos" value={s.active_loans} hint={`${s.members} socios activos`} />
        <KpiCard
          label="Préstamos vencidos"
          value={s.overdue_loans}
          tone={s.overdue_loans ? 'danger' : 'default'}
          hint="Requieren seguimiento"
        />
        <KpiCard label="Reservas abiertas" value={s.pending_reservations} tone="warning" />
        <KpiCard label="Multas por cobrar" value={formatMoney(s.pending_fines)} tone="warning" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <div className="border-b border-slate-200 px-5 py-4 dark:border-slate-800">
            <h2 className="font-semibold">Libros más prestados</h2>
          </div>
          {top.loading ? (
            <LoadingState />
          ) : !top.data?.length ? (
            <EmptyState title="Aún no hay préstamos registrados" />
          ) : (
            <ul className="space-y-3 p-5">
              {top.data.map((b) => (
                <li key={b.book_id}>
                  <div className="mb-1 flex justify-between text-sm">
                    <Link to={`/libros/${b.book_id}`} className="truncate font-medium hover:underline">
                      {b.title}
                    </Link>
                    <span className="tabular-nums text-slate-500">{b.loans}</span>
                  </div>
                  <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-800">
                    <div className="h-2 rounded-full bg-brand-500" style={{ width: `${(b.loans / maxLoans) * 100}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4 dark:border-slate-800">
            <h2 className="font-semibold">Socios con morosidad</h2>
            <Link to="/reportes" className="text-sm text-brand-600 hover:underline dark:text-brand-400">
              Ver reporte
            </Link>
          </div>
          {late.loading ? (
            <LoadingState />
          ) : !late.data?.length ? (
            <EmptyState title="No hay socios morosos" description="Todos los socios están al día" />
          ) : (
            <ul className="divide-y divide-slate-200 dark:divide-slate-800">
              {late.data.slice(0, 5).map((d) => (
                <li key={d.member.id} className="flex items-center justify-between gap-3 px-5 py-3 text-sm">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{d.member.full_name}</p>
                    <p className="text-xs text-slate-500">
                      {d.member.card_number} · {d.overdue_loans} vencido(s)
                    </p>
                  </div>
                  <span className="font-medium tabular-nums text-rose-600 dark:text-rose-400">
                    {formatMoney(d.pending_debt)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}

function MemberDashboard() {
  const status = useFetch<MemberStatus>('/members/me/status');
  const loans = useFetch<Page<Loan>>('/loans?status=activo&size=5');

  if (status.loading) return <LoadingState />;
  if (status.error || !status.data)
    return <ErrorState message={status.error?.message ?? 'Sin datos'} onRetry={status.reload} />;
  const s = status.data;

  return (
    <>
      {s.is_blocked && (
        <div className="mb-6">
          <Alert>
            <p className="font-medium">Su cuenta tiene restricciones:</p>
            <ul className="ml-5 mt-1 list-disc">
              {s.block_reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </Alert>
        </div>
      )}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Carnet" value={<span className="text-xl">{s.member.card_number}</span>} hint={`Socio ${s.member.member_type}`} />
        <KpiCard
          label="Préstamos activos"
          value={`${s.active_loans} / ${s.policy.max_active_loans}`}
          hint={`${s.policy.loan_days} días por préstamo`}
        />
        <KpiCard label="Vencidos" value={s.overdue_loans} tone={s.overdue_loans ? 'danger' : 'success'} />
        <KpiCard label="Deuda pendiente" value={formatMoney(s.pending_debt)} tone={Number(s.pending_debt) > 0 ? 'warning' : 'success'} />
      </div>
      <Card className="mt-6">
        <div className="border-b border-slate-200 px-5 py-4 dark:border-slate-800">
          <h2 className="font-semibold">Mis préstamos activos</h2>
        </div>
        {loans.loading ? (
          <LoadingState />
        ) : !loans.data?.items.length ? (
          <EmptyState title="No tiene préstamos activos" description="Explore el catálogo para encontrar su próxima lectura." />
        ) : (
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {loans.data.items.map((l) => (
              <li key={l.id} className="flex items-center justify-between gap-3 px-5 py-3 text-sm">
                <div className="min-w-0">
                  <p className="truncate font-medium">{l.book.title}</p>
                  <p className="text-xs text-slate-500">Vence el {formatDate(l.due_date)}</p>
                </div>
                <StatusBadge status={l.is_overdue ? 'vencido' : l.status} />
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}

export function DashboardPage() {
  const { user, isStaff } = useAuth();
  return (
    <>
      <PageHeader
        title={`Hola, ${user?.full_name.split(' ')[0] ?? ''}`}
        subtitle={isStaff ? 'Resumen general de la biblioteca' : 'Su actividad en la biblioteca'}
      />
      {isStaff ? <StaffDashboard /> : <MemberDashboard />}
    </>
  );
}
