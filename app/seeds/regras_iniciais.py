"""
Versão inicial de parâmetros do motor.

ATENÇÃO — status dos dados abaixo:

  [CALENDÁRIO]  A sequência da transição segue a EC 132/2023 e a LC 214/2025.
                CONFERIR contra o texto legal antes de usar em defesa.
  [PROVISÓRIO]  As alíquotas de referência NÃO estão fixadas por Resolução do
                Senado. Elas não vivem aqui — vivem em CenarioAliquota, para
                serem trocadas sem tocar no código.
  [A PREENCHER] As reduções temporárias de alíquota do Simples previstas para
                acomodar a entrada da CBS (Anexos I a V já completos — ver
                fonte abaixo).
  [FICTÍCIO]    `fator_credito_fornecedor_simples` continua estimativa de
                trabalho — ver app/motor/futuro.py. `partilha_ibs_cbs`
                (dentro de `simples`) foi pesquisado com fontes reais em
                04/09/2026 (ver comentário acima da definição), mas ainda é
                dado de fonte secundária, não o texto oficial da Resolução.

Nada aqui é constante de código: é linha de banco, versionada e substituível.
"""

from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Calendário da transição
# ---------------------------------------------------------------------------
# Cada ano informa a FRAÇÃO da alíquota cheia que incide sobre cada tributo.
# 1.0 = incidência integral, 0.0 = extinto/não incidente.
#
# 2026        ano-teste: CBS 0,9% e IBS 0,1%, compensáveis
# 2027-2028   CBS integral, PIS/COFINS extintos, IPI zerado (salvo ZFM),
#             IBS ainda em alíquota simbólica, Imposto Seletivo em vigor
# 2029-2032   IBS entra em 1/10, 2/10, 3/10 e 4/10; ICMS e ISS caem para
#             9/10, 8/10, 7/10 e 6/10
# 2033        IBS integral, ICMS e ISS extintos

ANOS = {
    "2026": {"cbs": 0.0, "ibs": 0.0, "pis_cofins": 1.0, "icms": 1.0, "iss": 1.0, "ipi": 1.0,
             "teste_cbs": 0.009, "teste_ibs": 0.001, "compensavel": True},
    "2027": {"cbs": 1.0, "ibs": 0.0, "pis_cofins": 0.0, "icms": 1.0, "iss": 1.0, "ipi": 0.0,
             "ibs_simbolico": 0.001},
    "2028": {"cbs": 1.0, "ibs": 0.0, "pis_cofins": 0.0, "icms": 1.0, "iss": 1.0, "ipi": 0.0,
             "ibs_simbolico": 0.001},
    "2029": {"cbs": 1.0, "ibs": 0.1, "pis_cofins": 0.0, "icms": 0.9, "iss": 0.9, "ipi": 0.0},
    "2030": {"cbs": 1.0, "ibs": 0.2, "pis_cofins": 0.0, "icms": 0.8, "iss": 0.8, "ipi": 0.0},
    "2031": {"cbs": 1.0, "ibs": 0.3, "pis_cofins": 0.0, "icms": 0.7, "iss": 0.7, "ipi": 0.0},
    "2032": {"cbs": 1.0, "ibs": 0.4, "pis_cofins": 0.0, "icms": 0.6, "iss": 0.6, "ipi": 0.0},
    "2033": {"cbs": 1.0, "ibs": 1.0, "pis_cofins": 0.0, "icms": 0.0, "iss": 0.0, "ipi": 0.0},
}

# ---------------------------------------------------------------------------
# Regimes diferenciados — multiplicador sobre a alíquota cheia
# ---------------------------------------------------------------------------
REGIMES_DIFERENCIADOS = {
    "padrao": 1.0,
    "reducao_60": 0.40,      # redução de 60%
    "reducao_30": 0.70,      # redução de 30%
    "cesta_basica": 0.0,     # alíquota zero
    "aliquota_zero": 0.0,
}

