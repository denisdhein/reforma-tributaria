"""
Monta as mensagens enviadas ao modelo — tanto a análise de uma tacada
(`construir_mensagens_analise`) quanto o chat de perguntas e respostas
sobre o resultado (`construir_mensagens_chat`).

A IA recebe fatos já calculados, nunca recalcula nada, e só pode citar
número pela chave em `resultado["referencias"]` — nunca dígito solto no
texto. É essa regra, imposta aqui e conferida em app/ia/verificacao.py, que
torna invenção numérica estruturalmente impossível (mesmo princípio da
docstring de app/motor/calculadora.py, agora do lado da IA). O chat usa a
mesma regra: é o motivo de reusar `verificacao.py` e `renderizador.py`
inalterados para as respostas de chat.
"""

from __future__ import annotations

import json

INSTRUCAO_SISTEMA = """
Você explica o resultado de uma simulação da Reforma Tributária do Consumo
brasileira (EC 132/2023, LC 214/2025, LC 227/2026) para um gestor ou
contador. Você NÃO calcula nada e não tem acesso a nenhum número além dos
que estão em "referencias", no contexto que você recebe.

Regras obrigatórias, sem exceção:
1. Para citar qualquer valor monetário, alíquota ou percentual, use
   exatamente o formato {{chave}} — por exemplo {{atual.carga_liquida_rs}}
   — usando só chaves que existem em "referencias". NUNCA escreva um
   número, R$ ou percentual diretamente no texto, nem por extenso.
2. Nunca afirme uma alíquota, prazo ou regra que não esteja no contexto.
3. Nunca dê certeza jurídica — é a estimativa de um protótipo acadêmico.
4. Termine sempre recomendando revisão por profissional contábil antes de
   qualquer decisão.
5. Português do Brasil, direto, sem jargão técnico, no máximo 160 palavras,
   sem markdown, sem listas — texto corrido em 2 a 3 parágrafos curtos.
6. Se houver bloco "simples" no contexto, comente a diferença entre único e
   híbrido usando as chaves simples.unico.* e simples.hibrido.*.
""".strip()

INSTRUCAO_SISTEMA_CHAT = """
Você responde perguntas de um gestor ou contador sobre o resultado de uma
simulação da Reforma Tributária do Consumo (EC 132/2023, LC 214/2025, LC
227/2026) que ele está vendo na tela agora. Você NÃO calcula nada e não tem
acesso a nenhum número além dos que estão em "referencias", no contexto
enviado na primeira mensagem.

Regras obrigatórias, sem exceção:
1. Para citar qualquer valor monetário, alíquota ou percentual, use
   exatamente o formato {{chave}} — usando só chaves que existem em
   "referencias". NUNCA escreva um número, R$ ou percentual diretamente,
   nem por extenso.
2. Se a pergunta pedir algo que não está no contexto (uma alíquota nova,
   uma regra não informada, uma opinião jurídica, um cálculo diferente do
   que já está pronto), diga claramente que essa informação não está
   disponível nesta simulação. Não invente, não estime de cabeça.
3. Nunca dê certeza jurídica — é a estimativa de um protótipo acadêmico.
4. Se a resposta tocar em decisão (comprar, mudar de regime, alterar
   preço), recomende revisão por profissional contábil.
5. Português do Brasil, direto, sem markdown — resposta curta, no máximo
   120 palavras, focada só no que foi perguntado.
""".strip()


def montar_contexto(resultado: dict) -> dict:
    """Fatos da simulação que a IA pode usar — mesmo formato tanto para a
    análise de uma tacada quanto para o chat, e é o que a tela reenvia a
    cada pergunta (ver app/web/rotas.py e o script embutido no template)."""
    m = resultado["meta"]
    return {
        "empresa": m["razao_social"],
        "regime": m["regime"],
        "ano_simulado": m["ano_base"],
        "direcao_da_variacao": resultado["comparacao"]["direcao"],
        "tem_opcao_simples": bool(resultado.get("simples")),
        "referencias": resultado["referencias"],
    }


def construir_mensagens_analise(resultado: dict) -> list[dict]:
    contexto = montar_contexto(resultado)
    conteudo = (
        "Contexto (JSON) — as únicas chaves citáveis estão dentro de "
        '"referencias":\n' + json.dumps(contexto, ensure_ascii=False, indent=2)
        + "\n\nEscreva a explicação agora, seguindo todas as regras do sistema."
    )
    return [
        {"role": "system", "content": INSTRUCAO_SISTEMA},
        {"role": "user", "content": conteudo},
    ]


INSTRUCAO_SISTEMA_CADASTRO = """
Você ajuda um gestor ou contador a preencher o cadastro de uma empresa num
sistema de simulação da Reforma Tributária do Consumo (EC 132/2023, LC
214/2025, LC 227/2026). Você explica o que cada campo do formulário
significa e por que ele importa para o cálculo — não preenche nada
sozinho, não decide por ninguém, não vê o que a pessoa já digitou.

Regras obrigatórias, sem exceção:
1. NUNCA cite uma alíquota, percentual ou valor numérico específico — nem
   como exemplo, nem de memória. Se perguntarem uma alíquota concreta
   (do ICMS, do Simples, do IBS/CBS etc.), diga que isso está nos
   parâmetros do sistema (tela de cenários) ou deve ser confirmado com um
   contador — você não tem acesso a dado tributário atualizado, e citar
   de cabeça é o tipo de erro que este sistema existe para evitar.
2. Nunca dê certeza jurídica sobre enquadramento, regime ou obrigação.
3. Se a dúvida for sobre uma decisão de negócio, recomende revisão por
   profissional contábil.
4. Português do Brasil, direto, no máximo 100 palavras, sem markdown.
""".strip()


def construir_mensagens_ajuda_cadastro(historico: list[dict], pergunta: str) -> list[dict]:
    """
    Sem `referencias` para ancorar — ainda não existe simulação calculada
    neste momento, só um formulário sendo preenchido. Por isso a garantia
    aqui é mais fraca (instrução no prompt, não verificação estrutural
    depois): ver app/ia/servico.py:responder_ajuda_cadastro e a ressalva
    no README.
    """
    mensagens = [{"role": "system", "content": INSTRUCAO_SISTEMA_CADASTRO}]
    for turno in historico:
        mensagens.append({"role": "user", "content": turno["pergunta"]})
        mensagens.append({"role": "assistant", "content": turno["resposta"]})
    mensagens.append({"role": "user", "content": pergunta})
    return mensagens


def construir_mensagens_chat(contexto: dict, historico: list[dict], pergunta: str) -> list[dict]:
    conteudo_contexto = (
        "Contexto (JSON) desta simulação — as únicas chaves citáveis estão "
        'dentro de "referencias":\n' + json.dumps(contexto, ensure_ascii=False, indent=2)
    )
    mensagens = [
        {"role": "system", "content": INSTRUCAO_SISTEMA_CHAT},
        {"role": "user", "content": conteudo_contexto},
        {"role": "assistant", "content": "Entendido. Pode perguntar sobre essa simulação."},
    ]
    for turno in historico:
        mensagens.append({"role": "user", "content": turno["pergunta"]})
        mensagens.append({"role": "assistant", "content": turno["resposta"]})
    mensagens.append({"role": "user", "content": pergunta})
    return mensagens
