"""
Testes do motor. A matemática é conferida na mão, não contra o próprio motor.
"""

from decimal import Decimal as D

import pytest

from app.motor import CustoEntrada, EntradaSimulacao, ItemEntrada, calcular
from app.motor.simples import ForaDoSimples, aliquota_efetiva
from app.seeds.regras_iniciais import PARAMETROS_INICIAIS as P

IBS = D("0.187")
CBS = D("0.0921")


def empresa_real(**kw):
    base = dict(
        razao_social="Teste Real",
        regime="real",
        faturamento_anual=D("1000000.00"),
        aliq_icms=D("0.17"), aliq_pis=D("0.0165"), aliq_cofins=D("0.076"),
        pct_compras_com_credito=D("1"),
        custos=[CustoEntrada("insumos", D("400000.00"), D("0"), True)],
    )
    base.update(kw)
    return EntradaSimulacao(**base)


# --------------------------------------------------------------------------
# Cenário atual
# --------------------------------------------------------------------------

def test_debitos_atuais_conferem_na_mao():
    """1.000.000 * (17% + 1,65% + 7,6%) = 262.500,00"""
    r = calcular(empresa_real(), 2026, IBS, CBS, P)
    assert r["atual"]["total_debitos_rs"] == "262500.00"


def test_creditos_atuais_conferem_na_mao():
    """400.000 * (1,65% + 7,6% + 17%) = 105.000,00"""
    r = calcular(empresa_real(), 2026, IBS, CBS, P)
    assert r["atual"]["creditos_rs"] == "105000.00"
    assert r["atual"]["carga_liquida_rs"] == "157500.00"


def test_ano_2026_nao_tem_ibs_cbs():
    """2026 é ano-teste: as frações de IBS e CBS são zero."""
    r = calcular(empresa_real(), 2026, IBS, CBS, P)
    assert r["futuro"]["tributos_rs"]["ibs"] == "0.00"
    assert r["futuro"]["tributos_rs"]["cbs"] == "0.00"


def test_baseline_nao_muda_com_o_ano_simulado():
    """`atual` é referência fixa: o sistema vigente a plena carga."""
    a = calcular(empresa_real(), 2027, IBS, CBS, P)["atual"]
    b = calcular(empresa_real(), 2033, IBS, CBS, P)["atual"]
    assert a == b
    assert a["total_debitos_rs"] == "262500.00"


def test_2027_extingue_pis_cofins_mantem_icms_no_ano_simulado():
    trib = calcular(empresa_real(), 2027, IBS, CBS, P)["futuro"]["tributos_rs"]
    assert "pis" not in trib and "cofins" not in trib
    assert D(trib["icms"]) > 0
    assert D(trib["cbs"]) > 0


def test_2033_extingue_icms_e_iss_no_ano_simulado():
    trib = calcular(empresa_real(), 2033, IBS, CBS, P)["futuro"]["tributos_rs"]
    assert "icms" not in trib and "iss" not in trib
    assert D(trib["ibs"]) > 0


def test_transicao_soma_os_dois_sistemas():
    """Em 2030 a empresa paga resíduo de ICMS e mais IBS/CBS."""
    f = calcular(empresa_real(), 2030, IBS, CBS, P)["futuro"]
    assert D(f["debitos_antigos_residuais_rs"]) > 0
    assert D(f["debitos_novos_rs"]) > 0


def test_curva_da_transicao_e_monotonica_no_ibs():
    """O IBS entra em 1/10, 2/10, 3/10, 4/10 e depois cheio."""
    valores = [
        D(calcular(empresa_real(), ano, IBS, CBS, P)["futuro"]["tributos_rs"]["ibs"])
        for ano in (2029, 2030, 2031, 2032, 2033)
    ]
    assert valores == sorted(valores)
    assert valores[0] < valores[-1]


def test_ano_fora_da_parametrizacao_falha():
    with pytest.raises(ValueError, match="não parametrizado"):
        calcular(empresa_real(), 2040, IBS, CBS, P)


# --------------------------------------------------------------------------
# Por fora vs. por dentro
# --------------------------------------------------------------------------

def test_base_do_ibs_cbs_e_a_receita_liquida_nao_a_bruta():
    """
    A base do novo sistema é menor que o faturamento bruto, porque IBS/CBS
    são por fora. Ignorar isso superestima a carga futura — é o erro mais
    comum neste tipo de simulador.
    """
    r = calcular(empresa_real(), 2033, IBS, CBS, P)
    liquida = D(r["futuro"]["receita_liquida_rs"])
    bruta = D(r["atual"]["receita_bruta_rs"])
    assert liquida < bruta
    assert liquida == bruta - D(r["atual"]["total_debitos_rs"])


