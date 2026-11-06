import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { simularApi, simularSemRede } from '../test/api-falsa';
import { Pergunte, urlSegura } from './Pergunte';

function abrir() {
  return render(
    <MemoryRouter>
      <Pergunte />
    </MemoryRouter>,
  );
}

const comFontes = {
  resposta: 'Em geral, o cuidado com o piso é de quem é dono do imóvel em frente.',
  fontes: [
    { titulo: 'Cartilha de calçadas (exemplo)', url: 'https://documentos.exemplo.invalid/cartilha.pdf' },
    { titulo: 'Sem link' },
    { titulo: 'Link perigoso', url: 'javascript:alert(1)' },
  ],
  confianca: 0.86,
  recusou: false,
};
const recusa = {
  resposta: 'Eu só consigo ajudar com problemas em calçadas de São Paulo.',
  fontes: [],
  confianca: 0.1,
  recusou: true,
};

afterEach(() => vi.unstubAllGlobals());

async function perguntar(texto: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText('Sua pergunta'), texto);
  await user.click(screen.getByRole('button', { name: 'Enviar' }));
  return user;
}

describe('Pergunte', () => {
  it('mostra a resposta com fontes clicáveis que abrem em nova aba com rel="noopener"', async () => {
    const { chamadas } = simularApi([{ metodo: 'POST', caminho: '/assistente', corpo: comFontes }]);
    abrir();
    await perguntar('Quem conserta a calçada?');

    const conversa = screen.getByRole('log', { name: 'Conversa com o assistente' });
    expect(await within(conversa).findByText(/cuidado com o piso/)).toBeInTheDocument();
    expect(within(conversa).getByText('Quem conserta a calçada?')).toBeInTheDocument();

    const link = within(conversa).getByRole('link', { name: /Cartilha de calçadas/ });
    expect(link).toHaveAttribute('href', 'https://documentos.exemplo.invalid/cartilha.pdf');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link.getAttribute('rel')).toContain('noopener');
    expect(link).toHaveTextContent('abre em uma nova aba');

    // fonte sem url vira texto; url com esquema perigoso não vira link
    expect(within(conversa).getByText('Sem link').closest('a')).toBeNull();
    expect(within(conversa).getByText('Link perigoso').closest('a')).toBeNull();
    expect(JSON.parse(chamadas[0].corpoTexto)).toEqual({ pergunta: 'Quem conserta a calçada?' });
  });

  it('a recusa (recusou=true) aparece com o mesmo destaque da resposta normal', async () => {
    simularApi([{ metodo: 'POST', caminho: '/assistente', corpo: recusa }]);
    abrir();
    await perguntar('Qual ação comprar?');

    const texto = await screen.findByText(/Eu só consigo ajudar com problemas em calçadas/);
    const balao = texto.closest('article')!;
    expect(balao).toHaveClass('balao-assistente');
    expect(balao).not.toHaveClass('balao-falha');
    expect(balao.className).toBe('balao balao-assistente'); // exatamente as mesmas classes de uma resposta normal
  });

  it('se a API falhar, dá uma mensagem amigável e o resto do app segue (link para reportar)', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    simularSemRede();
    abrir();
    await perguntar('Oi');

    const msg = await screen.findByText(/Não consegui falar com o assistente agora/);
    expect(msg).toHaveTextContent(/o resto do app continua funcionando/i);
    expect(screen.getByRole('link', { name: 'Registrar um problema agora' })).toHaveAttribute('href', '/reportar');
    // dá para perguntar de novo
    expect(screen.getByRole('button', { name: 'Enviar' })).toBeDisabled(); // campo vazio
    expect(screen.getByLabelText('Sua pergunta')).toBeEnabled();
  });

  it('erro 5xx da API também vira mensagem amigável', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    simularApi([{ metodo: 'POST', caminho: '/assistente', status: 500, corpo: { codigo: 'erro', mensagem: 'x' } }]);
    abrir();
    await perguntar('Oi');
    expect(await screen.findByText(/Não consegui falar com o assistente agora/)).toBeInTheDocument();
  });

  it('perguntas sugeridas enviam a pergunta com um toque', async () => {
    const { chamadas } = simularApi([{ metodo: 'POST', caminho: '/assistente', corpo: comFontes }]);
    abrir();
    await userEvent.click(screen.getByRole('button', { name: /Quem conserta uma calçada quebrada/ }));
    await screen.findByText(/cuidado com o piso/);
    expect(JSON.parse(chamadas[0].corpoTexto).pergunta).toMatch(/Quem conserta uma calçada quebrada/);
    expect(screen.queryByText('Por onde começar')).not.toBeInTheDocument();
  });

  it('não envia pergunta vazia e limita a 500 caracteres', () => {
    abrir();
    expect(screen.getByRole('button', { name: 'Enviar' })).toBeDisabled();
    expect(screen.getByLabelText('Sua pergunta')).toHaveAttribute('maxlength', '500');
  });

  it('a conversa é anunciada por leitor de tela (role=log, aria-live=polite)', () => {
    abrir();
    expect(screen.getByRole('log')).toHaveAttribute('aria-live', 'polite');
  });
});

describe('urlSegura', () => {
  it('aceita só http e https', () => {
    expect(urlSegura('https://exemplo.invalid/a')).toBe('https://exemplo.invalid/a');
    expect(urlSegura('http://exemplo.invalid/')).toBe('http://exemplo.invalid/');
    expect(urlSegura('javascript:alert(1)')).toBeNull();
    expect(urlSegura('data:text/html,x')).toBeNull();
    expect(urlSegura('nao é url')).toBeNull();
    expect(urlSegura(undefined)).toBeNull();
  });
});