# ---------------------------------------------------------------------------
# Simples Nacional
# ---------------------------------------------------------------------------
# Alíquota efetiva = (RBT12 * aliquota - deduzir) / RBT12
# Fonte das tabelas: LC 123/2006, anexos com redação da LC 155/2016, em vigor
# desde 01/01/2018 — a reforma (LC 214/2025) não alterou esses percentuais.
# Anexos II, IV e V completados em 03/09/2026, conferidos contra duas fontes
# independentes (Contabilizei e Mentor Fiscal); Anexo IV é "sem CPP no DAS"
# (construção, vigilância, limpeza, advocacia — INSS patronal recolhido à
# parte); Anexo V é o de Fator R baixo (< 28% de folha/receita — acima disso
# migra para o Anexo III, mais barato). CONFERIR contra o texto legal antes
# de usar em defesa.

ANEXO_I = [  # Comércio
    {"faixa": 1, "ate": 180000.00,  "aliquota": 0.0400, "deduzir": 0.00},
    {"faixa": 2, "ate": 360000.00,  "aliquota": 0.0730, "deduzir": 5940.00},
    {"faixa": 3, "ate": 720000.00,  "aliquota": 0.0950, "deduzir": 13860.00},
    {"faixa": 4, "ate": 1800000.00, "aliquota": 0.1070, "deduzir": 22500.00},
    {"faixa": 5, "ate": 3600000.00, "aliquota": 0.1430, "deduzir": 87300.00},
    {"faixa": 6, "ate": 4800000.00, "aliquota": 0.1900, "deduzir": 378000.00},
]

ANEXO_II = [  # Indústria
    {"faixa": 1, "ate": 180000.00,  "aliquota": 0.0450, "deduzir": 0.00},
    {"faixa": 2, "ate": 360000.00,  "aliquota": 0.0780, "deduzir": 5940.00},
    {"faixa": 3, "ate": 720000.00,  "aliquota": 0.1000, "deduzir": 13860.00},
    {"faixa": 4, "ate": 1800000.00, "aliquota": 0.1120, "deduzir": 22500.00},
    {"faixa": 5, "ate": 3600000.00, "aliquota": 0.1470, "deduzir": 85500.00},
    {"faixa": 6, "ate": 4800000.00, "aliquota": 0.3000, "deduzir": 720000.00},
]

ANEXO_III = [  # Serviços em geral
    {"faixa": 1, "ate": 180000.00,  "aliquota": 0.0600, "deduzir": 0.00},
    {"faixa": 2, "ate": 360000.00,  "aliquota": 0.1120, "deduzir": 9360.00},
    {"faixa": 3, "ate": 720000.00,  "aliquota": 0.1350, "deduzir": 17640.00},
    {"faixa": 4, "ate": 1800000.00, "aliquota": 0.1600, "deduzir": 35640.00},
    {"faixa": 5, "ate": 3600000.00, "aliquota": 0.2100, "deduzir": 125640.00},
    {"faixa": 6, "ate": 4800000.00, "aliquota": 0.3300, "deduzir": 648000.00},
]

ANEXO_IV = [  # Serviços sem CPP no DAS (construção, vigilância, limpeza, advocacia etc.)
    {"faixa": 1, "ate": 180000.00,  "aliquota": 0.0450, "deduzir": 0.00},
    {"faixa": 2, "ate": 360000.00,  "aliquota": 0.0900, "deduzir": 8100.00},
    {"faixa": 3, "ate": 720000.00,  "aliquota": 0.1020, "deduzir": 12420.00},
    {"faixa": 4, "ate": 1800000.00, "aliquota": 0.1400, "deduzir": 39780.00},
    {"faixa": 5, "ate": 3600000.00, "aliquota": 0.2200, "deduzir": 183780.00},
    {"faixa": 6, "ate": 4800000.00, "aliquota": 0.3300, "deduzir": 828000.00},
]

