"""
Verificação determinística da resposta do modelo, antes de qualquer usuário
ver o texto — o checklist descrito no TCC I (seção 4.4): aderência
numérica, coerência de direção, presença do aviso de revisão profissional.

Aderência numérica é estrutural e confiável: se a chave citada não existe
em `referencias`, é reprovação automática — vale sempre, relatório ou
chat. Coerência de direção e ausência de afirmação jurídica absoluta são
heurísticas por palavra-chave — suficientes para pegar os erros
grosseiros, não substituem leitura humana da resposta.

`modo_relatorio` desliga duas exigências que fazem sentido na análise de
uma tacada mas rejeitariam respostas de chat legítimas: toda pergunta
teria que citar uma referência mesmo sendo conceitual ("o que é IBS?"), e
toda resposta teria que recomendar revisão contábil mesmo sendo só
explicativa. O prompt do chat (app/ia/prompt.py) já pede a recomendação
apenas quando a resposta toca em decisão — cobrar sempre aqui rejeitaria
resposta correta.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

PADRAO_REFERENCIA = re.compile(r"\{\{([a-zA-Z0-9_.]+)\}\}")
# Número com casa decimal (vírgula OU ponto — achado real: o modelo pode
# citar internamente com ponto tipo "0.201800"), R$, ou percentual, fora
# do formato {{chave}}.
PADRAO_NUMERO_SOLTO = re.compile(r"R\$\s?\d|\d,\d|\d\.\d|\d+%")

PALAVRAS_REVISAO = ("profissional", "contáb", "contador")
PALAVRAS_CERTEZA_JURIDICA = (
    "com certeza", "certamente", "garantido", "garante", "sempre será", "é obrigatório",
)


@dataclass
class Verificacao:
    aprovada: bool
    motivos: list[str] = field(default_factory=list)


def verificar(texto: str, referencias: dict, direcao: str, modo_relatorio: bool = True) -> Verificacao:
    motivos: list[str] = []
    texto_lower = texto.lower()

    chaves_citadas = PADRAO_REFERENCIA.findall(texto)
    desconhecidas = [c for c in chaves_citadas if c not in referencias]
    if desconhecidas:
        motivos.append(f"referência(s) inexistente(s) em referencias: {', '.join(desconhecidas)}")

    if modo_relatorio and not chaves_citadas:
        motivos.append("nenhuma referência numérica citada no formato {{chave}}")

    # Remove as referências válidas antes de procurar número solto — senão
    # um valor como "17,70" dentro de {{cenario.aliquota_ibs}} dispararia
    # falso positivo.
    sem_referencias = PADRAO_REFERENCIA.sub("", texto)
    if PADRAO_NUMERO_SOLTO.search(sem_referencias):
        motivos.append("número citado fora do formato {{chave}}")

    if modo_relatorio and not any(p in texto_lower for p in PALAVRAS_REVISAO):
        motivos.append("não recomenda revisão por profissional contábil")

    if any(p in texto_lower for p in PALAVRAS_CERTEZA_JURIDICA):
        motivos.append("linguagem de certeza jurídica absoluta")

    if direcao == "aumento" and "redução" in texto_lower and "aumento" not in texto_lower:
        motivos.append("menciona redução mas o resultado calculado é de aumento")
    if direcao == "reducao" and "aumento" in texto_lower and "redução" not in texto_lower:
        motivos.append("menciona aumento mas o resultado calculado é de redução")

    return Verificacao(aprovada=not motivos, motivos=motivos)
