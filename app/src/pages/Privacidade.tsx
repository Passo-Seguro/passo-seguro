import { Link } from 'react-router';
import { Pagina } from '../components/Pagina';

export function Privacidade() {
  return (
    <Pagina titulo="Privacidade">
      <h2>O que guardamos</h2>
      <ul>
        <li>
          <strong>A foto</strong> que você tira ou escolhe.
        </li>
        <li>
          <strong>O local do problema</strong>. No mapa público ele aparece arredondado, a cerca de 100 metros.
        </li>
        <li>
          <strong>O texto</strong> que você escrever, se escrever. Não digite telefone, CPF nem nomes.
        </li>
        <li>
          <strong>Um número anônimo</strong> criado neste aparelho. Ele só serve para você ver e corrigir os seus
          relatos. O servidor guarda apenas uma versão embaralhada dele e nunca o mostra a ninguém.
        </li>
      </ul>

      <h2>Para que usamos</h2>
      <p>
        Para identificar o tipo de problema, encaminhá-lo à subprefeitura responsável, mostrar o andamento para você e
        mostrar no mapa onde estão os problemas da cidade.
      </p>

      <h2>O que não pedimos</h2>
      <p>Não pedimos nome, e-mail, telefone nem login. Você usa o app sem criar conta.</p>

      <h2>Sua localização</h2>
      <p>
        O app só usa o GPS quando você pede, ao reportar ou ao tocar em “Usar minha localização”. Se você negar, é só
        tocar no mapa para marcar o lugar.
      </p>

      <p>
        <Link to="/" className="botao botao-secundario">
          Voltar ao mapa
        </Link>
      </p>
    </Pagina>
  );
}