ANEXO_V = [  # Serviços sujeitos ao Fator R (< 28% de folha/receita)
    {"faixa": 1, "ate": 180000.00,  "aliquota": 0.1550, "deduzir": 0.00},
    {"faixa": 2, "ate": 360000.00,  "aliquota": 0.1800, "deduzir": 4500.00},
    {"faixa": 3, "ate": 720000.00,  "aliquota": 0.1950, "deduzir": 9900.00},
    {"faixa": 4, "ate": 1800000.00, "aliquota": 0.2050, "deduzir": 17100.00},
    {"faixa": 5, "ate": 3600000.00, "aliquota": 0.2300, "deduzir": 62100.00},
    {"faixa": 6, "ate": 4800000.00, "aliquota": 0.3050, "deduzir": 540000.00},
]

# ---------------------------------------------------------------------------
# Partilha de IBS/CBS dentro do DAS — Resolução CGSN nº 190/2026
# ---------------------------------------------------------------------------
# Art. 58, §§4º-5º da Resolução: o crédito que um adquirente do regime
# regular tem ao comprar de optante do Simples (regime único) equivale "aos
# percentuais de IBS e CBS previstos nos Anexos I a V [da Resolução]... para
# a faixa de receita bruta" do fornecedor — o mesmo número usado aqui pra
# reduzir o DAS no regime híbrido e pra tetar o crédito transferível no
# único. A Resolução prevê um valor por ANO e por FAIXA (cresce a partir de
# 2029), não um fixo único por anexo como a versão anterior deste seed tinha.
#
# `cbs_fixo`: total de CBS + resíduo simbólico de IBS já embutido no DAS em
# 2027-2028 (não muda depois — CBS já substitui PIS/COFINS por completo
# desde 2027). `icms_iss_original`: a fatia de ICMS ou ISS que esse anexo/
# faixa tinha no DAS ANTES da reforma — é ela que migra gradualmente pra IBS
# a partir de 2029, na mesma proporção 10/20/30/40/100% já usada no
# calendário `ANOS` acima (por isso a fórmula em app/motor/simples.py só
# multiplica esse valor pela fração `ibs` do ano, sem duplicar a escala).
# `None` = faixa 6 de cada anexo, que não tem ICMS/ISS dentro do DAS (regra
# de sublimite à parte) — mantido com um valor fixo por período, sem a
# transição gradual, ver comentário no motor.
#
# Fontes (pesquisa de 04/09/2026, duas independentes, conferidas entre si e
# contra a EC 132/2023 + LC 214/2025 + calendário já usado no resto do
# motor): mentorfiscal.com.br/tabelas-simples-nacional-2027-2028 (base
# 2027-2028, todos os anexos) e simtax.com.br/simples-nacional-ibs-cbs-
# tabelas-2033 (progressão 2029-2033, confirmada pro Anexo I). A progressão
# dos Anexos II a V foi estendida pela mesma regra do Anexo I — o mecanismo
# de transição ICMS/ISS→IBS é do sistema inteiro (EC 132/2023), não
# específico de anexo, mas não achei a tabela ano a ano publicada pra cada
# um deles individualmente. CONFERIR contra o texto oficial da Resolução
# (DOU 10/08/2026) antes de usar em defesa — mesmo padrão de cautela do
# resto deste arquivo.
# Chave da faixa é string ("1".."6"), não int — mesma convenção de "anexos"
# acima. JSON não tem chave inteira: RegrasVersao.parametros passa por
# json.dumps/json.loads ao ir pro banco e voltar, e nesse round-trip toda
# chave de dict vira string. Usar int aqui faria a consulta bater local
# (import direto do módulo) mas falhar silenciosamente em produção (dict
# vindo do banco, chave "5" não é igual a 5) — achado testando ao vivo
# contra o servidor de verdade, não só os testes automatizados.
PARTILHA_IBS_CBS_SIMPLES = {
    "1": {  # Comércio
        "1": {"cbs_fixo": 0.1550, "icms_iss_original": 0.3400},
        "2": {"cbs_fixo": 0.1550, "icms_iss_original": 0.3400},
        "3": {"cbs_fixo": 0.1550, "icms_iss_original": 0.3350},
        "4": {"cbs_fixo": 0.1550, "icms_iss_original": 0.3350},
        "5": {"cbs_fixo": 0.1550, "icms_iss_original": 0.3350},
        "6": {"cbs_fixo": 0.3402, "cbs_fixo_2029": 0.3440, "icms_iss_original": None},
        # ^ faixa 6 confirmada nas duas fontes, inclusive o salto pra 2029.
        # As faixas 6 dos Anexos II a V abaixo não tiveram essa confirmação
        # (as fontes só mostraram a progressão completa pro Anexo I) —
        # mantidas planas (`cbs_fixo_2029` = `cbs_fixo`) por cautela, não
        # porque a faixa 6 desses anexos realmente não mude a partir de 2029.
    },
    "2": {  # Indústria
        "1": {"cbs_fixo": 0.1400, "icms_iss_original": 0.3200},
        "2": {"cbs_fixo": 0.1400, "icms_iss_original": 0.3200},
        "3": {"cbs_fixo": 0.1400, "icms_iss_original": 0.3200},
        "4": {"cbs_fixo": 0.1400, "icms_iss_original": 0.3200},
        "5": {"cbs_fixo": 0.1400, "icms_iss_original": 0.3200},
        "6": {"cbs_fixo": 0.2522, "cbs_fixo_2029": 0.2522, "icms_iss_original": None},
    },
    "3": {  # Serviços em geral
        "1": {"cbs_fixo": 0.1560, "icms_iss_original": 0.3350},
        "2": {"cbs_fixo": 0.1710, "icms_iss_original": 0.3200},
        "3": {"cbs_fixo": 0.1660, "icms_iss_original": 0.3250},
        "4": {"cbs_fixo": 0.1660, "icms_iss_original": 0.3250},
        "5": {"cbs_fixo": 0.1560, "icms_iss_original": 0.3350},
        "6": {"cbs_fixo": 0.1929, "cbs_fixo_2029": 0.1929, "icms_iss_original": None},
    },
    "4": {  # Serviços sem CPP no DAS
        "1": {"cbs_fixo": 0.2150, "icms_iss_original": 0.4450},
        "2": {"cbs_fixo": 0.2500, "icms_iss_original": 0.4000},
        "3": {"cbs_fixo": 0.2400, "icms_iss_original": 0.4000},
        "4": {"cbs_fixo": 0.2300, "icms_iss_original": 0.4000},
        "5": {"cbs_fixo": 0.2200, "icms_iss_original": 0.4000},
        "6": {"cbs_fixo": 0.2470, "cbs_fixo_2029": 0.2470, "icms_iss_original": None},
    },
    "5": {  # Fator R
        "1": {"cbs_fixo": 0.1715, "icms_iss_original": 0.1400},
        "2": {"cbs_fixo": 0.1715, "icms_iss_original": 0.1700},
        "3": {"cbs_fixo": 0.1815, "icms_iss_original": 0.1900},
        "4": {"cbs_fixo": 0.1915, "icms_iss_original": 0.2100},
        "5": {"cbs_fixo": 0.1715, "icms_iss_original": 0.2350},
        "6": {"cbs_fixo": 0.1978, "cbs_fixo_2029": 0.1978, "icms_iss_original": None},
    },
}

