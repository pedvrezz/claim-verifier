# claim-verifier

Uma skill para adequar a força das afirmações à evidência disponível. Antes
de entregar uma resposta, o agente distingue o que verificou, o que inferiu
e o que depende apenas de memória ou suposição.

O procedimento exige checagem dos pontos decisivos e uma ressalva específica
quando falta confirmação. Não promete eliminar erros, fazer pesquisa em toda
frase ou provar segurança de código com um único teste.

## Conteúdo

| Arquivo ou pasta | Uso |
| --- | --- |
| `SKILL.md` | Procedimento, critérios e descrição para descoberta da skill. |
| `checklists/` | Conferência de código, fatos, links e APIs. |
| `scripts/check_links.py` | Checagem de respostas HTTP, com saída textual ou JSON. |
| `examples/before-after.md` | Exemplos ilustrativos de redação calibrada. |
| `evals/` | Cenários e rubrica para avaliação manual do comportamento. |
| `tests/` | Testes locais do validador de URLs. |
| `agents/openai.yaml` | Metadados de apresentação para agentes compatíveis. |

## Uso no Hermes

A documentação oficial indica `~/.hermes/skills/` como diretório principal
e permite configurar diretórios adicionais. Para uso local, colocar a pasta
completa em `~/.hermes/skills/claim-verifier/`, incluindo os checklists e o
script, e conferir sua presença com `hermes skills list` em uma nova sessão.
Respeitar o diretório do perfil ativo quando usar perfis.

A descoberta disponibiliza a skill ao agente; não garante que ele a carregue
em toda resposta. A descrição foi escrita para favorecer uso em tarefas com
afirmações verificáveis. Para testar uma invocação explícita, usar
`/claim-verifier` seguido da tarefa. Para uma política recorrente, orientar
o agente a carregar essa skill antes de concluir tarefas factuais ou técnicas.
Essa orientação continua dependente do agente e das ferramentas disponíveis.

Fontes oficiais consultadas em 8 de outubro de 2026:
[sistema de skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/)
e [criação de skills](https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills/).
As instruções acima não significam que uma instalação no seu Hermes já ocorreu.

## Validador de links

Usar Python 3.10 ou superior. O script não depende de pacotes externos.
Executar os comandos na pasta da skill:

```bash
python3 scripts/check_links.py --file resposta.md --json
python3 -m unittest discover -s tests -v
```

O validador confere respostas HTTP. Ler a página continua necessário para
verificar o conteúdo. Consultar
[opções e estados](checklists/links-and-apis.md) antes de interpretar a saída.

## Avaliação e contribuições

Consultar a [rubrica](evals/README.md). Os cenários permitem comparar agentes
com e sem a skill; nenhuma redução de erros é alegada sem uma avaliação real.
Os exemplos publicados são ilustrativos e estão identificados como tal.

Para contribuir, propor um checklist de domínio com critérios de evidência,
limites e casos de teste. Não incluir dados pessoais, credenciais, resultados
inventados ou instruções que executem ações reais apenas para validá-las.
