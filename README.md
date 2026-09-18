# Sistema de apoio à decisão · Reforma Tributária

TCC — simulação de impacto da Reforma Tributária do Consumo
(EC 132/2023, LC 214/2025, LC 227/2026).

**Princípio central:** o motor determinístico calcula, a IA explica.
Nenhuma alíquota, data ou percentual de transição vive no código.

## Estado atual

Esqueleto funcional. Sobe, conecta no banco, carrega parâmetros.

| Item | Situação |
|---|---|
| Modelos e migrations | pronto |
| Parâmetros versionados e cenários de alíquota | pronto |
| Seed com empresas fictícias | pronto |
| Rotas de leitura | pronto |
| Motor de cálculo | pronto (47 testes) — 3 de 3 calibrações corrigidas, ver abaixo |
| Simples: único vs. híbrido | pronto (motor) |
| Interface web — rodar simulação e ver resultado | pronto (`/`, server-rendered) |
| Login e multi-tenant (empresa/escritório, admin) | pronto — ver seção Autenticação |
| Integração com IA + camada de verificação (RF05) | pronto — ver seção IA generativa |
| Tema claro/escuro, navegação, perfil (foto, nome, nome da conta) | pronto |
| Identidade visual (tipografia, paleta) | pronto — ver seção própria |
| Cadastro de empresa pela tela (RF01) — empresa, custos, itens | pronto — ver seção Cadastro de empresa |
| Cenários de alíquota criados pelo usuário ("e se…") | pronto — ver seção Cenários |
| Gráfico de comparação (RF06) | pronto — ver seção Gráficos |
| Histórico e persistência da simulação (RF08/RF11) | pronto — ver seção própria |
| Exportação/impressão do relatório (RF07) | pronto — ver seção própria |
| Repetir simulação com parâmetros alterados (RF10) | pronto — ver seção Histórico |

## Subindo

```bash
docker compose up -d db          # ou um Postgres 16 local
cp .env.example .env

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload
```

Documentação interativa em `http://localhost:8000/docs`. A interface de simulação exige
login — ver seção Autenticação para as contas que o seed já deixa prontas.

## Deploy (Render)

`render.yaml` na raiz descreve tudo: web service Python + banco Postgres
gratuito, ligados. Migration e seed rodam junto com o `startCommand` — o
plano free do Render não tem "pre-deploy command" (achado testando: o
Render recusa o blueprint com esse erro se tentar usar), então os dois
entram na cadeia que sobe o serviço, toda vez que ele inicia (inclusive ao
acordar do sono). Seguro porque os dois são idempotentes — rodar de novo
não duplica nada.

**Passo a passo:**

1. Suba este repositório pro GitHub — pelo GitHub Desktop (`File > Add
   local repository`, aponta pra esta pasta, publica), ou 100% pelo site:
   cria um repositório vazio em github.com, usa o link "uploading an
   existing file" que aparece, e arrasta pra lá o conteúdo de
   `git archive HEAD -o pacote.zip` extraído (evita levar `.venv`, `.env`,
   histórico do git — só o que está versionado). Útil se a conta do GitHub
   Desktop estiver vinculada a outra organização/empresa.
2. Crie conta em [render.com](https://render.com) (grátis, geralmente sem
   pedir cartão no plano free).
3. No painel, **New > Blueprint**, conecte o repositório do GitHub. O
   Render lê o `render.yaml` sozinho e propõe criar o banco + o serviço web
   juntos.
4. Antes de confirmar, ele vai pedir pra preencher as variáveis marcadas
   `sync: false` — só você vê e digita, nunca aparece pra mim:
   - `OPENAI_API_KEY` — a chave da OpenAI (a mesma do seu `.env` local)
   - `ADMIN_EMAIL` — seu e-mail de admin
   - `ADMIN_SENHA` — a senha que você quer usar pra entrar como admin
   `SECRET_KEY` é gerada sozinha pelo Render, ninguém escolhe.
5. Deploy. Leva alguns minutos na primeira vez (build + migration + seed).
   O Render te dá uma URL tipo `https://reforma-tributaria.onrender.com` —
   é essa que você manda pro seu amigo.

**Limitações do plano gratuito, pra não ter surpresa:**
- O serviço web "dorme" depois de um tempo sem acesso — o primeiro clique
  depois disso demora uns 30-60s pra acordar. Normal, não é erro.
- O banco Postgres gratuito do Render expira em 90 dias (aviso por e-mail
  antes). Pra um teste com um amigo não é problema; pra algo permanente,
  precisaria upgrade de plano.
- Fotos de perfil (`app/web/static/uploads/`) ficam no disco do servidor,
  que **não é persistente** no plano free — um redeploy apaga as fotos já
  enviadas (o resto dos dados, que fica no Postgres, não é afetado). Se
  isso incomodar, dá pra resolver depois com um Render Disk (pago) ou
  movendo upload pra um serviço externo — não é urgente pra uma demo.
- Se o `render.yaml` mudar de formato entre quando isso foi escrito e
  quando você for usar, o Render mostra erro de validação apontando o
  campo — dá pra ajustar ali mesmo ou criar o banco e o serviço web
  manualmente pelo painel (mais clique, mas sempre funciona).

## Estrutura

```
app/
  config.py              variáveis de ambiente
  db.py                  engine e sessão
  models/
    base.py              Base, enums, JSONType portável
    identidade.py        Tenant, Usuario
    empresa.py           Empresa, CustoEmpresa, ItemEmpresa
    parametros.py        CenarioAliquota, RegrasVersao
    simulacao.py         Simulacao, AnaliseIA, LogAuditoria
  seeds/
    regras_iniciais.py   calendário 2026-2033, Simples, cenários
  auth/
    seguranca.py          hash de senha (argon2), token de sessão (JWT)
    dependencias.py        usuario_web / usuario_api, escopo por tenant
  api/rotas.py           rotas de leitura (JSON), autenticadas
  web/
    adaptador.py          Empresa (ORM) -> EntradaSimulacao (motor)
    rotas.py               login/logout, GET / (formulário), POST /simular
    empresas.py             cadastro de empresa (RF01) + ajuda da IA
    cenarios.py              cenários de alíquota do usuário ("e se…")
    historico.py              lista/reabre Simulacao salva (RF08/RF11)
    graficos.py               barras de comparação (RF06), sem lib nova
    uploads.py               salva foto de perfil em disco, nome gerado
    templates/              Jinja2, sem build step, sem JS externo
    static/uploads/          fotos de perfil (fora do git, .gitkeep só)
alembic/                 migrations
scripts/
  seed.py                 popula parâmetros, tenants e empresas fictícias
  criar_usuario.py         provisiona conta (uso do admin, sem cadastro público)
```

