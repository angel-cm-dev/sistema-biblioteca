# ADR 0002: Reservas FIFO con apartado temporal y reloj inyectable

- **Estado:** aceptada
- **Fecha:** 2026-11

## Contexto

Cuando todos los ejemplares de un libro están prestados, los socios deben poder hacer cola. Hay que decidir qué pasa al devolverse un ejemplar, cuánto tiempo se guarda y cómo probar reglas que dependen del paso de los días.

## Decisión

1. **Se reserva el libro, no el ejemplar**, y solo si no hay ejemplares disponibles.
2. La cola es **FIFO** por `created_at, id`.
3. Toda vez que un ejemplar vuelve a circular, un único método (`ReservationService.route_copy`) decide su destino: si hay cola, queda `apartado` para el primero durante `RESERVATION_HOLD_DAYS`; si no, `disponible`. Esto cubre devolución, alta de ejemplar, fin de mantenimiento, cancelación y expiración con el mismo código.
4. Un ejemplar apartado **solo se presta al socio que lo reservó**.
5. Las renovaciones se **bloquean** si hay reservas pendientes del libro.
6. La **expiración** de apartados se ejecuta de forma perezosa (antes de prestar o reservar) y mediante `POST /reservations/expire-holds`. No se añade un scheduler para mantener el despliegue simple.
7. El tiempo se obtiene de un **`Clock` inyectado** (`SystemClock` en producción, `FixedClock` en pruebas y en el seed).

## Consecuencias

- (+) Comportamiento justo y predecible; un solo punto de verdad para el destino de un ejemplar.
- (+) Las pruebas avanzan el tiempo con `clock.advance(days=4)`; el seed simula 45 días usando los mismos servicios.
- (-) Si nadie presta ni reserva, un apartado vencido sigue figurando como `lista` hasta que se ejecute la expiración. En producción se recomienda un cron que llame al endpoint (está en el roadmap).
