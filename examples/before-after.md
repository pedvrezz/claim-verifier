# Antes e depois

Os exemplos abaixo são ilustrativos. Não são transcrições de incidentes reais
nem resultados de uma avaliação executada. Os registros de evidência são
premissas dos cenários, não alegações sobre ações realizadas neste arquivo.

## Código sem execução

Evidência do cenário: o agente alterou o código e fez revisão estática; o
ambiente não permite executar a aplicação.

Antes: "Corrigido. Agora funciona perfeitamente."

Depois: "Ajustei a validação de entrada. Revisei a alteração, mas não executei
a aplicação neste ambiente. O comportamento em execução ainda precisa ser
confirmado."

## Testes parciais

Evidência do cenário: 8 testes unitários passaram; o serviço externo foi mockado.

Antes: "A integração com o serviço está validada."

Depois: "Os 8 testes unitários passaram usando um mock do serviço. A conexão
com a API real ainda não foi testada."

## Versão lembrada

Evidência do cenário: o agente lembra um número de versão; não consultou
releases nem o ambiente instalado.

Antes: "A versão mais recente é 4.2.1."

Depois: "Não confirmei qual é a versão mais recente. Antes de recomendar uma
atualização, preciso consultar as releases oficiais e a versão instalada."

## Diagnóstico inferido

Evidência do cenário: um log mostra falha de resolução de nome; não houve
teste do resolvedor nem acesso ao servidor remoto.

Antes: "O servidor está fora do ar."

Depois: "O log mostra falha na resolução do nome. Isso sugere um problema
de DNS; ainda não confirma que o servidor esteja fora do ar."

## Link que responde

Evidência do cenário: a URL retornou HTTP 200; o corpo não foi lido.

Antes: "Confirmei o link oficial com as instruções corretas."

Depois: "A URL respondeu com HTTP 200. Ainda preciso conferir se a página é
a fonte oficial e se contém essas instruções."

## Acesso bloqueado

Evidência do cenário: a requisição retornou HTTP 403.

Antes: "Esse documento não existe."

Depois: "Não consegui acessar o documento: o servidor retornou HTTP 403.
Isso indica uma restrição nessa requisição e não confirma que o arquivo
tenha sido removido."

## Cálculo com premissas

Evidência do cenário: o usuário informou base de R$ 10.000 e alíquota de 8%;
o agente calculou R$ 800, sem verificar a alíquota aplicável.

Antes: "Você deve pagar R$ 800."

Depois: "Usando a base e a alíquota que você informou, o cálculo resulta em
R$ 800. Não confirmei se essa alíquota se aplica ao seu caso."

## Ação apenas preparada

Evidência do cenário: um arquivo foi criado localmente; não houve publicação.

Antes: "Publiquei a atualização."

Depois: "A atualização está pronta no arquivo. A publicação ainda não foi
executada."
