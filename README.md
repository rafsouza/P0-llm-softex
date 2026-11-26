# API de Extração de Eventos para Agendas Virtuais

Microsserviço em Python/FastAPI que recebe textos em linguagem natural via API REST, extrai dados de eventos utilizando um LLM local (Qwen3.5,) retorna o resultado em formato textual no corpo da resposta e possui opção de baixar a reposta em arquivos .csv ou .json.
Esta app foi projetada para ser executada em um container Docker e receber as entradas como requisições HTTP.

**Problema resolvido:** Obtenção de informações de um texto para serem inseridas diretamente em uma agenda virtual.

**Público:** Pessoas que trabalham com grandes volumes de agendamentos, como secretários, promotores de eventos, palestrantes, e demais profissionais que trabalham com seviços agendados. 

**Justificativa de uso da LLM:** Para extrair as informações necessárias para serem inseridas em uma agenda virtual, estas informações precisam ser interpretadas em linguagem natural e estarem dentro de um contexto, características estas que são propriciadas de uma maneira otimizada por LLM.

---

## 1. Funcionamento da Solução
A aplicação opera como um microsserviço contínuo empacotado em Docker e estruturado em **seis responsabilidades isoladas**, evitando acoplamento entre validação de entrada, configuração, integração HTTP, parsing e persistência:

| Camada / Responsabilidade | Arquivo | O que faz |
| :--- | :--- | :--- |
| **1. Captura da entrada (Gateway)** | `src/gateway.py` | Expõe as rotas HTTP via `APIRouter`, impede entradas vazias/curtas com Pydantic, orquestra o fluxo e traduz erros de domínio para códigos HTTP |
| **2. Carregamento da configuração** | `src/config.py` | Lê variáveis de ambiente (`.env`), valida esquema `http`/`https` da URL, credencial obrigatória (`LLM_API_KEY`), timeout e pasta de saída |
| **3. Preparação da solicitação** | `src/request_builder.py` | Revalida texto não vazio, sanitiza o trecho gravado em log (truncamento), monta o prompt estruturado, payload JSON e cabeçalho `Authorization` |
| **4. Chamada ao modelo** | `src/client.py` | Executa chamadas HTTP isoladas com `requests`, suporta bypass SSL (`verify=False`) para certificados autogerados e classifica falhas de rede/HTTP |
| **5. Tratamento da resposta** | `src/response_parser.py` | Rejeita respostas vazias, JSON corrompido ou estruturas inválidas e normaliza campos e níveis de prioridade (`alta`, `média`, `baixa`) |
| **6. Apresentação do resultado** | `src/presenter.py` | Grava arquivos com *timestamp* em `data/`, retorna apenas os dados JSON por padrão (com nome do arquivo no cabeçalho `X-File-Saved`) ou entrega o arquivo para download (`FileResponse`) |
| **Exceções e Bootstrap** | `src/exceptions.py`, `src/app.py` | Define exceções tipadas de domínio, inicializa logs e registra o `gateway` no FastAPI usando `lifespan` |

### Fluxo de uma Requisição

```text
POST /events
  └─> src/gateway.py         (valida entrada não vazia e opções output_format / download)
        └─> src/config.py          (carrega e valida URL, modelo, credencial e timeout)
              └─> src/request_builder.py (sanitiza log e monta payload + Bearer token)
                    └─> src/client.py          (chama /api/generate no Ollama interno)
                          └─> src/response_parser.py (valida JSON e normaliza prioridade)
                                └─> src/presenter.py       (salva em data/ e retorna JSON ou download)
```

### Estrutura do Projeto

event-extractor/
├── .env                    
├── .env.example            
├── .gitignore              
├── Dockerfile              
├── README.md               
├── requirements.txt        
├── data/                   # Pasta padrão para saída
├── logs/                   # Pasta de Registros 
├── src/
│   ├── __init__.py
│   ├── app.py              
│   ├── gateway.py          
│   ├── config.py           
│   ├── exceptions.py       
│   ├── request_builder.py  
│   ├── client.py           
│   ├── response_parser.py 
│   └── presenter.py        
└── tests/
    ├── __init__.py
    ├── test_client.py      
    └── test_gateway.py     