def test_ignorar_por_fora_superestimaria_a_carga():
    """Quantifica o erro: aplicar a alíquota sobre a receita bruta infla o IBS."""
    r = calcular(empresa_real(), 2033, IBS, CBS, P)
    correto = D(r["futuro"]["tributos_rs"]["ibs"])
    ingenuo = D(r["atual"]["receita_bruta_rs"]) * IBS
    assert ingenuo > correto


# --------------------------------------------------------------------------
# Crédito e setor de serviços
# --------------------------------------------------------------------------

def test_servicos_ganham_com_credito_amplo():
    """
    Prestador que toma muito serviço quase não credita hoje e credita no novo
    modelo. Se o motor só olhasse alíquota de saída, diria que ele piora.
    """
    servico = EntradaSimulacao(
        razao_social="Consultoria",
        regime="presumido",
        faturamento_anual=D("1000000.00"),
        aliq_iss=D("0.05"), aliq_pis=D("0.0065"), aliq_cofins=D("0.03"),
        pct_compras_com_credito=D("0"),
        custos=[CustoEntrada("servicos_tomados", D("400000.00"), D("0"), False)],
    )
    r = calcular(servico, 2033, IBS, CBS, P)
    assert D(r["futuro"]["creditos_rs"]) > 0
    assert D(r["atual"]["creditos_rs"]) == 0


def test_fornecedor_simples_reduz_credito():
    sem = empresa_real(custos=[CustoEntrada("insumos", D("400000.00"), D("0"), True)])
    com = empresa_real(custos=[CustoEntrada("insumos", D("400000.00"), D("1"), True)])
    r_sem = calcular(sem, 2033, IBS, CBS, P)
    r_com = calcular(com, 2033, IBS, CBS, P)
    assert D(r_com["futuro"]["creditos_rs"]) < D(r_sem["futuro"]["creditos_rs"])


def test_pct_imposto_embutido_desconta_credito_do_custo():
    """
    Calibração 2 do motor (ver README): sem esse desconto, credita-se
    IBS/CBS em cima do valor cheio do custo — inclusive a parte que já é
    ICMS/PIS/COFINS do fornecedor embutido no preço, superestimando o
    crédito. 400.000 * (1 - 20%) * 27,91% = 89.312,00
    """
    e = empresa_real(pct_imposto_embutido_custos=D("0.20"))
    r = calcular(e, 2033, IBS, CBS, P)
    assert r["futuro"]["creditos_rs"] == "89312.00"


def test_sem_pct_imposto_embutido_credito_e_o_de_sempre():
    """Não informado (None) preserva o comportamento anterior a este parâmetro."""
    r = calcular(empresa_real(), 2033, IBS, CBS, P)
    assert r["futuro"]["creditos_rs"] == "111640.00"


def test_simples_hibrido_tambem_desconta_imposto_embutido():
    """
    Mesmo desconto de futuro.py, aplicado no crédito do híbrido do Simples.
    2.100.000 * (1 - 20%) * 27,91% = 468.888,00
    """
    r = calcular(empresa_simples(pct_imposto_embutido_custos=D("0.20")), 2033, IBS, CBS, P)
    assert r["simples"]["hibrido"]["creditos_rs"] == "468888.00"


def test_folha_nao_gera_credito():
    e = empresa_real(custos=[CustoEntrada("folha", D("500000.00"), D("0"), False)])
    r = calcular(e, 2033, IBS, CBS, P)
    assert r["futuro"]["creditos_rs"] == "0.00"


# --------------------------------------------------------------------------
# Item a item vs. agregado
# --------------------------------------------------------------------------

def test_modo_agregado_quando_nao_ha_itens():
    r = calcular(empresa_real(), 2026, IBS, CBS, P)
    assert r["meta"]["modo_calculo"] == "agregado"
    assert any("agregado" in x for x in r["limitacoes"])


