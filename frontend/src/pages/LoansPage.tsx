import { useState } from 'react';
import type { FormEvent } from 'react';
import { Pagination } from '@/components/Pagination';
import { StatusBadge } from '@/components/StatusBadge';
import {
  Alert,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  LoadingState,
  Modal,
  PageHeader,
  SearchInput,
  SelectField,
  Table,
  Td,
  Th,
} from '@/components/ui';
import { useAuth } from '@/context/AuthContext';
import { useToast } from '@/context/ToastContext';
import { useDebounce } from '@/hooks/useDebounce';
import { useFetch } from '@/hooks/useFetch';
import { api, ApiError } from '@/lib/api';
import { formatDate, formatMoney } from '@/lib/format';
import { buildQuery, toggleSort } from '@/lib/query';
import { required, validate } from '@/lib/validation';
import type { Loan, Page, ReturnResult } from '@/types';

function NewLoanModal({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const { notify } = useToast();
  const [form, setForm] = useState({ card_number: '', inventory_code: '' });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const close = () => {
    setForm({ card_number: '', inventory_code: '' });
    setErrors({});
    setFormError(null);
    onClose();
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const found = validate(form, {
      card_number: [required('Ingrese el carnet del socio')],
      inventory_code: [required('Escanee o ingrese el código del ejemplar')],
    }) as Record<string, string>;
    setErrors(found);
    if (Object.keys(found).length) return;
    setSaving(true);
    setFormError(null);
    try {
      const loan = await api.post<Loan>('/loans', form);
      notify(`Préstamo registrado: "${loan.book.title}" vence el ${formatDate(loan.due_date)}`);
      onCreated();
      close();
    } catch (err) {
      // Las reglas de negocio (límite, bloqueo por deuda, apartado) llegan como ProblemDetails.
      setFormError(err instanceof ApiError ? err.message : 'No se pudo registrar el préstamo');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      title="Registrar préstamo"
      onClose={close}
      footer={
        <>
          <Button variant="secondary" onClick={close}>Cancelar</Button>
          <Button type="submit" form="loan-form" loading={saving}>Prestar</Button>
        </>
      }
    >
      <form id="loan-form" onSubmit={submit} noValidate className="space-y-4">
        {formError && <Alert>{formError}</Alert>}
        <Field label="Carnet del socio" placeholder="BIB-2026-0001" value={form.card_number} error={errors.card_number}
          onChange={(e) => setForm({ ...form, card_number: e.target.value })} autoFocus />
        <Field label="Código de inventario" placeholder="INV-00001-001" value={form.inventory_code} error={errors.inventory_code}
          hint="Compatible con lector de código de barras"
          onChange={(e) => setForm({ ...form, inventory_code: e.target.value })} />
      </form>
    </Modal>
  );
}

export function LoansPage() {
  const { isStaff } = useAuth();
  const { notify } = useToast();
  const [q, setQ] = useState('');
  const [filter, setFilter] = useState('activo');
  const [sort, setSort] = useState('-loaned_at');
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState<number | null>(null);
  const search = useDebounce(q);

  const params = {
    q: search,
    status: filter === 'vencido' ? 'activo' : filter,
    overdue: filter === 'vencido' ? true : undefined,
    sort,
    page,
    size: 10,
  };
  const loans = useFetch<Page<Loan>>(`/loans${buildQuery(params)}`);

  const doReturn = async (loan: Loan) => {
    setBusy(loan.id);
    try {
      const r = await api.post<ReturnResult>(`/loans/${loan.id}/return`);
      const parts = ['Devolución registrada'];
      if (r.fine) parts.push(`multa de ${formatMoney(r.fine.amount)} por ${r.fine.days_late} día(s) de retraso`);
      if (r.reserved_for) parts.push(`ejemplar apartado para ${r.reserved_for.member.full_name}`);
      notify(parts.join(' · '), r.fine ? 'info' : 'success');
      loans.reload();
    } catch (err) {
      notify(err instanceof ApiError ? err.message : 'Error', 'error');
    } finally {
      setBusy(null);
    }
  };

  const doRenew = async (loan: Loan) => {
    setBusy(loan.id);
    try {
      const r = await api.post<Loan>(`/loans/${loan.id}/renew`);
      notify(`Renovado hasta el ${formatDate(r.due_date)}`);
      loans.reload();
    } catch (err) {
      notify(err instanceof ApiError ? err.message : 'Error', 'error');
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <PageHeader
        title={isStaff ? 'Préstamos' : 'Mis préstamos'}
        subtitle={isStaff ? 'Préstamos, devoluciones y renovaciones' : 'Consulte vencimientos y renueve sus préstamos'}
        actions={isStaff && <Button onClick={() => setCreating(true)}>Nuevo préstamo</Button>}
      />
      <Card>
        <div className="flex flex-col gap-3 p-4 sm:flex-row">
          {isStaff && (
            <SearchInput placeholder="Libro, socio, carnet o código" value={q} aria-label="Buscar préstamos"
              onChange={(e) => { setQ(e.target.value); setPage(1); }} />
          )}
          <SelectField aria-label="Estado" value={filter} onChange={(e) => { setFilter(e.target.value); setPage(1); }}>
            <option value="activo">Activos</option>
            <option value="vencido">Vencidos</option>
            <option value="devuelto">Devueltos</option>
            <option value="">Todos</option>
          </SelectField>
        </div>
        {loans.loading && !loans.data ? (
          <LoadingState />
        ) : loans.error ? (
          <ErrorState message={loans.error.message} onRetry={loans.reload} />
        ) : !loans.data?.items.length ? (
          <EmptyState title="No hay préstamos para mostrar" />
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  <Th>Libro</Th>
                  {isStaff && <Th>Socio</Th>}
                  <Th sortKey="loaned_at" sort={sort} onSort={(k) => setSort(toggleSort(sort, k))}>Prestado</Th>
                  <Th sortKey="due_date" sort={sort} onSort={(k) => setSort(toggleSort(sort, k))}>Vence</Th>
                  <Th>Renov.</Th>
                  <Th>Estado</Th>
                  <Th className="text-right">Acciones</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {loans.data.items.map((l) => (
                  <tr key={l.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <Td>
                      <p className="max-w-[16rem] truncate font-medium">{l.book.title}</p>
                      <p className="font-mono text-xs text-slate-500">{l.physical_copy.inventory_code}</p>
                    </Td>
                    {isStaff && (
                      <Td>
                        <p>{l.member.full_name}</p>
                        <p className="text-xs text-slate-500">{l.member.card_number}</p>
                      </Td>
                    )}
                    <Td>{formatDate(l.loaned_at)}</Td>
                    <Td>
                      {formatDate(l.due_date)}
                      {l.is_overdue && <p className="text-xs text-rose-600">{l.days_overdue} día(s) de retraso</p>}
                    </Td>
                    <Td className="tabular-nums">{l.renewals_count}</Td>
                    <Td><StatusBadge status={l.is_overdue ? 'vencido' : l.status} /></Td>
                    <Td className="space-x-2 text-right">
                      {l.status === 'activo' && (
                        <>
                          {!l.is_overdue && (
                            <Button size="sm" variant="secondary" disabled={busy === l.id} onClick={() => doRenew(l)}>Renovar</Button>
                          )}
                          {isStaff && (
                            <Button size="sm" disabled={busy === l.id} onClick={() => doReturn(l)}>Devolver</Button>
                          )}
                        </>
                      )}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <Pagination page={loans.data.page} pages={loans.data.pages} total={loans.data.total} size={loans.data.size} onChange={setPage} />
          </>
        )}
      </Card>
      {isStaff && <NewLoanModal open={creating} onClose={() => setCreating(false)} onCreated={loans.reload} />}
    </>
  );
}
