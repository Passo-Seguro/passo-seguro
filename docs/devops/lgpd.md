# LGPD: onde ficam os dados pessoais

Este documento lista os dados pessoais do Passo Seguro, onde ficam e como são protegidos. Cada afirmação foi conferida no código de [`api/`](../../api/), no [`app/`](../../app/) e no Terraform de [`infra/`](../../infra/). O que ainda não está implementado está na tabela **Pendente**, com o próximo passo.

Não é parecer jurídico. As bases legais precisam da revisão do grupo.

O produto não pede nome, e-mail, telefone nem login. Mesmo assim, três dados do relato podem identificar uma pessoa: a **foto** (rosto, placa, fachada), o **local** (coordenadas) e o **texto livre**. O identificador do aparelho também conta, porque liga relatos ao mesmo autor.

## Implementado

| Dado | Onde fica | Como é protegido | Conferido em |
|---|---|---|---|
| **Foto** | Azure Files, share `fotos`, conta Standard LRS em `centralus` (EUA). A API grava em `relatos/<uuid4>.<jpg\|png>` | Só JPEG e PNG, validados pelo conteúdo, até 10 MB. A API **remove o EXIF** (o GPS exato da câmera) ao regravar a imagem. Nome do arquivo com UUID aleatório. Conta com TLS 1.2 e HTTPS obrigatório, sem blob público. Veja o risco da URL pública em [`arquitetura.md`](./arquitetura.md#fotos-é-público-por-url-não-adivinhável) | [`api/app/services/imagens.py`](../../api/app/services/imagens.py), [`infra/storage.tf`](../../infra/storage.tf) |
| **Coordenadas** (local do problema) | Postgres Flexible Server privado (coluna `localizacao`, PostGIS, **precisão exata**) | Banco sem endereço público, NSG só com a 5432 vinda da `snet-aca`, `sslmode=require`. O mapa público (`GET /relatos/proximos`) devolve lat e lon **arredondadas a 3 casas (~100 m)** e não devolve foto nem descrição. A API só aceita relatos dentro de uma caixa de coordenadas que envolve o município de São Paulo | [`api/app/routers/rc2.py`](../../api/app/routers/rc2.py), [`infra/banco.tf`](../../infra/banco.tf), [`infra/rede.tf`](../../infra/rede.tf) |
| **Coordenadas exatas fora do mapa** | Resposta de `GET /relatos` e de `PATCH /relatos/{id}` | Só saem com o token de serviço (triagem) ou, no `PATCH`, para o autor do relato. A triagem precisa do ponto exato para encaminhar. O arredondamento vale só para o mapa público | [`api/app/services/relatos.py`](../../api/app/services/relatos.py) |
| **`autor_id`** (número anônimo do aparelho) | No aparelho (`localStorage`). No banco, só `autor_hash` | **HMAC-SHA256** do `autor_id`, com `SALT_AUTOR` como chave (hash com sal, sem o id original). O sal vem do **Key Vault** (segredo `salt-autor`) e **não fica no banco**: quem vazar só o banco não reverte os ids por tentativa e erro. O `autor_id` e o hash **não saem pela API nem entram nos logs**. Sem o sal configurado, a API nem sobe com a rc2 ligada | [`api/app/seguranca.py`](../../api/app/seguranca.py), [`api/app/main.py`](../../api/app/main.py), [`infra/segredos.tf`](../../infra/segredos.tf) |
| **Texto livre** (`descricao`) | Postgres | Até 1000 caracteres. A tela de Privacidade pede para não digitar telefone, CPF nem nomes. **Não há filtro automático** (veja Pendente) | [`api/app/schemas/relatos.py`](../../api/app/schemas/relatos.py), [`app/src/pages/Privacidade.tsx`](../../app/src/pages/Privacidade.tsx) |
| **Fila offline no aparelho** | IndexedDB do navegador | Guarda a foto, o local, o texto e o `autor_id` até o envio e apaga o item logo depois do 201 da API | [`app/src/offline/fila.ts`](../../app/src/offline/fila.ts) |
| **Pergunta ao assistente** | Enviada ao serviço do **Railway** (LLM). A API não grava a pergunta | A API envia **só** `{"pergunta": "<texto>"}` (de 1 a 500 caracteres) e o cabeçalho `Authorization: Bearer <token>`. Não envia `autor_id`, localização, foto nem cabeçalhos do cidadão. O token vem do Key Vault (`assistente-token`). Em erro, o log registra só o tipo da exceção, nunca a pergunta nem a URL. Se o assistente cair, a resposta é a recusa padrão com o link do SP156 | [`api/app/clients/assistente.py`](../../api/app/clients/assistente.py), [`api/app/schemas/assistente.py`](../../api/app/schemas/assistente.py) |
| **Logs da API** | Saída padrão do contêiner, que vai para o Log Analytics | Uma linha JSON por requisição, com método, **modelo** da rota (`/relatos/{id}`), status, duração e um id aleatório. **Sem** corpo, foto, descrição, **query string** (traz coordenadas), cabeçalhos (`X-Autor-Id`, tokens) nem IP. Lista fechada de campos permitidos. Os rótulos das métricas também usam só o modelo da rota | [`api/app/observabilidade.py`](../../api/app/observabilidade.py) |
| **Logs do nginx (app)** | Saída do contêiner do app, no Log Analytics | O log de acesso grava o **caminho sem query string**, e não grava Referer nem cookies. O log de erro só registra falhas graves (`crit`), porque o log de erro do nginx imprime a query string | [`app/nginx.conf.template`](../../app/nginx.conf.template) |
| **Retenção dos logs** | Log Analytics `log-passoseguro` | Retenção de **30 dias** e teto de 0,15 GB por dia | [`infra/monitoramento.tf`](../../infra/monitoramento.tf) |
| **Backups do banco** | Backups automáticos do PostgreSQL Flexible Server | Retenção de **7 dias**, sem redundância geográfica (as cópias ficam na mesma região) | [`infra/banco.tf`](../../infra/banco.tf) |
| **Segredos** | Key Vault | Acesso por Entra ID e RBAC. Os apps leem com identidade gerenciada. Nenhum segredo no git (Gitleaks no pipeline) | [`infra/segredos.tf`](../../infra/segredos.tf), [`ci.yml`](../../.github/workflows/ci.yml) |
| **Região** | Azure `centralus` (EUA) | Veja a seção [Região e transferência internacional](#região-e-transferência-internacional) | [`infra/variables.tf`](../../infra/variables.tf) |

## Pendente

| Item | Situação hoje | Próximo passo |
|---|---|---|
| **Desfoque de rostos e placas** | **Não existe no código.** A API só valida a imagem e remove o EXIF. A foto vai ao Azure Files como o cidadão a enviou. O README dizia "fotos publicadas têm rostos e placas desfocados"; isso ainda não é verdade | Passar um detector de rostos e placas em [`services/imagens.py`](../../api/app/services/imagens.py), **depois de `limpar_imagem` e antes de `armazenamento.salvar`**, e aplicar desfoque gaussiano nas caixas. Se o detector falhar, **não gravar a foto** (responder 503) em vez de gravar sem desfoque. Testar com fotos fictícias e acrescentar o teste em `api/tests/`. O repositório `passo-seguro-visao` já tem um YOLO e pode ganhar as classes `rosto` e `placa` |
| **Aviso sobre a pergunta ao assistente** | A pergunta vai em texto puro ao Railway. A tela de Privacidade **não menciona** o assistente nem o Railway | Em [`Privacidade.tsx`](../../app/src/pages/Privacidade.tsx) e ao lado do campo da pergunta, avisar: "sua pergunta é enviada a um serviço externo (Railway); não escreva nome, telefone, CPF ou endereço" |
| **Filtro de dado pessoal na pergunta** | A API **não filtra** nada antes de enviar ao Railway; só limita o tamanho a 500 caracteres | Em `routers/assistente.py`, antes de `assistente.perguntar`, detectar CPF, telefone, e-mail e CEP por expressão regular e **recusar ou mascarar**. Cobrir com teste |
| **Condições do Railway** | Região, retenção e registro das perguntas no serviço **não estão documentados** neste repositório | Perguntar à pessoa que opera o serviço: região, se as perguntas ficam em log e por quanto tempo. Registrar a resposta neste arquivo |
| **Aviso sobre o armazenamento nos EUA** | A tela de Privacidade não diz que foto, local e relato ficam em servidores nos EUA | Acrescentar a frase em [`Privacidade.tsx`](../../app/src/pages/Privacidade.tsx) e no aviso da primeira abertura ([`AvisoPrivacidade.tsx`](../../app/src/components/AvisoPrivacidade.tsx)) |
| **Base legal da transferência (art. 33)** | Não há consentimento específico para a transferência: o aviso inicial só tem o botão "Entendi" | O grupo decide a base (veja a seção abaixo) e o texto do app passa a refletir essa decisão |
| **IP nos logs do nginx** | O `log_format` do nginx inclui `$remote_addr`. O log da API não tem IP, mas o do nginx tem. Atrás do ingress da plataforma, esse campo pode ser o endereço do proxy e não o do cidadão. **Não verificamos** | Consultar o Log Analytics (tabela `ContainerAppConsoleLogs_CL`, ou `ContainerAppConsoleLogs`) e ver o que o campo `ip` mostra. Se aparecer IP de cidadão, remover o campo do `log_format` em [`nginx.conf.template`](../../app/nginx.conf.template) |
| **Exclusão de dados** | **Não há endpoint nem rotina.** Só existe SQL manual para relatos simulados e fakes ([`modo-deteccao.md`](../modo-deteccao.md), [`dados-simulados.md`](../dados-simulados.md)). Apagar a linha do banco **não apaga a foto** do Azure Files | Criar `scripts/apagar_dados_do_autor.py`: recebe um `autor_id`, calcula o hash, lista os relatos, remove os arquivos do share e depois as linhas. Depois, propor ao grupo o `DELETE /meus-relatos` na próxima emenda do contrato |
| **Prazo de retenção dos relatos e das fotos** | **Não definido.** Os relatos e as fotos ficam sem prazo. Os backups guardam a cópia por até 7 dias depois da exclusão | O grupo define o prazo. Depois, uma rotina (Container Apps Job) apaga relatos `resolvido` e `rejeitado` antigos, com as fotos |
| **Canal do titular (art. 18)** | A tela de Privacidade não informa como pedir acesso, correção ou exclusão, nem quem é o responsável | Acrescentar o e-mail da equipe na tela de Privacidade e combinar o fluxo: pedido, conferência do `autor_id`, execução do script acima |
| **Foto sem backup** | O Terraform não configura backup nem snapshot do share `fotos` | Ligar snapshots ou o Azure Backup do share. Se for decidido não ter backup, registrar como risco aceito |
| **URL da foto sem expiração** | A rota `/fotos/*` é pública por URL não adivinhável (risco aceito em [`infra/README.md`](../../infra/README.md#riscos-aceitos)). A URL não expira nem se revoga | Trocar por URL assinada (SAS) de curta duração ou por rota autenticada, junto com o desfoque |

## Região e transferência internacional

Os dados ficam em `centralus`, nos EUA, e a pergunta ao assistente vai a um serviço no Railway (região não documentada). Isso é **transferência internacional** de dados pessoais, regida pelo art. 33 da LGPD.

**Motivo da região.** A assinatura Azure for Students só permite `chilecentral`, `eastus`, `southcentralus`, `centralus` e `canadacentral`. **Nenhuma é no Brasil.** O PostgreSQL Flexible Server está restrito em `eastus` e `southcentralus`. VNet, Container Apps e banco precisam ficar na mesma região, e o time escolheu `centralus` para tudo. Não avaliamos neste repositório se `canadacentral` ou `chilecentral` atendem o banco; fica como alternativa a conferir.

**Base do art. 33: a confirmar pelo grupo.** O art. 33 só permite a transferência em casos listados. Dois deles são os candidatos mais prováveis para este projeto:

- **Inciso II**, garantias oferecidas pelo controlador (por exemplo, cláusulas contratuais padrão). O contrato do provedor de nuvem pode servir de apoio, e a ANPD regulamentou as cláusulas-padrão.
- **Inciso VIII**, consentimento específico e em destaque, com informação prévia do caráter internacional da operação. **O app hoje não faz isso**: o aviso inicial informa o que é guardado, mas não diz que fica nos EUA, e o botão é só "Entendi".

Enquanto o grupo não decide, trate a base como **pendente**. Os dois passos concretos estão na tabela acima: aviso sobre os EUA e o Railway na tela de Privacidade, e o registro da base escolhida neste arquivo.

## Retenção e como apagar

| Dado | Retenção hoje | Como apagar hoje |
|---|---|---|
| Relatos (linha no Postgres) | Sem prazo (pendente) | SQL manual no banco. Para relatos simulados: `python scripts/gerar_dados_simulados.py --apagar` |
| Fotos | Sem prazo (pendente) | Remover o arquivo `relatos/<id>.<ext>` do share `fotos`. A API tem `Armazenamento.remover`, mas só a usa para desfazer um relato que falhou ao gravar; nenhuma rota apaga relato |
| Cópias nos backups do banco | 7 dias | Expiram sozinhas |
| Logs (Log Analytics) | 30 dias | Expiram sozinhos |
| `autor_id` no aparelho | Até a pessoa limpar os dados do navegador | A própria pessoa |

Para apagar **todos os dados de um relato** hoje, na ordem certa: guarde a `foto_chave` do relato, apague a linha e só então apague o arquivo. O procedimento com os comandos está em [`modo-deteccao.md`](../modo-deteccao.md#como-apagar). Os backups do banco ainda guardam a linha por até 7 dias.
