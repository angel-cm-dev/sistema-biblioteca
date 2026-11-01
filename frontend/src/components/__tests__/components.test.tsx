import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Pagination } from '../Pagination';
import { StatusBadge, statusTone } from '../StatusBadge';
import { EmptyState, ErrorState } from '../ui';

describe('Pagination', () => {
  it('muestra el rango y deshabilita "Anterior" en la primera página', () => {
    render(<Pagination page={1} pages={3} total={25} size={10} onChange={() => {}} />);
    expect(screen.getByText(/Mostrando/)).toHaveTextContent('Mostrando 1–10 de 25');
    expect(screen.getByRole('button', { name: 'Anterior' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Siguiente' })).toBeEnabled();
  });

  it('notifica el cambio de página', async () => {
    const onChange = vi.fn();
    render(<Pagination page={2} pages={3} total={25} size={10} onChange={onChange} />);
    await userEvent.click(screen.getByRole('button', { name: 'Siguiente' }));
    expect(onChange).toHaveBeenCalledWith(3);
  });

  it('calcula el último rango parcial y no se muestra sin resultados', () => {
    const { rerender, container } = render(
      <Pagination page={3} pages={3} total={25} size={10} onChange={() => {}} />,
    );
    expect(screen.getByText(/Mostrando/)).toHaveTextContent('21–25 de 25');
    rerender(<Pagination page={1} pages={0} total={0} size={10} onChange={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe('StatusBadge', () => {
  it('asigna colores semánticos por estado', () => {
    expect(statusTone('disponible')).toBe('green');
    expect(statusTone('vencido')).toBe('red');
    expect(statusTone('lista')).toBe('violet');
    expect(statusTone('desconocido')).toBe('slate');
  });

  it('renderiza la etiqueta personalizada', () => {
    render(<StatusBadge status="bloqueado" label="en riesgo" />);
    expect(screen.getByText('en riesgo')).toHaveClass('bg-rose-100');
  });
});

describe('Estados', () => {
  it('ErrorState permite reintentar', async () => {
    const onRetry = vi.fn();
    render(<ErrorState message="Servidor caído" onRetry={onRetry} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Servidor caído');
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(onRetry).toHaveBeenCalled();
  });

  it('EmptyState muestra título y descripción', () => {
    render(<EmptyState title="Sin libros" description="Agregue uno" />);
    expect(screen.getByText('Sin libros')).toBeInTheDocument();
    expect(screen.getByText('Agregue uno')).toBeInTheDocument();
  });
});