## Interface web

`GET /` mostra um formulário simples: escolher uma das empresas do seed, o
ano da simulação, o cenário de alíquotas e, se a empresa for do Simples, a
opção a comparar. `POST /simular` roda o motor e reexibe a mesma página com
o resultado — carga atual vs. simulada, tributos por rubrica, a tabela
único vs. híbrido quando aplicável, as limitações (RF09) e um aviso de que
a camada de IA (RF05) ainda não está integrada.

Sem SPA, sem HTMX, sem build step: FastAPI + Jinja2 renderizam a página no
servidor. Decisão consciente — `jinja2` já estava no `requirements.txt` e
não há tooling de frontend no repositório; para um protótipo acadêmico,
menos peças móveis pesa mais do que "framework moderno" no currículo da
tecnologia. Exportação/impressão (RF07) e histórico (RF11) — ver seções
próprias abaixo. Cadastro de empresa pela tela (RF01) — ver seção própria
abaixo.

**Nota de ambiente**: testado localmente com SQLite (sem Docker/Postgres
disponíveis na máquina de desenvolvimento), com um pequeno shim que
registra `now()` — que o SQLite não tem nativamente — via
`sqlite3.Connection.create_function`, sem alterar nenhum arquivo do
projeto. `func.now()` como `server_default` é específico de Postgres; em
produção/dev normal, com `docker compose up -d db`, isso não é necessário.

### Tema, navegação e perfil

Tudo em `app/web/templates/base.html`, sem lib nova. Tema claro/escuro via
CSS custom properties redefinidas sob `[data-theme="dark"]` e
`@media (prefers-color-scheme: dark)` — o botão no cabeçalho grava a
escolha em `localStorage` e um script inline no `<head>` aplica antes do
primeiro paint (sem isso, pisca claro e escurece depois). Segue o sistema
até o usuário escolher explicitamente.

`GET/POST /perfil`: editar o próprio nome, foto (JPG/PNG/WEBP até 2 MB,
salva em `app/web/static/uploads/` com nome gerado — nunca o nome
original, nunca escolhido pelo cliente) e o nome da conta (`Tenant.nome` —
rotulado "nome da empresa" ou "nome do escritório" conforme
`Tenant.tipo`). Renomear a conta é bloqueado no servidor para papel
`operador` (só gestor/admin), não só escondido na tela — o campo
desabilitado no HTML não é a proteção real. Testado: editar nome + nome da
conta, subir foto, trocar foto (a antiga é apagada do disco), remover
foto, e rejeitar upload que não é imagem (nenhum arquivo fica no disco).

Avatar sem foto usa a inicial do nome sobre uma cor tirada de uma paleta
fixa por `usuario.id % 6` — só para não repetir a mesma cor pra todo
mundo, não é identidade visual pensada.

**Achado reportado pelo Denis: link "Simular" saindo roxo, camuflado no
fundo escuro.** O link na listagem de empresas era um `<a>` sem `class` —
sem cor própria, herdava o roxo padrão do navegador pra link já visitado
(`:visited`), que não combina com o resto da paleta. `.botao-secundario`
(usada em "Simular"/"Editar"/"Cancelar") ganhou `display`, `padding` e
`border-radius` próprios — antes só funcionava direito em `<button>`,
porque pegava essas propriedades da regra base de `button`, que um `<a>`
não tem. Cor explícita em qualquer link estilizado como botão sempre
vence o `:visited` do navegador, então isso não volta a acontecer em
nenhum outro link da tela.

### Identidade visual (18/09/2026)

Pedido do Denis: "dá pra deixar a interface mais bonita?". A tela estava
funcional mas genérica — fonte padrão do sistema, azul comum de
dashboard, cards planos. Refeito só em `app/web/templates/base.html`
(tokens de cor + tipografia são compartilhados por toda a aplicação via
CSS custom properties, então um único arquivo alcança todas as telas):

- **Tipografia**: IBM Plex Serif (títulos), IBM Plex Sans (corpo) e IBM
  Plex Mono (valores monetários, percentuais, tabelas — com
  `font-variant-numeric: tabular-nums` pra colunas de número alinharem).
  Carregadas via Google Fonts (`<link>` no `<head>`, mesmo domínio já
  usado pelo `parametros_motor.html` gerado nessa mesma sessão — os dois
  documentos do "produto Reforma Tributária" agora compartilham a mesma
  linguagem visual).
- **Cor**: saiu o azul genérico (`#1d4ed8`) por um teal mais próprio
  (`#0e6e86` claro / `#3fc0d6` escuro) — verde/vermelho continuam
  reservados pro significado semântico (redução/aumento de carga), não
  competem com o acento principal. Fundo, bordas e texto levemente
  reaquecidos (verde-acinzentado em vez de azul-acinzentado) pra combinar.
- **Hierarquia**: cards com mais respiro (padding/radius maiores),
  números grandes dos indicadores (carga atual/simulada/variação) mais
  pesados, barras do gráfico com cantos mais arredondados e um highlight
  sutil no topo.
- Cores do cabeçalho (sempre escuro, nas duas paletas — dark navbar sobre
  página clara é um padrão comum) reajustadas de cinza-azulado pra
  cinza-esverdeado, coerente com o novo acento.
- `@media print` (RF07) recebeu os mesmos tokens atualizados, senão o PDF
  exportado saía com a paleta antiga enquanto a tela já usava a nova.
- Nenhuma mudança de estrutura HTML nas páginas — só `base.html` (tokens +
  regras de componente). `app/web/graficos.py` já usava `var(--cor-...)`
  pras cores das barras, então o gráfico herdou a paleta nova de graça,
  sem precisar tocar no Python.
- Testado visualmente nas telas de login, simular, empresas e num
  resultado completo (indicadores, gráfico, tabela de tributos, único vs.
  híbrido, limitações, análise de IA) — tema escuro conferido por
  screenshot; tema claro conferido lendo os valores computados das
  variáveis CSS direto do DOM (o ambiente de preview usado nessa sessão
  tem um problema conhecido de renderizar capturas de tela do tema claro
  como se fossem escuras — achado ao vivo, não é bug da aplicação: o
  `getComputedStyle` confirma os tokens corretos mesmo quando a captura
  engana).

