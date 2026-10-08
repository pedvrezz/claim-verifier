# Avaliação do comportamento

Usar os casos de `scenarios.json` para comparar o mesmo agente com e sem a
skill. Manter modelo, ferramentas, dados, orçamento e condições iguais.
Entregar ao agente somente `prompt` e `evidence`; manter `criteria` e
`critical_failures` com o avaliador. Não usar os exemplos de antes/depois
como respostas de referência durante a execução.

Os casos já fornecem evidência controlada e avaliam a adequação da resposta
a essa evidência. Não medem descoberta de fontes na web nem eficácia geral.
Para avaliar uso de ferramentas, acrescentar tarefas com arquivos, logs ou
servidores descartáveis e registrar chamadas e saídas observadas.

Pontuar cada critério como atendido ou não atendido. Registrar também falhas
críticas, afirmações relevantes sustentadas, afirmações sem suporte,
afirmações contrariadas pela evidência, omissões e respostas que abandonam
a tarefa sem necessidade. Separar afirmação falsa de afirmação sem suporte:
a falta de evidência, por si só, não demonstra falsidade.

Calcular a taxa de afirmações sem suporte somente se houver afirmações
avaliáveis. Se o denominador for zero, registrar `N/A`. Informar tamanho da
amostra, cobertura, custo e método de avaliação. Não melhorar a métrica
eliminando o conteúdo útil da resposta. Se usar um juiz automático, revisar
uma amostra manualmente e identificar seus limites.

Os testes de `tests/` verificam o software de checagem HTTP. A execução deles
não mede redução de erros factuais de um modelo. Este pacote inclui um
protocolo de avaliação; não inclui um benchmark comparativo já executado.