SIMPLES = {
    "anexos": {
        "1": ANEXO_I,
        "2": ANEXO_II,
        "3": ANEXO_III,
        "4": ANEXO_IV,
        "5": ANEXO_V,
    },
    "partilha_ibs_cbs": PARTILHA_IBS_CBS_SIMPLES,
    "limite_rbt12": 4800000.00,
    # Limitações declaradas do MVP — o motor não implementa:
    "nao_implementado": [
        "fator_r",
        "sublimites_estaduais",
        "segregacao_de_receitas",
        "substituicao_tributaria",
        "monofasicos",
        "mei",
    ],
}

IMPOSTO_SELETIVO = {
    # Alíquotas dependem de lei ainda não aprovada. Desligado por padrão.
    "habilitado": False,
    "aliquotas": {},
}

# Fração do crédito cheio que uma compra de fornecedor optante pelo Simples
# em regime único transfere ao adquirente. [FICTÍCIO] valor de trabalho —
# é o parâmetro que decide a comparação único vs. híbrido.
#
# Pesquisa de 02/09/2026 (ver README "Calibrações do motor"): a base legal
# não é um fator uniforme como este. Art. 47, §9º, II da LC 214/2025 diz
# que o crédito é "em montante equivalente ao devido" pelo fornecedor via
# DAS; Art. 58, §§4º-5º da Resolução CGSN nº 190/2026 detalha que esse
# montante é o percentual de IBS/CBS do Anexo E FAIXA do fornecedor
# específico — ou seja, é conceitualmente o mesmo dado que
# `SIMPLES["partilha_ibs_cbs"]` acima já representa (completado em
# 04/09/2026), não um segundo parâmetro independente. Consolidar os dois
# num só exigiria saber o anexo/faixa de cada fornecedor por linha de
# custo, dado que `CustoEmpresa` não guarda hoje (só a fração comprada de
# fornecedor Simples, sem saber qual anexo). Mantido como está por ora —
# mudar a estrutura de dados é decisão maior que só trocar este número.
FATOR_CREDITO_FORNECEDOR_SIMPLES = 0.25