**Segunda rodada — componentes, não só cor (mesmo dia).** Feedback direto:
"o layout tá igual, tu só mudou a cor, eu queria botões, campos bonitos".
Justo — a primeira rodada só trocou tokens de cor/fonte, sem repensar a
forma dos próprios controles. Essa rodada mexe nos componentes de
verdade, ainda só em `base.html`:

- **Botões** (`button`, `.botao-link`): saíram do preenchimento chapado
  pra um gradiente sutil (`linear-gradient` de cima pra baixo na própria
  cor do tema) com sombra colorida (na cor do acento, não cinza genérico)
  e um leve "levantar" no hover (`translateY(-1px)` + sombra maior),
  voltando ao lugar no clique. `.botao-secundario` ganhou o mesmo
  levantar e um fundo sutil no hover em vez de só trocar a borda.
- **Campos** (`select`, `input`): borda mais grossa, `border-radius`
  maior, mais respiro interno, anel de foco mais visível
  (`box-shadow` de 4px em vez de 3px). `<select>` perdeu a seta
  padrão do navegador — agora é uma seta SVG embutida via
  `background-image` (`data:image/svg+xml`), com uma versão pro tema
  claro e outra pro escuro (a cor do traço não muda sozinha, então
  precisa de duas versões, uma em cada bloco de tema).
- **Rádios** (`.radios label`): de bolinha nativa + texto pra um
  controle segmentado — cada opção vira uma "pill" com borda, e a
  selecionada preenche com a cor do acento (`:has(input:checked)`,
  suportado nos navegadores modernos, sem precisar de JS). Checkboxes e
  rádios em geral ganharam `accent-color` na cor do tema, pra não ficarem
  cinza/azul do sistema operacional destoando do resto.
- **Bug achado e corrigido na hora**: o rótulo em maiúsculas com
  letter-spacing que a primeira rodada deu pros labels de campo
  (`.campo label`) vazou pros rádios e pro checkbox "remover foto atual"
  — os dois ficam estruturalmente dentro de uma `div.campo` no HTML (pra
  herdar o espaçamento), então `.campo label` (seletor por descendência)
  também batia neles. O resultado: "Comparar único e híbrido" virava
  "COMPARAR ÚNICO E HÍBRIDO" sem eu ter pedido. Corrigido resetando
  `text-transform` e `letter-spacing` explicitamente em `.radios label` e
  `.chk-remover` — CSS não herda automaticamente as propriedades que uma
  regra mais específica não redeclara, então bastou declarar de volta.
- Testado visualmente de novo: login, formulário de simulação (rádios
  segmentados, select com seta customizada), listagem de empresas
  (botões secundários) e o formulário de cadastro de empresa (o mais
  cheio de campos do sistema).

**Terceira rodada — estrutura, não só componente (mesmo dia).** Feedback
com 5 screenshots da tela real: "tá mt genérico, parece html puro, qro
uma mudança grande, em tudo, só nao deixa os botoes mt neon e brilhosos".
Nem cor nem forma de componente bastam se o layout inteiro continua
sendo "barra no topo + card embaixo" — o pedido era mudar a estrutura da
página. Ainda tudo em `base.html` (confirmado por grep que nenhum outro
template referencia as classes de header/nav, então a troca ficou
contida num arquivo só):

- **Navegação lateral**: o `<header class="topo">` horizontal virou
  `<aside class="lateral">` — barra fixa à esquerda, sempre escura (nas
  duas paletas, mesmo raciocínio do cabeçalho antigo), com marca + ícone
  no topo, links de navegação com ícone SVG desenhado à mão (traço,
  `currentColor`, estilo Feather) no meio, e tema/usuário/sair no rodapé.
  Abaixo de 880px de largura a mesma marcação vira barra horizontal no
  topo (só muda `flex-direction` num `@media`, sem duplicar HTML nem
  JS de menu hambúrguer).
- **Fundo com profundidade**: `body` ganhou dois `radial-gradient` bem
  sutis (opacidade baixa, cor do acento) posicionados nos cantos, atrás
  da cor sólida de fundo — textura sem ficar chamativo.
- **Identidade de card**: `.cartao` ganhou uma borda superior de 3px na
  cor do acento, pra parar de parecer uma caixa branca genérica.
- **Tratamento de tabela**: zebra striping (`tbody tr:nth-child(even)`),
  destaque de linha no hover, e o cabeçalho da tabela ganhou uma borda
  inferior de 2px na cor do acento em vez do cinza padrão.
- **Sem neon**: o `box-shadow` colorido dos botões (herdado da segunda
  rodada) foi reduzido — menos blur, menos opacidade — pra manter a
  profundidade sem virar brilho/glow, exatamente o limite que o Denis
  pediu.
- Testado visualmente: desktop (tema claro e escuro) nas telas de
  simular, empresas e perfil, e o colapso responsivo em viewport de
  celular (375px) — a barra lateral vira topo horizontal com rótulos
  escondidos, só ícone, sem quebrar a navegação.

## Gráfico de comparação (RF06)

`app/web/graficos.py`. O RF06 do TCC I pedia "tabelas, cartões **e
gráficos** simples" — só faltava o gráfico, e o próprio wireframe (Figura
3) já mostrava barras de "Comparação entre cenários". Sem lib nova: barra
é `<div>` com `height` em `%`, cor via variável CSS — tema-aware de
graça, sem duplicar cor por tema, e sem SVG/canvas/dependência.

Dois gráficos na tela de resultado: **carga atual vs. simulada** (sempre,
cor da segunda barra muda com a direção — vermelho se aumenta, verde se
reduz) e **Simples único vs. híbrido** (só quando as duas opções foram
calculadas — se a simulação pediu só uma, não faz sentido comparar duas
barras; nesse caso o gráfico não aparece). Neste segundo, a opção mais
barata fica verde, a outra cinza — ajuda a ver de cara qual vale mais a
pena, sem precisar ler a tabela. `_montar_barras()` normaliza a barra
maior pra 100% de altura e usa piso de 4% pra uma barra pequena não
sumir visualmente. Não decide nenhum número novo — só a proporção visual
de valores que o motor já calculou.

Testado com a Distribuidora (Simples): os dois gráficos aparecem juntos,
"Único" sai visivelmente mais baixo e verde (mais barato) que "Híbrido"
— o mesmo resultado que já estava na tabela ao lado, só que visível de
relance. Conferido nos dois temas.

## Cadastro de empresa (RF01)