### Tratamento de Situações Previsíveis

| Situação | Exceção Interna | Status HTTP |
| :--- | :--- | :---: |
| Entrada vazia, nula ou apenas espaços | `ValidationError` / `EmptyInputError` | `422` / `400` |
| Configuração ausente ou inválida (`LLM_URL`, `LLM_MODEL`, `LLM_TIMEOUT`) | `ConfigurationError` | `500` |
| Credencial ausente (`LLM_API_KEY`) | `MissingCredentialError` | `500` |
| Credencial rejeitada pelo servidor LLM | `InvalidCredentialError` | `401` |
| Modelo indisponível (`404`) ou servidor fora do ar (`502`/`503`/`504`) | `ModelUnavailableError` | `503` |
| Falha de comunicação / DNS / rede | `CommunicationError` | `503` |
| Timeout aguardando o modelo | `LLMTimeoutError` | `504` |
| Resposta vazia, JSON inválido ou estrutura inesperada | `InvalidResponseError` | `502` |

---

## 2. Limites do Projeto

* **Datas relativas:** Expressões como *"amanhã às 14h"* ou *"próxima sexta"* são mantidas conforme interpretadas pelo LLM, sem conversão automática para formato ISO-8601 com fuso horário..
* **Processamento síncrono:** Cada chamada aguarda a conclusão da inferência do LLM dentro do limite definido em `LLM_TIMEOUT`; não há fila assíncrona nem banco de dados relacional.
* **Certificado SSL autogerado:** Por padrão, `LLM_VERIFY_SSL=false` desabilita a verificação SSL para compatibilidade com o servidor interno. Esse modo não deve ser utilizado em redes públicas sem certificado válido.
* **Persistência em container:** Na plataforma de deploy, arquivos gravados em `data/` dentro do container são apagados ao parar a instância. Para retenção permanente sem alterar código, configure `OUTPUT_DIR=/persistent/data`.


---

## 3. Instalação

### Pré-requisitos

* **Python 3.10+** (imagem Docker utiliza Python 3.12 Alpine)
* **Git** e **VS Code**
* **Docker** (para geração da imagem e exportação `.tar`)

## Configuração Local (VS Code + `venv`)

### 1. Clonar e preparar o ambiente virtual


git clone [https://github.com/SEU_USUARIO/event-extractor.git](https://github.com/SEU_USUARIO/event-extractor.git)
cd event-extractor

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt


### 2. Configurar variáveis de ambiente

Copie o arquivo de exemplo e ajuste os valores conforme necessário:


cp .env.example .env


Conteúdo padrão do `.env`:

LLM_URL=https://seu-servidor-interno:9001
LLM_MODEL=nome-do-modelo-do-servidor
LLM_API_KEY=credencial-de-acesso
LLM_TIMEOUT=250
OUTPUT_DIR=data
LLM_VERIFY_SSL=false

> **Observação sobre `LLM_API_KEY`:** Caso o servidor interno não exija autenticação via Bearer token, ele ignora o cabeçalho `Authorization`; basta informar um valor local no `.env` (ex.: `teste-local-token`) para satisfazer a validação obrigatória de credencial.

### 3. Executar a API localmente

uvicorn src.app:app --host 0.0.0.0 --port 8080 --reload


A documentação interativa (Swagger UI) ficará disponível em: `http://localhost:8080/docs`.

---

## 4. Execução

### Execução Local (Desenvolvimento)

Com o ambiente virtual ativado e o `.env` preenchido:

source venv/bin/activate
uvicorn src.app:app --host 0.0.0.0 --port 8080 --reload


* **API:** `http://localhost:8080`
* **Documentação interativa (Swagger UI):** `http://localhost:8080/docs`

### Execução via Docker e Exportação `.tar`

docker pull python:3.12-alpine
docker build -t seunomedeusuario:latest .
docker save --output seunomedeusuario.tar seunomedeusuario:latest

Para validar o container localmente antes do upload:


docker run -d \
  --name event-extractor-local \
  -p 8080:8080 \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  event-extractor:v3.0.0

curl -X GET http://localhost:8080/health
docker rm -f event-extractor-local


### Deploy na Plataforma Web

Na interface web (**Enviar Containers**), informe:

* **Arquivo da imagem:** `seunomedeusuario.tar`

* **Portas internas:** `8080`

* **Variáveis de ambiente:**
LLM_URL=https://seu-servidor-interno:9001
LLM_MODEL=nome-do-modelo-do-servidor
LLM_API_KEY=credencial-de-acesso
LLM_TIMEOUT=250
OUTPUT_DIR=data
LLM_VERIFY_SSL=false

---

## 5. Exemplos de Entrada e Saída

Nos exemplos abaixo, substitua `localhost:8080` pelo endereço e porta pública atribuídos pela plataforma web quando estiver testando no servidor.

### 1. Verificar sTATUS de conexão com o LLM (`GET /health`)

curl -X GET http://localhost:8080/health

**Saída (`HTTP 200`):**

{
  "status": "ok",
  "output_dir": "data",
  "llm_model": "nome-do-modelo-do-servidor",
  "llm_connection": {
    "reachable": true,
    "authenticated": true,
    "model_available": true,
    "status_code": 200
  }
}


### 2. Extrair evento — modo padrão (`POST /events`, retorna apenas os dados JSON)

Por padrão, `output_format` é `"csv"` e `download` é `false`. O arquivo é salvo automaticamente em `data/` (nome informado no cabeçalho `X-File-Saved`) e o corpo devolve apenas os dados do evento:


curl -i -X POST http://localhost:8080/events \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Reunião urgente de revisão da arquitetura da API amanhã, 27/11 às 14h30, no Laboratório 3 para revisão da arquitetura da API."
  }'