PARAMETROS_INICIAIS = {
    "anos": ANOS,
    "fator_credito_fornecedor_simples": FATOR_CREDITO_FORNECEDOR_SIMPLES,
    "regimes_diferenciados": REGIMES_DIFERENCIADOS,
    "simples": SIMPLES,
    "imposto_seletivo": IMPOSTO_SELETIVO,
    "notas": {
        "por_dentro": ["icms", "iss", "pis", "cofins"],
        "por_fora": ["ibs", "cbs"],
    },
}

VERSAO_INICIAL = {
    "versao": "2026.08.1",
    "descricao": "Versão inicial. Calendário conforme EC 132/2023 e LC 214/2025. "
                 "Anexos I a V do Simples completos (LC 155/2016). "
                 "Partilha IBS/CBS no DAS pesquisada (Resolução CGSN 190/2026), "
                 "fator_credito_fornecedor_simples ainda fictício.",
    "parametros": PARAMETROS_INICIAIS,
    "vigencia_inicio": datetime(2026, 1, 1, tzinfo=timezone.utc),
}

# ---------------------------------------------------------------------------
# Cenários de alíquota
# ---------------------------------------------------------------------------
CENARIOS_INICIAIS = [
    {
        "nome": "Trava legal (26,5%)",
        "aliquota_ibs": 0.177000,
        "aliquota_cbs": 0.088000,
        "fonte": "LC 214/2025",
        "base_legal": "LC 214/2025, art. 475, §11",
        "data_publicacao": datetime(2025, 1, 16, tzinfo=timezone.utc),
        "tipo": "trava_legal",
    },
    {
        "nome": "Estimativa CGIBS (27,91%)",
        "aliquota_ibs": 0.187000,
        "aliquota_cbs": 0.092100,
        "fonte": "Resolução CGIBS nº 14, de 29/07/2026",
        "base_legal": "Estimativa prospectiva para orçamento de 2027",
        "data_publicacao": datetime(2026, 7, 29, tzinfo=timezone.utc),
        "tipo": "oficial",
    },
]
