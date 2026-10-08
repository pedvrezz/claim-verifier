# Links e APIs

1. Obter a URL da fonte consultada, do arquivo ou da documentação oficial.
   Não construir um caminho plausível e apresentá-lo como link confirmado.
2. Conferir esquema, domínio, caminho, versão e finalidade. Evitar chamadas
   que possam consumir links de uso único, confirmar operações ou expor
   credenciais. Validar APIs autenticadas pelo SDK, schema ou documentação,
   sem divulgar tokens.
3. Para URLs públicas de leitura, conferir a resposta HTTP e os redirecionamentos.
   Ler também o conteúdo para confirmar título, assunto e suporte à afirmação.
   Detectar páginas de login, erro com HTTP 200 e redirecionamento à página inicial.
4. Para APIs, conferir método, endpoint, parâmetros, tipos, autenticação e
   formato de resposta. Um GET não comprova que um POST aceita o mesmo recurso;
   documentação comprova o contrato descrito, não o comportamento observado.
5. Usar sandbox ou mock para chamadas com efeito. Identificar que o resultado
   veio de simulação. Não fazer escrita em produção como verificação.

## Validador incluído

Executar a partir da pasta da skill:

```bash
python3 scripts/check_links.py --file resposta.md
python3 scripts/check_links.py --file resposta.md --json
python3 scripts/check_links.py --stdin --json < resposta.md
```

Também aceitar URLs como argumentos. Usar `--help` para consultar as opções.
O script usa Python 3.10 ou superior, sem pacotes externos. Fazer HEAD e, se o
servidor responder 403, 405 ou 501, tentar GET sem ler o corpo. Verificar cada
destino de redirecionamento, limitar saltos e manter a validação TLS.

| Estado do script | Interpretação |
| --- | --- |
| reachable | Recebeu HTTP 2xx; o conteúdo ainda precisa ser lido. |
| missing | Recebeu HTTP 404 ou 410 nessa requisição; não prova indisponibilidade universal. |
| restricted | Recebeu 401, 403, 407 ou 429; acesso ou limite impediu a confirmação. |
| unknown | Erro de rede, TLS, timeout, 5xx ou outra resposta inconclusiva. |
| blocked | A política do script impediu a chamada, como destino privado ou credencial na URL. |
| invalid | URL malformada ou esquema não suportado. |

Retornar código 0 somente quando todas as URLs responderem com HTTP 2xx;
retornar 1 se houver outro estado; retornar 2 para erro de argumentos, leitura
ou ausência de URLs. Deduplicar URLs e retirar fragmentos da requisição.

Ocultar valores de query e credenciais na saída. Recusar URLs com credenciais
embutidas ou parâmetros comuns de autenticação. Não enviar cookies,
Authorization ou usar proxies de ambiente. O filtro não identifica todo
segredo possível: conferir os links antes da execução.

Bloquear destinos não públicos por padrão, inclusive após redirecionamento.
Usar `--allow-private` somente para diagnóstico autorizado de um endereço
conhecido ou para os testes locais. O timeout limita operações de socket;
a resolução DNS do sistema pode levar mais tempo. Não seguir links da página
nem interpretar a saída como validação semântica.