def test_item_a_item_soma_o_mesmo_que_agregado_com_aliquotas_iguais():
    """Dois itens de 50% com as mesmas alíquotas devem dar o mesmo total."""
    itens = [
        ItemEntrada("A", D("0.5"), aliq_icms=D("0.17"), aliq_pis=D("0.0165"), aliq_cofins=D("0.076")),
        ItemEntrada("B", D("0.5"), aliq_icms=D("0.17"), aliq_pis=D("0.0165"), aliq_cofins=D("0.076")),
    ]
    r_ag = calcular(empresa_real(), 2026, IBS, CBS, P)
    r_it = calcular(empresa_real(itens=itens), 2026, IBS, CBS, P)
    assert r_it["meta"]["modo_calculo"] == "item_a_item"
    assert r_it["atual"]["total_debitos_rs"] == r_ag["atual"]["total_debitos_rs"]


def test_regime_diferenciado_reduz_carga_do_item():
    normal = [ItemEntrada("N", D("1"), aliq_icms=D("0.17"))]
    reduzido = [ItemEntrada("R", D("1"), aliq_icms=D("0.17"), regime_diferenciado="reducao_60")]
    r_n = calcular(empresa_real(itens=normal), 2033, IBS, CBS, P)
    r_r = calcular(empresa_real(itens=reduzido), 2033, IBS, CBS, P)
    assert D(r_r["futuro"]["total_debitos_rs"]) < D(r_n["futuro"]["total_debitos_rs"])


# --------------------------------------------------------------------------
# Simples Nacional
# --------------------------------------------------------------------------

def test_aliquota_efetiva_anexo_i_faixa_3_confere_na_mao():
    """(500.000 * 9,5% - 13.860) / 500.000 = 6,728%"""
    efetiva, faixa = aliquota_efetiva(D("500000"), P["simples"]["anexos"]["1"])
    assert faixa["faixa"] == 3
    assert efetiva == D("0.067280")


def test_primeira_faixa_efetiva_igual_nominal():
    efetiva, _ = aliquota_efetiva(D("100000"), P["simples"]["anexos"]["1"])
    assert efetiva == D("0.040000")


def test_aliquota_efetiva_anexo_ii_faixa_3_confere_na_mao():
    """Indústria: (500.000 * 10,00% - 13.860) / 500.000 = 7,228%"""
    efetiva, faixa = aliquota_efetiva(D("500000"), P["simples"]["anexos"]["2"])
    assert faixa["faixa"] == 3
    assert efetiva == D("0.072280")


def test_aliquota_efetiva_anexo_iv_faixa_3_confere_na_mao():
    """Serviços sem CPP: (500.000 * 10,20% - 12.420) / 500.000 = 7,716%"""
    efetiva, faixa = aliquota_efetiva(D("500000"), P["simples"]["anexos"]["4"])
    assert faixa["faixa"] == 3
    assert efetiva == D("0.077160")


def test_aliquota_efetiva_anexo_v_faixa_3_confere_na_mao():
    """Fator R: (500.000 * 19,50% - 9.900) / 500.000 = 17,520%"""
    efetiva, faixa = aliquota_efetiva(D("500000"), P["simples"]["anexos"]["5"])
    assert faixa["faixa"] == 3
    assert efetiva == D("0.175200")


def test_acima_do_limite_do_simples_falha():
    with pytest.raises(ForaDoSimples, match="acima do limite"):
        aliquota_efetiva(D("5000000"), P["simples"]["anexos"]["1"])


def test_anexo_nao_parametrizado_falha():
    with pytest.raises(ForaDoSimples, match="não parametrizado"):
        aliquota_efetiva(D("300000"), [])


def empresa_simples(**kw):
    base = dict(
        razao_social="Distribuidora",
        regime="simples",
        simples_anexo=1,
        faturamento_anual=D("3200000.00"),
        rbt12=D("3200000.00"),
        custos=[CustoEntrada("mercadorias", D("2100000.00"), D("0"), True)],
    )
    base.update(kw)
    return EntradaSimulacao(**base)


def test_simples_roda_as_duas_opcoes_por_padrao():
    r = calcular(empresa_simples(), 2033, IBS, CBS, P)
    assert set(r["simples"]) == {"unico", "hibrido"}


def test_hibrido_transfere_mais_credito_ao_cliente():
    """É esta diferença que decide a escolha do regime."""
    r = calcular(empresa_simples(), 2033, IBS, CBS, P)
    unico = D(r["simples"]["unico"]["credito_transferido_ao_cliente_rs"])
    hibrido = D(r["simples"]["hibrido"]["credito_transferido_ao_cliente_rs"])
    assert hibrido > unico


def test_unico_nao_gera_credito_proprio():
    r = calcular(empresa_simples(), 2033, IBS, CBS, P)
    assert r["simples"]["unico"]["creditos_rs"] == "0.00"
    assert D(r["simples"]["hibrido"]["creditos_rs"]) > 0