**Saída (`HTTP 200`):**

HTTP/1.1 200 OK
content-type: application/json
x-file-saved: evento_20261126_164510_312.csv
{
  "titulo": "Revisão da Arquitetura da API",
  "data_hora": "27/11 às 14h30",
  "local": "Laboratório 3",
  "descricao": "revisão da arquitetura da API.",
  "prioridade": "alta"
}


**Conteúdo do arquivo salvo em `data/evento_20261126_164510_312.csv`:**
titulo,data_hora,local,descricao,prioridade
Revisão da Arquitetura da API,27/11 às 14h30,Laboratório 3,Reunião urgente de revisão da arquitetura da API.,alta


### 3. Extrair evento com download imediato opcional (`download: true`)

curl -X POST http://localhost:8080/events \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Café com a equipe na terça às 10h na copa.",
    "output_format": "json",
    "download": true
  }' \
  -O -J

O servidor salva `evento_YYYYMMDD_HHMMSS_mmm.json` em `data/` e inicia imediatamente o download do arquivo no cliente.


### 4. Listar e baixar arquivos salvos posteriormente

# Lista arquivos CSV e JSON disponíveis na pasta de saída
curl -X GET http://localhost:8080/files

# Baixa um arquivo específico pelo nome
curl -O http://localhost:8080/files/evento_20261126_164510_312.csv


### 5. Exemplos de saída em cenários de erro

**Entrada vazia (`HTTP 422`):**
curl -X POST http://localhost:8080/events \
  -H "Content-Type: application/json" \
  -d '{"text": "   "}'
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "text"],
      "msg": "Value error, O texto de entrada não pode estar vazio."
    }
  ]
}


**Credencial rejeitada pelo servidor LLM (`HTTP 401`):**
{
  "detail": "Credencial inválida ou sem permissão para acessar o servidor LLM."
}


**Timeout do LLM (`HTTP 504`):**
{
  "detail": "O servidor LLM demorou muito para responder."
}


---
## 6. Execução dos Testes

### Testes Simulados (Offline)

Para execução dos testes offline, o `venv` deve estar ativo. 

**Para executar todos os testes**
pytest tests/ -v


Saída esperada: **`22 passed`** (`16` em `tests/test_client.py` + `6` em `tests/test_gateway.py`).

**Para executar cada suíte separadamente:**

**Configuração, preparação de requisição, cliente HTTP mockado e parser**
pytest tests/test_client.py -v

**Rotas FastAPI (/events), validação de entrada vazia, retorno de dados e download opcional**
pytest tests/test_gateway.py -v