`app/web/empresas.py` + `empresas_lista.html` / `empresa_nova.html`.
`GET /empresas` lista as empresas do tenant (todas, se admin) com botão
"+ Nova empresa"; `GET/POST /empresas/nova` é o formulário completo —
identificação, regime tributário (com os campos do Simples aparecendo só
quando o regime é Simples, via JS), faturamento e composição, margens,
alíquotas atuais (escondidas para Simples — não é de lá que vêm), custos e
despesas, e itens/produtos, esses dois últimos em tabelas com linhas
adicionadas/removidas dinamicamente (`<template>` + JS puro, sem lib).

A empresa nasce presa ao `tenant_id` do usuário logado — nunca escolhido
no formulário, pra não dar pra criar empresa em tenant alheio. Sem itens
cadastrados, a simulação cai no modo "agregado" do motor (já testado
antes); com itens, a alíquota de cada um, quando não preenchida, herda a
da empresa — mesma regra de `app/web/adaptador.py`, não duplicada aqui.
Os itens precisam somar 100% do faturamento (validado no servidor); custo
negativo e Simples sem anexo também são barrados. Em erro de validação, o
formulário inteiro é redesenhado com o que já foi digitado — inclusive as
linhas de custo e item — para não obrigar a pessoa a digitar tudo de novo.

**Editar empresa** (`GET/POST /empresas/{id}/editar`): mesmo template
`empresa_nova.html`, reaproveitado nos dois modos (`modo == 'editar'`
muda a action do form, o texto do botão e o título da página). A
validação saiu de dentro de `criar_empresa` para `_validar_e_montar()`,
uma função só, chamada pelos dois — criar e editar não têm regra
diferente, só o que fazem com o resultado. Ao salvar, custos e itens
antigos são apagados e os novos inseridos do zero (mais simples que
tentar casar linha por linha; sem nada referenciando `CustoEmpresa.id`/
`ItemEmpresa.id` ainda, não há custo nisso). Testado: abrir o form de uma
empresa existente com Anexo 4 (o mesmo caso da mensagem de erro acima),
ver os campos vindos do banco em formato de tela (fração vira "17,5", não
"0.175" — `_pct_str()`, inverso de `_fracao()`), trocar para Anexo 1 e
salvar, e simular em seguida sem erro.

**Excluir empresa** (`POST /empresas/{id}/excluir`): apaga em cascata
(custos e itens junto, via `cascade="all, delete-orphan"` do modelo — não
sobra órfão). Confirmação por `confirm()` do navegador antes de enviar.
Bloqueado no servidor (não só escondido na tela) para empresa de outro
tenant e para papel `operador` — mesma régua já usada em renomear a conta
no perfil. Sem `Simulacao` persistida ainda, não existe histórico órfão a
zelar; quando existir, precisa revisitar isso.