def test_opcao_explicita_roda_apenas_ela():
    r = calcular(empresa_simples(), 2033, IBS, CBS, P, opcao_simples="hibrido")
    assert set(r["simples"]) == {"hibrido"}
    assert r["futuro"]["opcao_simples"] == "hibrido"


def test_hibrido_usa_receita_liquida_nao_a_bruta():
    """
    Regressão: a apuração regular do híbrido calculava IBS/CBS por fora
    sobre a receita bruta — mesmo erro que o resto do motor já evita para
    os demais regimes (ver test_ignorar_por_fora_superestimaria_a_carga).
    Inflava a carga do híbrido e distorcia a comparação com o único, que
    é o resultado principal desta parte do motor.
    """
    r = calcular(empresa_simples(), 2033, IBS, CBS, P)
    hibrido = r["simples"]["hibrido"]
    bruta = D(hibrido["receita_bruta_rs"])
    correto = D(hibrido["ibs_cbs_por_fora_rs"])
    ingenuo = bruta * (IBS + CBS)
    assert correto < ingenuo


# --------------------------------------------------------------------------
# Comparação, referências e limitações
# --------------------------------------------------------------------------

def test_direcao_coerente_com_a_diferenca():
    r = calcular(empresa_real(), 2033, IBS, CBS, P)
    dif = D(r["comparacao"]["diferenca_rs"])
    direcao = r["comparacao"]["direcao"]
    assert (dif > 0 and direcao == "aumento") or (dif < 0 and direcao == "reducao") or dif == 0


def test_margem_se_desloca_na_direcao_oposta_a_carga():
    e = empresa_real(margem_liquida=D("0.11"))
    r = calcular(e, 2033, IBS, CBS, P)
    dif = D(r["comparacao"]["diferenca_rs"])
    var = D(r["comparacao"]["variacao_margem_pp"])
    assert (dif > 0) == (var < 0) or dif == 0


def test_referencias_cobrem_os_numeros_principais():
    r = calcular(empresa_real(), 2033, IBS, CBS, P)
    ref = r["referencias"]
    for chave in (
        "atual.carga_liquida_rs", "futuro.carga_liquida_rs",
        "comparacao.diferenca_rs", "comparacao.direcao",
    ):
        assert chave in ref


def test_todo_numero_do_resultado_esta_nas_referencias_principais():
    """A IA só pode citar número que exista aqui."""
    r = calcular(empresa_real(), 2033, IBS, CBS, P)
    assert r["referencias"]["atual.carga_liquida_rs"] == r["atual"]["carga_liquida_rs"]
    assert r["referencias"]["comparacao.diferenca_rs"] == r["comparacao"]["diferenca_rs"]


def test_limitacoes_sempre_presentes():
    r = calcular(empresa_real(), 2033, IBS, CBS, P)
    assert len(r["limitacoes"]) >= 4
    assert any("Senado" in x for x in r["limitacoes"])


def test_resultado_e_serializavel_em_json():
    import json
    r = calcular(empresa_simples(), 2030, IBS, CBS, P)
    assert json.loads(json.dumps(r))["meta"]["ano_base"] == 2030


def test_reprodutibilidade():
    a = calcular(empresa_real(), 2029, IBS, CBS, P)
    b = calcular(empresa_real(), 2029, IBS, CBS, P)
    assert a == b


# --------------------------------------------------------------------------
# Regressões encontradas rodando com dados reais
# --------------------------------------------------------------------------

def test_baseline_do_simples_e_o_das_nao_zero():
    """Regressão: o baseline usava alíquotas nulas e a carga de hoje dava zero."""
    r = calcular(empresa_simples(), 2033, IBS, CBS, P)
    assert D(r["atual"]["carga_liquida_rs"]) > 0
    assert r["atual"]["tributos_rs"]["das"] == r["atual"]["carga_liquida_rs"]


def test_receita_liquida_desconta_debito_e_nao_carga_liquida():
    """
    Regressão: descontar a carga líquida encolhia a base do IBS/CBS e
    inflava artificialmente a redução para quem tem muito crédito.
    """
    r = calcular(empresa_real(), 2033, IBS, CBS, P)["atual"]
    bruta = D(r["receita_bruta_rs"])
    assert D(r["receita_liquida_rs"]) == bruta - D(r["total_debitos_rs"])
    assert D(r["receita_liquida_rs"]) != bruta - D(r["carga_liquida_rs"])
