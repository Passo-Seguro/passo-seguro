# Relatos criados sob visão fake (`modo_deteccao`)

A visão e o assistente têm uma versão **fake** (`USE_FAKE_VISAO`, `USE_FAKE_ASSISTENTE`) que serve
só para desenvolvimento: a categoria do relato sai do hash da imagem, **não do modelo**. Ela vem
desligada por padrão e, quando ligada, a API avisa no log, em `/health` e na métrica
`passo_seguro_modo_fake`. Mesmo assim, um relato criado sob fake já está no banco. Para não
misturá-lo com os de verdade, cada relato guarda **como a categoria foi obtida**.

## A coluna

`relatos.modo_deteccao` é **interna**: não está no contrato (`openapi.yaml`) nem em nenhuma
resposta da API (há teste para isso). Valores:

| Valor | Quando |
|---|---|
| `real` | A visão real (serviço de visão, `VISAO_URL`) respondeu com ao menos uma detecção. |
| `fake` | O cliente fake respondeu com ao menos uma detecção. |
| `nenhuma` | A visão falhou (fora do ar, timeout, erro, resposta fora do contrato), **não detectou nada**, ou o relato é simulado por script. |

Os relatos de `scripts/gerar_dados_simulados.py` continuam com `simulado = true` e
`modo_deteccao = 'nenhuma'` (não passaram por visão nenhuma). Relatos que já existiam antes da
migração `0003` ficam como `nenhuma` (não há como saber como foram detectados).

> `simulado` e `modo_deteccao` respondem a perguntas diferentes. `simulado` = "este relato foi
> inventado por script". `modo_deteccao = 'fake'` = "um relato **de verdade** (enviado ao
> endpoint) cuja categoria veio do detector de mentira".

## Como consultar

Com o banco da composição de desenvolvimento no ar:

```bash
docker compose -f docker-compose.dev.yml exec db psql -U passo -d passo_seguro
```

```sql
-- Quantos relatos há de cada tipo?
SELECT modo_deteccao, simulado, count(*)
FROM relatos
GROUP BY modo_deteccao, simulado
ORDER BY 1, 2;

-- Os relatos criados sob visão fake (sem os simulados por script)
SELECT id, criado_em, categoria, confianca, status
FROM relatos
WHERE modo_deteccao = 'fake' AND NOT simulado
ORDER BY criado_em;

-- Algum relato fake já saiu da fila de novos (revisado, validado, encaminhado...)?
SELECT status, count(*)
FROM relatos
WHERE modo_deteccao = 'fake' AND NOT simulado
GROUP BY status;
```

Antes de uma demonstração, o resultado da primeira consulta tem de mostrar **nenhuma** linha
com `fake`. Se aparecer, apague (abaixo) ou, se o relato já foi tratado por uma pessoa, decida
com o grupo em vez de apagar.

## Como apagar

Confira o que será apagado com a consulta acima. Depois, numa transação, para poder desfazer:

```sql
BEGIN;
DELETE FROM relatos WHERE modo_deteccao = 'fake' AND NOT simulado;
-- confira a quantidade que o psql informou (DELETE n) e, se estiver certo:
COMMIT;      -- ou ROLLBACK; para desistir
```

Apagar a linha **não apaga a foto** da pasta de fotos. Para remover também os arquivos, liste
as chaves **antes** do `DELETE`, e depois apague cada arquivo:

```bash
docker compose -f docker-compose.dev.yml exec -T db psql -U passo -d passo_seguro -At \
  -c "SELECT foto_chave FROM relatos WHERE modo_deteccao = 'fake' AND NOT simulado" > chaves-fake.txt

# (rode o DELETE acima) e então:
while read -r chave; do
  docker compose -f docker-compose.dev.yml exec -T api rm -f "/data/fotos/$chave"
done < chaves-fake.txt
rm chaves-fake.txt
```

Os relatos simulados por script têm o próprio comando de limpeza
(`python scripts/gerar_dados_simulados.py --apagar`, ver [dados-simulados.md](./dados-simulados.md)),
que não toca nos relatos reais nem nos criados sob fake.