**Ajuda da IA durante o cadastro** (`POST /empresas/ajuda`): chat ao lado
do formulário para tirar dúvida sobre o que cada campo significa ("o que é
RBT12?"). Instruída a nunca citar uma alíquota ou número específico — se
perguntarem, redireciona para a tela de cenários ou para um contador. Essa
garantia é só de prompt, não estrutural: diferente do chat de resultado
(`/chat`), aqui não existe `referencias` calculada para checar a resposta
contra nada, então não passa por `verificacao.py`/`renderizador.py`. É uma
categoria de confiança mais fraca, declarada assim na tela e no código.

## Cenários de alíquota do usuário

`app/web/cenarios.py` + `cenarios_lista.html` / `cenario_novo.html`. O
modelo já previa isso — `CenarioAliquota.tenant_id` (nulo = global,
preenchido = de um tenant) e `TipoCenario.USUARIO` existiam desde o
início, só não havia tela. Existe porque a reforma ainda está em
transição: a alíquota de referência não está fixada por Resolução do
Senado, pode mudar, e a reforma em si pode não avançar como está hoje.
Em vez de esperar um número oficial fechado, o usuário testa a própria
hipótese.

`GET /cenarios` lista os cenários visíveis (oficiais/trava legal + os do
próprio tenant), com selo indicando "hipótese sua" nos criados pelo
usuário — o mesmo selo aparece no resultado da simulação (`index.html`)
quando o cenário usado é um deles, para nunca confundir hipótese com
número oficial. `GET/POST /cenarios/novo`: nome, alíquota do IBS e da CBS
(0 a 100%, valida no servidor), fonte e base legal opcionais — inclusive
"e se a reforma for cancelada" é só criar um cenário com 0% e 0%, testado
e o motor responde corretamente (carga simulada zera, mantendo a curva de
transição já calibrada pros tributos antigos). Cenário nasce no
`tenant_id` do usuário logado, visível para todo mundo do mesmo tenant —
não é uma preferência pessoal, é um parâmetro de simulação compartilhado.
Não tem editar nem excluir cenário ainda, só criar — fica pra depois se
precisar.

**Atalho na própria tela de simulação:** em vez de obrigar ir em
"Cenários" criar um antes, `POST /simular` aceita `ibs_personalizado` e
`cbs_personalizado` (campos de texto opcionais, ao lado do `<select>` de
cenário) — digitou os dois, a rota valida com `fracao_validada` e
procura/cria um `CenarioAliquota` (`tipo=TipoCenario.USUARIO`, nome
`"Personalizado (IBS X% + CBS Y%)"`) no tenant do usuário, reaproveitando
se já existir um igual (dedupe por `aliquota_ibs`+`aliquota_cbs` exatos).
Preencheu os campos → vale mais que o `<select>`; deixou em branco → volta
pro fluxo normal do cenário escolhido. Continua aparecendo depois na lista
de Cenários, com o mesmo selo "hipótese sua".

**Anexos II, IV e V completados (antes vazios).** Simular uma empresa do
Simples com Anexo II, IV ou V dava
`ForaDoSimples("Anexo não parametrizado nesta versão de regras.")` — os
dois anexos tinham tabela (I e III), os outros três estavam vazios de
propósito no seed inicial. Preenchidos em `app/seeds/regras_iniciais.py`
com a tabela oficial (LC 123/2006, redação LC 155/2016, em vigor desde
2018 — a reforma não mexeu nesses percentuais), conferida contra duas
fontes independentes. Anexo I a V cadastrados hoje.

## Histórico de simulações (RF08/RF10/RF11)

`app/models/simulacao.py` (`Simulacao`, `AnaliseIA`) já existia desde o
início do projeto — modelo pronto, tabela migrada, nada usava. Toda
`POST /simular` bem sucedida agora grava uma linha ali, sem passo extra de
"salvar": é histórico automático, não um recurso à parte.

- `_salvar_simulacao()` em `app/web/rotas.py`, chamada logo depois do
  motor calcular. Congela um snapshot do que entrou (`dados_informados` —
  a `EntradaSimulacao` inteira, serializada; `cenario_aliquota_snapshot`;
  `regras_snapshot`) e do que saiu (`resultado`, o dicionário completo do
  motor) — editar o cenário ou a versão de regras depois não altera
  retroativamente o que já foi salvo (é a garantia que a própria docstring
  do modelo já pedia). Desnormaliza `carga_atual_rs`/`carga_futura_rs`/
  `diferenca_rs`/`diferenca_pct` pra listar sem reabrir o JSON toda vez.
- Se a análise por IA respondeu (aprovada ou reprovada — `resposta_bruta`
  não nulo), grava também um `AnaliseIA` ligado 1:1 (prompt enviado,
  resposta bruta e renderizada, status da verificação, tokens, latência).
  Quando a IA está indisponível não há o que auditar, então não grava —
  a tela de histórico mostra "IA não respondeu nesta simulação" nesse caso.
- `app/web/historico.py`: `GET /historico` lista (tenant-scoped, admin
  atravessa todos), mais recente primeiro; `GET /historico/{id}` reabre
  uma simulação salva. As duas telas reusam `app/web/templates/_resultado.html`
  — o mesmo bloco de resultado que aparece logo depois de `POST /simular`
  foi extraído da `index.html` pra não duplicar entre "acabei de simular" e
  "abri uma do histórico".
- **Fecha também a lacuna de integridade do chat** (documentada há tempo,
  ver seção "Chat" abaixo): antes, `POST /chat` recebia o contexto de volta
  do navegador a cada pergunta — um usuário podia adulterar esse JSON no
  devtools. Agora recebe só `simulacao_id`, relê `Simulacao.resultado` do
  banco e reconstrói o contexto ali — o servidor nunca mais confia no que o
  cliente diz que é o resultado.
- Testado ao vivo: rodou uma simulação, apareceu em `/historico` com os
  números certos; abriu o detalhe, o gráfico e a análise de IA
  re-renderizaram a partir do que foi salvo (não recalculados); perguntou
  algo no chat da tela de histórico e a resposta veio fundamentada nos
  números daquela simulação salva, sem tocar no motor de novo; id de
  simulação inexistente ou de outro tenant tratado como "não encontrada",
  igual à régua já usada em `/simular` e `/empresas`.
- **RF10 — repetir simulação com parâmetros alterados**: botão "Simular
  novamente (editar parâmetros)" em `/historico/{id}`, leva pra
  `/?repetir={id}`. `GET /` pré-preenche `empresa_id`, `ano_base`,
  `opcao_simples` e o cenário — usa o cenário ao vivo se ele ainda existir e
  estiver ativo, senão reconstrói `ibs_personalizado`/`cbs_personalizado` a
  partir do `cenario_aliquota_snapshot` congelado (o cenário original pode
  ter sido desativado ou excluído depois; o snapshot nunca muda). Reusa o
  mesmo mecanismo de repopulação de formulário que já existia pra reexibir
  erro de validação — não é campo novo, é o `selecionado` de sempre
  alimentado por uma fonte diferente.
- **O que ficou de fora**: `LogAuditoria` (existe no modelo, não é
  gravado ainda — não há ainda uma ação sensível o bastante pra justificar
  auditar, mas fica pronto pro dia que precisar), edição/exclusão de uma
  simulação salva, e filtro por empresa na listagem do histórico (só
  ordena por data por enquanto).

## Exportação e impressão (RF07)

Botão "Imprimir / Exportar PDF" no topo do bloco de resultado (aparece
tanto numa simulação recém-rodada quanto reaberta do histórico, já que as
duas telas reusam `_resultado.html`) chama `window.print()` — o próprio
navegador oferece "Salvar como PDF" no diálogo de impressão. Decisão
consciente: gerar PDF no servidor pediria uma biblioteca nova (WeasyPrint
ou equivalente) e mais uma peça pra instalar/manter no Render; o navegador
já resolve sem dependência nenhuma, mesmo raciocínio que já valeu pra não
usar lib de gráfico no RF06.

Uma classe `.no-imprimir` esconde no papel o que só faz sentido na tela —
menu de navegação, o formulário de "Nova simulação", o botão de imprimir
e o chat (conversa interativa não cabe em relatório impresso). Um bloco
`@media print` em `base.html` força a paleta clara mesmo com o tema escuro
ativo (senão sai ilegível/gasta tinta à toa) e tira sombra dos cartões.

**Achado testando**: sobrescrever as variáveis de cor dentro de `@media
print { :root { ... } }` não bastava — `:root[data-theme="dark"]` é mais
específico que `:root` puro, então continuava ganhando mesmo estando fora
do media query de impressão. Corrigido com `!important` em cada variável
do bloco de impressão (única forma de vencer especificidade sem duplicar o
seletor). Testado reaproveitando a regra `@media print` de verdade da
folha de estilo (reescopada pra `@media screen` via JS só pra visualizar
sem imprimir de fato) — confirmado com tema escuro ativo: fundo e texto
dos cartões viram claro/escuro (não claro/claro), menu, formulário e chat
somem, gráfico de barras mantém a altura (usa `height` fixo em pixels, não
depende de viewport).

## Autenticação

Login por cookie de sessão (JWT assinado, `argon2-cffi` no hash da senha —
ambos já eram dependência do projeto, nada novo). `Usuario.tenant_id`
decide o que a conta enxerga: quem não é `admin` só vê empresas e cenários
do próprio tenant; `admin` atravessa todos. Isso vale tanto na tela (`/`,
`/simular`) quanto na API (`/api/empresas`) — inclusive contra tentar
simular uma empresa de outro tenant digitando o id direto no formulário
(tratada como inexistente, não como 403, para não revelar que o id existe).

**Sem cadastro público.** Contas são criadas por quem já é admin, com:

```bash
python -m scripts.criar_usuario --email joao@escritorio.com --nome "João" \
    --tenant-nome "Escritório João Contábil" --tenant-tipo escritorio
```

`python -m scripts.seed` já deixa três contas prontas para desenvolvimento:

| Conta | Tenant | Papel | Senha |
|---|---|---|---|
| `denisdhein@gmail.com` | Administração | admin | gerada e impressa no primeiro seed (ou `ADMIN_SENHA` no ambiente) |
| `contador@escritoriodemo.local` | Escritório Demonstração (Distribuidora + Metalúrgica) | gestor | `demo12345` |
| `financeiro@consultoriaaurora.local` | Consultoria Aurora ME | gestor | `demo12345` |

A senha do admin não fica em lugar nenhum do código — se você perdê-la,
apague o usuário e rode o seed de novo, ou defina `ADMIN_SENHA` antes de
rodar. As duas contas "demo" têm senha fixa de propósito: são só empresas
fictícias, não guardam nada a proteger, e a senha previsível ajuda a testar
isolamento de tenant sem caçar log.

**Pendências conscientes:** sem "esqueci minha senha", sem expiração de
sessão configurável além do fixo em `app/auth/seguranca.py` (12h), sem tela
de admin para gerenciar contas pela web (fica no CLI por enquanto).

## IA generativa

`app/ia/` — a camada que faltava para fechar o princípio central do TCC:
*o motor calcula, a IA explica*. Fluxo em `POST /simular`, depois que o
motor já produziu `resultado`:

1. **`prompt.py`** monta o prompt. A IA recebe `resultado["referencias"]`
   (o mapa chave → valor que o motor já expõe para isso) e uma instrução
   fixa: só pode citar número no formato `{{chave}}`, nunca dígito solto —
   nem por extenso. Sem essa regra a "IA explica" vira "IA inventa".
2. **`cliente.py`** chama o modelo (`openai`, `OPENAI_MODEL` em
   `app/config.py`, padrão `gpt-4o-mini`). Timeout de 30s. Qualquer falha
   (sem chave, rede, quota, sobrecarga do provedor) vira `IAIndisponivel`
   — vira aviso na tela, nunca 500.

   Era Gemini (`google-genai`) até 31/08/2026: trocado porque o único
   modelo disponível na chave testada (`gemini-3.6-flash`, recém-lançado —
   `gemini-2.0-flash` e `gemini-2.5-flash` já tinham saído de linha para
   chaves novas) respondeu com timeout e 503 de sobrecarga em sequência,
   inviabilizando demo ao vivo. O módulo existe isolado exatamente para
   essa troca custar pouco — só `cliente.py` mudou, prompt/verificação/
   renderização ficaram intactos.
3. **`verificacao.py`** roda antes de qualquer usuário ver o texto:
   toda `{{chave}}` citada precisa existir em `referencias` (estrutural,
   confiável — é o núcleo do checklist do TCC I, seção 4.4); mais três
   checagens heurísticas por palavra-chave (número solto fora do formato,
   ausência do aviso de revisão contábil, linguagem de certeza jurídica,
   direção incoerente com o resultado). Falhou uma checagem, a resposta é
   **descartada inteira** — não existe "renderiza mesmo assim".
4. **`renderizador.py`** só roda depois de aprovado: troca `{{chave}}`
   pelo valor formatado (`app/formatacao.py`, mesma função dos filtros
   Jinja da tela — um valor não pode ser exibido diferente na tela e na
   explicação da IA).

Três estados chegam ao template (`analise.status`): `aprovada` (mostra o
texto), `reprovada` (mostra o motivo, números do motor continuam na tela
normalmente) ou `indisponivel` (sem chave configurada, ou erro do
provedor — mesma ideia, a simulação não depende da IA para ser útil).

**Para ligar**: coloque uma chave em `OPENAI_API_KEY` no `.env` (chave em
https://platform.openai.com/api-keys, precisa de billing habilitado). Sem
isso, a tela funciona normalmente e mostra "análise por IA indisponível" —
testado assim.

**Bug real pego rodando com a chave de verdade**: `_formatar()` em
`renderizador.py` decidia se uma chave era percentual com
`chave.endswith("_pct")` — `atual.carga_pct_receita` e
`futuro.carga_pct_receita` têm `_pct` no meio do nome, não no fim, então
caíam no `return valor` cru: a análise mostrou "0.201800 da receita" em
vez de "20,18%". Trocado para `"_pct" in chave` (substring). A verificação
não pegou porque o texto usava `{{chave}}` corretamente — o defeito era só
na formatação, depois da aprovação. Ficou mais claro depois disso que o
`_formatar()` é uma lista branca: uma chave nova do motor que não bata em
nenhum dos quatro casos (`_rs`, `_pct`, `aliquota_efetiva`,
`margem_liquida`) sai crua da mesma forma, sem avisar. Não tem teste
automatizado cobrindo isso ainda — achado por inspeção visual do
resultado, não por suíte.

### Chat — perguntas sobre o resultado

Abaixo da análise, `POST /chat` deixa perguntar em linguagem livre sobre a
simulação ("por que a carga caiu tanto?", "essa empresa pode optar pelo
Simples híbrido?") sem reload de página — `fetch()` simples em
`<script>` no fim de `index.html`, sem framework, sem build step.

Passa pela mesma tubulação de `analisar()` (`app/ia/servico.py`:
`_executar()` compartilhado), só que com `modo_relatorio=False`: a
verificação continua exigindo que toda `{{chave}}` citada exista de
verdade (isso nunca afrouxa), mas não exige mais que toda resposta cite
alguma referência nem que sempre feche com "procure um contador" — faria
sentido numa análise de uma tacada, rejeitaria de forma errada uma
resposta de chat que é só conceitual ("o que é IBS?"). Testado com
pergunta simples, pergunta de acompanhamento usando o histórico da
conversa, e sem login (401).

**Contexto lido do banco por id (fechado em 03/09/2026, ver RF08/RF11
abaixo):** `POST /chat` recebe `simulacao_id`, relê `Simulacao.resultado`
do banco e reconstrói o contexto ali — o navegador não reenvia mais o JSON
a cada pergunta. Antes disso, a tela embutia `resultado["referencias"]` num
`<script type="application/json">` e o cliente reenviava esse mesmo bloco;
um usuário autenticado podia adulterar esse contexto no devtools e fazer a
IA "confirmar" números fabricados só na própria tela dele. Não expunha dado
de outro tenant nem quebrava a aplicação, mas era uma lacuna de integridade
real — fechada junto com a persistência da simulação, que é exatamente o
que criou o "id" pelo qual reler.

A verificação de "coerência de direção" e de "certeza jurídica" continua
heurística por palavra-chave, não NLU — pega o grosseiro, não substitui
leitura humana da resposta antes de usar em produção.

## Decisões que já estão embutidas no código

**`tenant_id` em toda tabela de negócio.** Retrofitar multi-tenant depois é
doloroso. Empresa direta é um tenant com uma empresa; escritório é um tenant
com várias. Mesmo objeto.

**`RegrasVersao` é imutável.** Alterar cria versão nova. É o que permite
representar 2026 a 2033 e sobreviver a mudança legislativa durante a pesquisa
sem reescrever código.

**`Simulacao` guarda snapshot congelado.** Os campos `*_snapshot` congelam
tudo que entrou no cálculo. As FKs servem só para rastreabilidade. Sem isso,
editar um cenário no painel admin alteraria retroativamente simulações antigas.

**`CustoEmpresa.pct_fornecedor_simples`.** Comprar de fornecedor do Simples em
regime único limita o crédito do adquirente. Sem esse campo o motor
superestima o crédito de quem tem cadeia de fornecedores pequenos.

**`Simulacao.grupo_comparacao` + `opcao_simples`.** Uma análise do Simples gera
duas linhas — regime único e híbrido — amarradas pelo mesmo grupo.

**Numeric, nunca float.** Monetário em `Numeric(18,2)`, alíquotas em
`Numeric(9,6)` como fração. Erro de arredondamento em cálculo tributário é
indefensável em banca.

## Status dos dados de parâmetro

Ver o cabeçalho de `app/seeds/regras_iniciais.py`. Resumo:

- **Calendário da transição** — conforme EC 132/2023 e LC 214/2025. *Conferir
  contra o texto legal antes da defesa.*
- **Alíquotas de referência** — não fixadas por Resolução do Senado. Não vivem
  nas regras: vivem em `CenarioAliquota`, trocáveis sem tocar no código.
  Dois cenários carregados: trava legal de 26,5% (LC 214/2025, art. 475, §11)
  e estimativa CGIBS de 27,91% (Resolução 14, de 29/07/2026).
- **Anexos I a V do Simples** — completos (LC 123/2006, redação LC 155/2016,
  em vigor desde 01/01/2018; a reforma não alterou esses percentuais).
- **Partilha de IBS/CBS no DAS do Simples** (`SIMPLES["partilha_ibs_cbs"]`)
  — pesquisado (Resolução CGSN 190/2026, duas fontes), não o texto oficial
  direto. *Conferir contra o DOU antes da defesa.* `fator_credito_
  fornecedor_simples` (parâmetro separado, comprador do regime regular)
  continua fictício — ver "Calibrações do motor".
- **Imposto Seletivo** — desligado. Alíquotas dependem de lei ainda não aprovada.

## Limitações declaradas do MVP

Não implementados, por escopo: Fator R, sublimites estaduais, segregação de
receitas, substituição tributária, monofásicos, MEI. Estão listados em
`parametros["simples"]["nao_implementado"]` para aparecerem no relatório.

## Próximo passo

Motor de cálculo: assinatura das funções, formato do `resultado` em JSON e os
identificadores estáveis que a camada de IA vai referenciar.

## Motor de cálculo — estado

Implementado e com 47 testes passando (`pytest tests/`). Cobre: cenário atual
a plena carga como baseline fixo, transição ano a ano de 2026 a 2033 somando
resíduo dos tributos antigos com IBS/CBS, cálculo item a item com queda para
agregado, regimes diferenciados por item, crédito amplo com redução para
fornecedor do Simples, e a comparação Simples único vs. híbrido.

O resultado inclui `referencias`: mapa plano de identificador estável para
valor. É o que a camada de IA vai receber — ela referencia chaves, não digita
números.

### Calibrações do motor

Três pontos apareceram rodando com os perfis do seed. Os três já foram
corrigidos — nenhum com número chutado, todos com base legal real ou
matemática conferida à mão.

**1. Base do IBS/CBS no Simples híbrido — CORRIGIDO (01/09/2026).** Em
`app/motor/simples.py`, a apuração regular do híbrido calculava IBS/CBS sobre
a receita **bruta**, enquanto o resto do motor sempre usa a líquida (mesmo
erro que `test_ignorar_por_fora_superestimaria_a_carga` já cobria para os
outros regimes, só que ninguém tinha escrito o equivalente para o híbrido).
Confirmado à mão com a Distribuidora do seed antes de mexer: `ibs_cbs_por_fora`
batia exatamente `3.200.000 × 26,5% = 848.000,00` — a bruta multiplicada
direto pela alíquota. Corrigido para usar `receita - das_reduzido` (o que
ainda fica embutido no preço depois do IBS/CBS sair do DAS), com
`test_hibrido_usa_receita_liquida_nao_a_bruta` como regressão. Resultado
prático: o gap entre único e híbrido nessa mesma empresa caiu de
R$ 189.851,87 para R$ 107.422,91 (~43% menor) — o híbrido continua mais caro
pra essa empresa específica, mas por uma margem bem menor e agora correta.

**2. Crédito amplo — CORRIGIDO (02/09/2026), com ressalva.** A hipótese
original ("dupla contagem entre a base líquida e o crédito das aquisições")
não se confirmou por leitura do código: débito (sobre receita) e crédito
(sobre custo) usam bases matematicamente independentes, do jeito que um IVA
não cumulativo deveria funcionar. O que apareceu, investigando de verdade,
foi uma **assimetria diferente**: a receita usada no débito é líquida dos
tributos *atuais* (`atual.calcular()` desconta ICMS/PIS/COFINS/ISS antes de
virar base do IBS/CBS), mas o custo usado no crédito
(`CustoEmpresa.valor_anual`) entrava **sem nenhum desconto equivalente** —
credita-se IBS/CBS em cima de um preço que ainda pode carregar imposto
antigo embutido, inflando o crédito.

Três saídas foram avaliadas com o Denis: (A) campo de % de imposto embutido
por linha de custo — mais preciso, mas ninguém sabe esse número de cabeça
por fornecedor, e o formulário de cadastro já é grande; (B) só documentar a
convenção "digite líquido" — zero código, mas não resolve de verdade, quem
preenche vai copiar o valor bruto da nota fiscal do mesmo jeito; (C) um
fator único por empresa, aplicado a todos os custos — meio-termo, mesmo
padrão que `pct_compras_com_credito` já usa pro sistema atual. **Escolhida:
opção C.**

Novo campo `Empresa.pct_imposto_embutido_custos` (migration `ff825da42c0e`),
propagado por `EntradaSimulacao.pct_imposto_embutido_custos` até
`futuro.calcular_creditos()` e o crédito do híbrido em `simples.py` (ambos
tinham o mesmo problema — corrigidos juntos). Desconta a fração informada de
`custo.valor_anual` antes de aplicar a alíquota nova:
`credito = valor_anual × (1 − fator) × aliq_total`. Não informado (padrão)
mantém o comportamento anterior — testes antigos passam sem alteração.
Testado com números exatos (`test_pct_imposto_embutido_desconta_credito_do_custo`,
`test_simples_hibrido_tambem_desconta_imposto_embutido`) e ao vivo: editando
a Metalúrgica do seed com 20% de imposto embutido, a carga simulada de 2033
subiu de R$ 492.900,00 (1,76% da receita — o resultado suspeito original) para
R$ 1.414.570,00 (5,05% da receita), com a limitação exibindo a premissa
usada ("Crédito de IBS/CBS sobre custos descontado em 20,00%..."). Campo de
formulário em "Custos e despesas" no cadastro de empresa, com texto de ajuda
explicando o que é — deixado em branco assume 0% (nenhuma mudança).

**Opção A implementada também (04/09/2026), como refinamento sobre a C —
não uma troca.** A ressalva acima ("é uma média por empresa, não por
fornecedor") motivou pedir a opção A depois: `CustoEmpresa.pct_imposto_embutido`
(migration `111b3c1a8e87`), um valor por linha de custo que sobrepõe o
padrão da empresa quando informado — mesma regra de override que
`ItemEmpresa` já usa pras alíquotas (`app/web/adaptador.py:_aliq_item`).
Linha sem valor próprio cai no padrão da empresa; empresa sem padrão e
linha sem valor mantém o comportamento de sempre (0%, sem desconto). As
duas opções coexistem por design — C nunca deixou de existir, virou o
"senão" da A. `_limitacao_imposto_embutido()` em `app/motor/calculadora.py`
relata o que foi efetivamente usado: só padrão, só por linha, misto, ou
nenhum desconto — não dá pra resumir num único percentual quando os custos
usam fontes diferentes. Testado com números exatos (3 testes novos,
`test_pct_imposto_embutido_por_linha_*`) e ao vivo contra a Metalúrgica do
seed: sobrepor uma linha de 14,5 milhões (padrão 20%) pra 30% reduziu o
crédito daquela linha especificamente, sem afetar as outras — a limitação
passou a mostrar "1 de 3 linha(s) com valor próprio".

**3. Partilha de IBS/CBS no DAS do Simples — CORRIGIDO (04/09/2026), com uma
ressalva que permanece.** Base legal encontrada em 02/09/2026 (Art. 47 §9º
II da LC 214/2025 + Art. 58 §§4º-5º da Resolução CGSN nº 190/2026): o
crédito que um adquirente do regime regular tem ao comprar de optante do
Simples equivale "aos percentuais de IBS e CBS previstos nos Anexos I a
V... para a faixa de receita bruta" do fornecedor — por **anexo e por
faixa**, com um valor que **cresce a partir de 2029**, não um fixo único
por anexo como o parâmetro `pct_ibs_cbs_no_das` modelava até então.

Na época só tinha um dado real (Anexo I, 2027-2028 = 15,50% do DAS) — não a
tabela completa. Em 04/09/2026, nova pesquisa encontrou duas fontes
independentes com a tabela inteira: mentorfiscal.com.br (base 2027-2028,
todos os 5 anexos) e simtax.com.br (progressão 2029-2033, confirmada pro
Anexo I). As duas batem entre si e com o dado que já tínhamos. Achado que
destravou a implementação: a progressão do IBS dentro do Simples segue
**a mesma escala 10/20/30/40/100%** que o calendário `ANOS` já usa pro
resto do motor — então em vez de uma tabela gigante (5 anexos × 6 faixas ×
7 anos), a fórmula ficou:

```
pct_ibs_cbs_no_das = cbs_fixo + icms_iss_original × fração_ibs_do_ano
```

`cbs_fixo` (CBS já substitui PIS/COFINS por inteiro desde 2027, não muda
mais) e `icms_iss_original` (a fatia de ICMS/ISS que esse anexo/faixa tinha
antes da reforma, migrando gradualmente pra IBS) vêm de
`app/seeds/regras_iniciais.py:PARTILHA_IBS_CBS_SIMPLES` — ver o comentário
completo ali, com a fonte de cada número. `app/motor/simples.py` ganhou
`_pct_ibs_cbs_no_das()`, chamada tanto no regime único (teto do crédito
transferível ao cliente) quanto no híbrido (redução do DAS). Antes de 2027
a Resolução ainda não vale — o motor devolve zero, sem separar IBS/CBS do
DAS (comportamento correto: a mudança só começa em 2027).

**Bug real achado testando ao vivo contra o servidor** (não pego pelos
testes automatizados): as chaves de faixa (`1` a `6`) no dicionário Python
são inteiras, mas `RegrasVersao.parametros` passa por `json.dumps`/
`json.loads` ao ir pro banco e voltar — e JSON não tem chave inteira, toda
chave de objeto vira string nesse round-trip. Rodando os testes (que
importam o dicionário direto do módulo, sem passar pelo banco) tudo batia;
simulando pela tela de verdade, o crédito transferido ficava zerado o
tempo todo, silenciosamente. Corrigido usando string ("1".."6") desde a
origem, mesma convenção que `anexos` já usava. Fica registrado como lição:
testar só contra o módulo Python não pega esse tipo de bug — precisa
passar pelo banco pelo menos uma vez.

3 testes novos com números conferidos à mão (`test_partilha_ibs_cbs_no_das_*`)
e testado ao vivo simulando a Distribuidora do seed (Anexo I, faixa 5) em
2027, 2030 e 2033: o crédito transferido ao cliente no regime único cresce
de R$ 57.396,62 pra R$ 82.206,78 pra R$ 181.447,39 — e o DAS do híbrido
encolhe na mesma proporção, exatamente o comportamento esperado da
transição. 47 testes passando.

**Ressalva que permanece**: os números das faixas 2-5 dos Anexos II a V
foram estendidos pela mesma fórmula do Anexo I (o mecanismo de transição
ICMS/ISS→IBS é do sistema inteiro, não específico de anexo), mas só o
Anexo I teve a progressão ano a ano confirmada nas fontes — os demais são
extrapolação razoável, não confirmação direta. A faixa 6 de todos os
anexos não tem ICMS/ISS no DAS (regra de sublimite à parte) e ficou com um
valor fixo, sem a transição gradual — só o Anexo I teve o salto de 2029
confirmado nas fontes; os outros quatro ficaram conservadoramente planos.
CONFERIR contra o texto oficial da Resolução (DOU 10/08/2026) antes de
usar em defesa. `fator_credito_fornecedor_simples` (parâmetro separado,
usado quando o comprador é do regime regular) continua fictício — é
conceitualmente o mesmo dado, mas consolidar os dois exigiria saber o
anexo/faixa de cada fornecedor por linha de custo, que `CustoEmpresa` não
guarda hoje.
