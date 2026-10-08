# Código

1. Ler o arquivo, o diff e as instruções do projeto. Identificar o comportamento
   alegado e o ambiente em que precisa funcionar. Conferir dependências no
   manifesto e no lockfile; consultar documentação oficial se a API for incerta.
2. Separar o que é possível verificar: sintaxe, imports, build, testes,
   integração e execução no ambiente de destino. Informar a versão realmente
   consultada ou executada; não deduzir a versão instalada pelo nome do pacote.
3. Executar o menor teste que exercite o comportamento alterado. Usar entradas
   e resultados esperados independentes da implementação. Incluir casos de
   erro que possam invalidar a conclusão. Usar recursos descartáveis para
   rede, banco e sistema de arquivos.
4. Conferir a saída, o código de retorno e o contexto de execução. Uma suíte
   vazia, testes ignorados ou mocks não equivalem a integração real.
5. Revisar o alcance da frase final. "Passou nos testes X" é sustentado pela
   execução de X. "Funciona em produção" exige evidência desse ambiente.

| Evidência observada | Formulação sustentada |
| --- | --- |
| Leitura do código | "Revisei a implementação; não executei." |
| Compilação sem erro | "Compilou neste ambiente." |
| Importação do módulo | "O módulo foi importado nesta versão do Python." |
| Testes locais específicos | "Os cenários executados passaram." |
| Integração com servidor descartável | "A integração foi exercitada nesse servidor de teste." |
| Ferramenta indisponível | "A alteração está pronta; não consegui executar X aqui." |

Não afirmar compatibilidade com sistemas ou versões que não foram testados
ou cobertos por documentação adequada. Não ampliar os testes repetidamente
sem um novo risco ou falha que justifique o trabalho.
