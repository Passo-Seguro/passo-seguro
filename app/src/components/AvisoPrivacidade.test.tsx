import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { AvisoPrivacidade } from './AvisoPrivacidade';

function abrir() {
  return render(
    <MemoryRouter>
      <AvisoPrivacidade />
    </MemoryRouter>,
  );
}

describe('Aviso de privacidade', () => {
  it('aparece na primeira abertura dizendo o que é coletado e por quê', () => {
    abrir();
    const aviso = screen.getByRole('region', { name: 'Sua privacidade' });
    expect(aviso).toHaveTextContent(/foto/);
    expect(aviso).toHaveTextContent(/local/);
    expect(aviso).toHaveTextContent(/texto/);
    expect(aviso).toHaveTextContent(/número anônimo/);
    expect(aviso).toHaveTextContent(/Não pedimos nome, e-mail nem login/);
  });

  it('some depois do "Entendi" e não volta na próxima abertura', async () => {
    const { unmount } = abrir();
    await userEvent.click(screen.getByRole('button', { name: 'Entendi' }));
    expect(screen.queryByRole('region', { name: 'Sua privacidade' })).not.toBeInTheDocument();
    unmount();
    abrir();
    expect(screen.queryByRole('region', { name: 'Sua privacidade' })).not.toBeInTheDocument();
  });
});
