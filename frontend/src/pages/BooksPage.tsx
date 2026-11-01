import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { Pagination } from '@/components/Pagination';
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
import { buildQuery, toggleSort } from '@/lib/query';
import { isbn as isbnRule, required, validate } from '@/lib/validation';
import type { Author, Book, Category, Page } from '@/types';

const EMPTY_FORM = { isbn: '', title: '', publisher: '', publication_year: '', category_id: '', initial_copies: '1' };

function NewBookModal({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const authors = useFetch<Author[]>(open ? '/authors' : null);
  const categories = useFetch<Category[]>(open ? '/categories' : null);
  const { notify } = useToast();
  const [form, setForm] = useState(EMPTY_FORM);
  const [authorIds, setAuthorIds] = useState<number[]>([]);
  const [newAuthor, setNewAuthor] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const close = () => {
    setForm(EMPTY_FORM);
    setAuthorIds([]);
    setErrors({});
    setFormError(null);
    onClose();
  };

  const addAuthor = async () => {
    if (newAuthor.trim().length < 2) return;
    try {
      const created = await api.post<Author>('/authors', { name: newAuthor.trim() });
      setAuthorIds((ids) => [...ids, created.id]);
      setNewAuthor('');
      authors.reload();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'No se pudo crear el autor');
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const found: Record<string, string> = validate(form, {
      isbn: [required(), isbnRule],
      title: [required()],
    });
    if (!authorIds.length) found.author_ids = 'Seleccione al menos un autor';
    setErrors(found);
    if (Object.keys(found).length) return;
    setSaving(true);
    setFormError(null);
    try {
      await api.post('/books', {
        isbn: form.isbn,
        title: form.title,
        publisher: form.publisher || null,
        publication_year: form.publication_year ? Number(form.publication_year) : null,
        category_id: form.category_id ? Number(form.category_id) : null,
        author_ids: authorIds,
        initial_copies: Number(form.initial_copies || 0),
      });
      notify('Libro registrado correctamente');
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
      title="Registrar libro"
      onClose={close}
      footer={
        <>
          <Button variant="secondary" onClick={close}>Cancelar</Button>
          <Button type="submit" form="book-form" loading={saving}>Guardar</Button>
        </>
      }
    >
      <form id="book-form" onSubmit={submit} noValidate className="space-y-4">
        {formError && <Alert>{formError}</Alert>}
        <Field label="ISBN" value={form.isbn} error={errors.isbn} hint="10 o 13 dígitos; se valida el dígito de control"
          onChange={(e) => setForm({ ...form, isbn: e.target.value })} />
        <Field label="Título" value={form.title} error={errors.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Editorial" value={form.publisher} onChange={(e) => setForm({ ...form, publisher: e.target.value })} />
          <Field label="Año" type="number" value={form.publication_year} error={errors.publication_year}
            onChange={(e) => setForm({ ...form, publication_year: e.target.value })} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectField label="Categoría" value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value })}>
            <option value="">Sin categoría</option>
            {categories.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </SelectField>
          <Field label="Ejemplares iniciales" type="number" min={0} max={50} value={form.initial_copies}
            onChange={(e) => setForm({ ...form, initial_copies: e.target.value })} />
        </div>
        <fieldset>
          <legend className="mb-1 text-sm font-medium text-slate-700 dark:text-slate-300">Autores</legend>
          <div className="max-h-36 space-y-1 overflow-y-auto rounded-lg border border-slate-300 p-2 dark:border-slate-700">
            {authors.data?.map((a) => (
              <label key={a.id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={authorIds.includes(a.id)}
                  onChange={(e) =>
                    setAuthorIds((ids) => (e.target.checked ? [...ids, a.id] : ids.filter((i) => i !== a.id)))
                  }
                />
                {a.name}
              </label>
            ))}
          </div>
          {errors.author_ids && <p className="mt-1 text-xs text-rose-600">{errors.author_ids}</p>}
          <div className="mt-2 flex gap-2">
            <input
              className="block w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
              placeholder="Nuevo autor…"
              value={newAuthor}
              onChange={(e) => setNewAuthor(e.target.value)}
            />
            <Button variant="secondary" size="sm" onClick={addAuthor}>Agregar</Button>
          </div>
        </fieldset>
      </form>
    </Modal>
  );
}

export function BooksPage() {
  const { isStaff } = useAuth();
  const { notify } = useToast();
  const [q, setQ] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [available, setAvailable] = useState('');
  const [sort, setSort] = useState('title');
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const search = useDebounce(q);

  const categories = useFetch<Category[]>('/categories');
  const books = useFetch<Page<Book>>(
    `/books${buildQuery({ q: search, category_id: categoryId, available, sort, page, size: 10 })}`,
  );

  const reserve = async (book: Book) => {
    try {
      const r = await api.post<{ queue_position: number }>('/reservations', { book_id: book.id });
      notify(`Reserva registrada. Posición en la cola: ${r.queue_position}`);
      books.reload();
    } catch (err) {
      notify(err instanceof ApiError ? err.message : 'No se pudo reservar', 'error');
    }
  };

  const resetPage = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v);
    setPage(1);
  };

  return (
    <>
      <PageHeader
        title="Catálogo"
        subtitle="Busque por título, ISBN o autor"
        actions={isStaff && <Button onClick={() => setCreating(true)}>Nuevo libro</Button>}
      />
      <Card>
        <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
          <SearchInput placeholder="Buscar…" value={q} onChange={(e) => resetPage(setQ)(e.target.value)} aria-label="Buscar libros" />
          <div className="grid grid-cols-2 gap-3 sm:flex">
            <SelectField aria-label="Categoría" value={categoryId} onChange={(e) => resetPage(setCategoryId)(e.target.value)}>
              <option value="">Todas las categorías</option>
              {categories.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </SelectField>
            <SelectField aria-label="Disponibilidad" value={available} onChange={(e) => resetPage(setAvailable)(e.target.value)}>
              <option value="">Todos</option>
              <option value="true">Con disponibles</option>
              <option value="false">Sin disponibles</option>
            </SelectField>
          </div>
        </div>
        {books.loading && !books.data ? (
          <LoadingState />
        ) : books.error ? (
          <ErrorState message={books.error.message} onRetry={books.reload} />
        ) : !books.data?.items.length ? (
          <EmptyState title="No se encontraron libros" description="Pruebe con otros términos o filtros." />
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  <Th sortKey="title" sort={sort} onSort={(k) => setSort(toggleSort(sort, k))}>Título</Th>
                  <Th>Autores</Th>
                  <Th>Categoría</Th>
                  <Th sortKey="publication_year" sort={sort} onSort={(k) => setSort(toggleSort(sort, k))}>Año</Th>
                  <Th>Disponibles</Th>
                  <Th className="text-right">Acciones</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {books.data.items.map((b) => (
                  <tr key={b.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <Td>
                      <Link to={`/libros/${b.id}`} className="font-medium text-brand-700 hover:underline dark:text-brand-400">
                        {b.title}
                      </Link>
                      <p className="text-xs text-slate-500">ISBN {b.isbn}</p>
                    </Td>
                    <Td className="max-w-[16rem] truncate">{b.authors.map((a) => a.name).join(', ')}</Td>
                    <Td>{b.category?.name ?? '—'}</Td>
                    <Td>{b.publication_year ?? '—'}</Td>
                    <Td>
                      <span className={b.available_copies ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}>
                        {b.available_copies}
                      </span>{' '}
                      / {b.total_copies}
                    </Td>
                    <Td className="text-right">
                      {!isStaff && b.available_copies === 0 && b.total_copies > 0 ? (
                        <Button size="sm" variant="secondary" onClick={() => reserve(b)}>Reservar</Button>
                      ) : (
                        <Link to={`/libros/${b.id}`} className="text-sm text-slate-500 hover:underline">Ver detalle</Link>
                      )}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <Pagination page={books.data.page} pages={books.data.pages} total={books.data.total} size={books.data.size} onChange={setPage} />
          </>
        )}
      </Card>
      {isStaff && <NewBookModal open={creating} onClose={() => setCreating(false)} onCreated={books.reload} />}
    </>
  );
}
