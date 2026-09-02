"""
Versão inicial de parâmetros do motor.

ATENÇÃO — status dos dados abaixo:

  [CALENDÁRIO]  A sequência da transição segue a EC 132/2023 e a LC 214/2025.
                CONFERIR contra o texto legal antes de usar em defesa.
  [PROVISÓRIO]  As alíquotas de referência NÃO estão fixadas por Resolução do
                Senado. Elas não vivem aqui — vivem em CenarioAliquota, para
                serem trocadas sem tocar no código.
  [A PREENCHER] Anexos II, IV e V do Simples, e as reduções temporárias de
                alíquota do Simples previstas para acomodar a entrada da CBS.
  [FICTÍCIO]    `pct_ibs_cbs_no_das` são estimativas de trabalho, para o motor
                ter o que consumir. Substituir por apuração fundamentada.

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
# Fonte das tabelas: LC 123/2006, anexos com redação da LC 155/2016. CONFERIR.

ANEXO_I = [  # Comércio
    {"faixa": 1, "ate": 180000.00,  "aliquota": 0.0400, "deduzir": 0.00},
    {"faixa": 2, "ate": 360000.00,  "aliquota": 0.0730, "deduzir": 5940.00},
    {"faixa": 3, "ate": 720000.00,  "aliquota": 0.0950, "deduzir": 13860.00},
    {"faixa": 4, "ate": 1800000.00, "aliquota": 0.1070, "deduzir": 22500.00},
    {"faixa": 5, "ate": 3600000.00, "aliquota": 0.1430, "deduzir": 87300.00},
    {"faixa": 6, "ate": 4800000.00, "aliquota": 0.1900, "deduzir": 378000.00},
]

ANEXO_III = [  # Serviços em geral
    {"faixa": 1, "ate": 180000.00,  "aliquota": 0.0600, "deduzir": 0.00},
    {"faixa": 2, "ate": 360000.00,  "aliquota": 0.1120, "deduzir": 9360.00},
    {"faixa": 3, "ate": 720000.00,  "aliquota": 0.1350, "deduzir": 17640.00},
    {"faixa": 4, "ate": 1800000.00, "aliquota": 0.1600, "deduzir": 35640.00},
    {"faixa": 5, "ate": 3600000.00, "aliquota": 0.2100, "deduzir": 125640.00},
    {"faixa": 6, "ate": 4800000.00, "aliquota": 0.3300, "deduzir": 648000.00},
]

SIMPLES = {
    "anexos": {
        "1": ANEXO_I,
        "2": [],     # [A PREENCHER] Indústria
        "3": ANEXO_III,
        "4": [],     # [A PREENCHER] Serviços com CPP por fora
        "5": [],     # [A PREENCHER] Serviços sujeitos ao Fator R
    },
    # Fração da alíquota efetiva do DAS que corresponde a IBS+CBS.
    # É o teto do crédito transferível ao adquirente no regime único.
    # [FICTÍCIO] valores de trabalho.
    "pct_ibs_cbs_no_das": {"1": 0.16, "2": 0.16, "3": 0.14, "4": 0.14, "5": 0.14},
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
# é o parâmetro que decide a comparação único vs. híbrido. Fundamentar.
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
                 "Anexos II, IV e V do Simples pendentes. pct_ibs_cbs_no_das fictício.",
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
