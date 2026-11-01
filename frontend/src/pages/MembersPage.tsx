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
import { useToast } from '@/context/ToastContext';
import { useDebounce } from '@/hooks/useDebounce';
import { useFetch } from '@/hooks/useFetch';
import { api, ApiError } from '@/lib/api';
import { formatDate, formatMoney } from '@/lib/format';
import { buildQuery, toggleSort } from '@/lib/query';
import { dni, email, minLength, required, strongPassword, validate } from '@/lib/validation';
import type { Member, MemberStatus, Page } from '@/types';

const EMPTY = { full_name: '', email: '', document_id: '', phone: '', member_type: 'estudiante', password: '' };

function NewMemberModal({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const { notify } = useToast();
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const set = (k: keyof typeof EMPTY) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  const close = () => {
    setForm(EMPTY);
    setErrors({});
    setFormError(null);
    onClose();
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const found = validate(form, {
      full_name: [required(), minLength(3)],
      email: [required(), email],
      document_id: [required(), dni],
      password: [strongPassword],
    }) as Record<string, string>;
    setErrors(found);
    if (Object.keys(found).length) return;
    setSaving(true);
    setFormError(null);
    try {
      const m = await api.post<Member>('/members', {
        ...form,
        phone: form.phone || null,
        password: form.password || null,
      });
      notify(`Socio registrado con carnet ${m.card_number}`);
      onCreated();
      close();
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.fieldErrors);
        setFormError(err.message);
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      title="Registrar socio"
      onClose={close}
      footer={
        <>
          <Button variant="secondary" onClick={close}>Cancelar</Button>
          <Button type="submit" form="member-form" loading={saving}>Guardar</Button>
        </>
      }
    >
      <form id="member-form" onSubmit={submit} noValidate className="space-y-4">
        {formError && <Alert>{formError}</Alert>}
        <Field label="Nombre completo" value={form.full_name} error={errors.full_name} onChange={set('full_name')} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Correo" type="email" value={form.email} error={errors.email} onChange={set('email')} />
          <Field label="DNI / CE" value={form.document_id} error={errors.document_id} onChange={set('document_id')} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Teléfono" value={form.phone} error={errors.phone} onChange={set('phone')} />
          <SelectField label="Tipo de socio" value={form.member_type} onChange={set('member_type')}>
            <option value="estudiante">Estudiante (3 libros · 14 días)</option>
            <option value="docente">Docente (10 libros · 30 días)</option>
            <option value="externo">Externo (2 libros · 7 días)</option>
          </SelectField>
        </div>
        <Field
          label="Contraseña de acceso (opcional)"
          type="password"
          value={form.password}
          error={errors.password}
          hint="Si la indica, el socio podrá ingresar al sistema con su correo"
          onChange={set('password')}
        />
      </form>
    </Modal>
  );
}

function StatusModal({ memberId, onClose }: { memberId: number | null; onClose: () => void }) {
  const status = useFetch<MemberStatus>(memberId ? `/members/${memberId}/status` : null);
  const s = status.data;
  return (
    <Modal open={memberId !== null} title="Situación del socio" onClose={onClose}>
      {status.loading || !s ? (
        <LoadingState />
      ) : (
        <div className="space-y-3 text-sm">
          <p className="text-base font-medium">{s.member.full_name} <span className="text-slate-500">({s.member.card_number})</span></p>
          <dl className="grid grid-cols-2 gap-2">
            <dt className="text-slate-500">Préstamos activos</dt><dd>{s.active_loans} / {s.policy.max_active_loans}</dd>
            <dt className="text-slate-500">Vencidos</dt><dd>{s.overdue_loans}</dd>
            <dt className="text-slate-500">Deuda pendiente</dt><dd>{formatMoney(s.pending_debt)}</dd>
            <dt className="text-slate-500">Días por préstamo</dt><dd>{s.policy.loan_days}</dd>
            <dt className="text-slate-500">Renovaciones máx.</dt><dd>{s.policy.max_renewals}</dd>
          </dl>
          {s.block_reasons.length > 0 ? (
            <Alert>{s.block_reasons.join('. ')}</Alert>
          ) : (
            <Alert kind="info">{s.can_borrow ? 'Puede recibir préstamos.' : 'Alcanzó su límite de préstamos.'}</Alert>
          )}
        </div>
      )}
    </Modal>
  );
}

export function MembersPage() {
  const [q, setQ] = useState('');
  const [type, setType] = useState('');
  const [sort, setSort] = useState('full_name');
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const [statusOf, setStatusOf] = useState<number | null>(null);
  const search = useDebounce(q);
  const members = useFetch<Page<Member>>(`/members${buildQuery({ q: search, member_type: type, sort, page, size: 10 })}`);

  return (
    <>
      <PageHeader title="Socios" subtitle="Registro de socios y su situación" actions={<Button onClick={() => setCreating(true)}>Nuevo socio</Button>} />
      <Card>
        <div className="flex flex-col gap-3 p-4 sm:flex-row">
          <SearchInput placeholder="Nombre, carnet, DNI o correo" value={q} aria-label="Buscar socios"
            onChange={(e) => { setQ(e.target.value); setPage(1); }} />
          <SelectField aria-label="Tipo de socio" value={type} onChange={(e) => { setType(e.target.value); setPage(1); }}>
            <option value="">Todos los tipos</option>
            <option value="estudiante">Estudiante</option>
            <option value="docente">Docente</option>
            <option value="externo">Externo</option>
          </SelectField>
        </div>
        {members.loading && !members.data ? (
          <LoadingState />
        ) : members.error ? (
          <ErrorState message={members.error.message} onRetry={members.reload} />
        ) : !members.data?.items.length ? (
          <EmptyState title="No hay socios que coincidan" />
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  <Th sortKey="card_number" sort={sort} onSort={(k) => setSort(toggleSort(sort, k))}>Carnet</Th>
                  <Th sortKey="full_name" sort={sort} onSort={(k) => setSort(toggleSort(sort, k))}>Nombre</Th>
                  <Th>Documento</Th>
                  <Th sortKey="member_type" sort={sort} onSort={(k) => setSort(toggleSort(sort, k))}>Tipo</Th>
                  <Th sortKey="created_at" sort={sort} onSort={(k) => setSort(toggleSort(sort, k))}>Alta</Th>
                  <Th>Estado</Th>
                  <Th className="text-right">Acciones</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {members.data.items.map((m) => (
                  <tr key={m.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <Td className="font-mono text-xs">{m.card_number}</Td>
                    <Td>
                      <p className="font-medium">{m.full_name}</p>
                      <p className="text-xs text-slate-500">{m.email}</p>
                    </Td>
                    <Td>{m.document_id}</Td>
                    <Td className="capitalize">{m.member_type}</Td>
                    <Td>{formatDate(m.created_at)}</Td>
                    <Td><StatusBadge status={m.is_active ? 'activo' : 'cancelada'} label={m.is_active ? 'activo' : 'inactivo'} /></Td>
                    <Td className="text-right">
                      <Button size="sm" variant="ghost" onClick={() => setStatusOf(m.id)}>Ver situación</Button>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <Pagination page={members.data.page} pages={members.data.pages} total={members.data.total} size={members.data.size} onChange={setPage} />
          </>
        )}
      </Card>
      <NewMemberModal open={creating} onClose={() => setCreating(false)} onCreated={members.reload} />
      <StatusModal memberId={statusOf} onClose={() => setStatusOf(null)} />
    </>
  );
}
