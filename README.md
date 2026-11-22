# Event Extractor API

Microsserviço em Python/FastAPI que recebe textos em linguagem natural via API REST, extrai dados de eventos utilizando um LLM local (Qwen3.5) e salva os resultados em arquivos estruturados (.csv ou .json).
Esta app foi projetada para ser executada em um container Docker e receber as entradas como requisições HTTP.


---

## Funcionalidades Principais

* **Extração estruturada via LLM interno:** Gera automaticamente `titulo`, `data_hora`, `local`, `descricao` e classifica a `prioridade` (`alta`, `média` ou `baixa`).
* **Saída flexível sem sobrescrita:** Grava arquivos com *timestamp* em milissegundos (`evento_YYYYMMDD_HHMMSS_mmm.csv` ou `.json`) no diretório configurado em `OUTPUT_DIR` (padrão: `data/`).
* **Segurança e privacidade:** Sanitização de logs (truncamento do texto de entrada em `logs/client.log`), segredos isolados em `.env` e imagem Docker baseada em `python:3.12-alpine` com pacotes atualizados.


---

## Estrutura do Projeto


event-extractor/
├── .env                  
├── .env.example          
├── .gitignore            
├── Dockerfile            
├── README.md             
├── requirements.txt      
├── data/                 # Pasta padrão para saída
├── logs/                 # Pasta de Registros           
├── src/
│   ├── __init__.py
│   ├── app.py            
│   └── client.py         
└── tests/
    ├── __init__.py
    └── test_client.py     


---

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
LLM_TIMEOUT=45
OUTPUT_DIR=data


### 3. Executar a API localmente

uvicorn src.app:app --host 0.0.0.0 --port 8080 --reload


A documentação interativa (Swagger UI) ficará disponível em: `http://localhost:8080/docs`.

---

## Endpoints da API

### `GET /health`
Verifica se a API está operacional, qual diretório de saída está ativo e se o servidor  interno responde ao endpoint `/api/tags`.


curl -X GET http://localhost:8080/health


### `POST /events`
Recebe o texto em linguagem natural, extrai o evento via LLM e grava o arquivo na pasta definida em `OUTPUT_DIR`.

**Parâmetros do corpo JSON:**

| Campo | Tipo | Obrigatório | Padrão | Descrição |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `string` | Sim | — | Texto contendo informações do evento (mínimo de 5 caracteres) |
| `output_format` | `"csv" \| "json"` | Não | `"csv"` | Formato do arquivo salvo na pasta de saída |

**Exemplo de requisição (CSV padrão):**


curl -X POST http://localhost:8080/events \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Reunião urgente de revisão da API amanhã, 21/11 às 14h30, no Laboratório 3."
  }'

**Exemplo de requisição (JSON):**


curl -X POST http://localhost:8080/events \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Café rápido com a equipe na terça às 10h na copa.",
    "output_format": "json"
  }'


**Exemplo de resposta (`HTTP 200`):**


{
  "status": "success",
  "message": "Evento extraído e salvo com sucesso.",
  "format": "csv",
  "file_saved": "data/evento_20261120_143015_412.csv",
  "data": {
    "titulo": "Revisão da API",
    "data_hora": "21/11 às 14h30",
    "local": "Laboratório 3",
    "descricao": "Reunião urgente de revisão da API.",
    "prioridade": "alta"
  }
}

**Códigos de erro tratados:**

| Status HTTP | Causa |
| :--- | :--- |
| `422` | Texto muito curto (menos de 5 caracteres) ou `output_format` inválido |
| `502` | Erro HTTP retornado pelo servidor interno ou resposta fora do formato JSON válido |
| `503` | Servidor LLM interno inacessível na rede |
| `504` | Tempo limite (`LLM_TIMEOUT`) excedido aguardando resposta do LLM |
| `500` | Falha de escrita em disco ou erro interno inesperado |

---

## Testes Unitários Offline

Os testes interceptam todas as chamadas HTTP com `requests-mock`, validando sucesso, bypass SSL, normalização de campos, sanitização de logs, timeout, erro de conexão, erro HTTP 500 e resposta JSON corrompida sem depender do servidor LLM:

pytest tests/test_client.py -v

---

## Build Docker e Exportação para `.tar`

### 1. Construir a imagem atualizada e exportar

docker pull python:3.12-alpine
docker build --no-cache -t event-extractor:latest .
docker save --output event-extractor.tar event-extractor:latest
ls -lh event-extractor.tar

> A imagem baseada em `python:3.12-alpine` fica muito abaixo do limite máximo de **1024 MB** exigido pela plataforma.

### 2. Testar o container localmente

docker run -d \
  --name event-extractor-local \
  -p 8080:8080 \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  event-extractor:latest

curl -X GET http://localhost:8080/health
docker rm -f event-extractor-local

### 3. Deploy na Plataforma Web

Na interface web da plataforma (**Enviar Containers**), informe:

* **Arquivo:** `event-extractor.tar`
* **Portas internas:** `8080`
* **Variáveis de ambiente:**

LLM_URL=https://seu-servidor-interno:9001
LLM_MODEL=nome-do-modelo-do-servidor
LLM_TIMEOUT=45
OUTPUT_DIR=data


> **Observação sobre persistência na plataforma:** Na plataforma de containers, apenas arquivos gravados em `/persistent` sobrevivem ao desligamento do container. Para manter os arquivos gerados após reiniciar o container em produção sem alterar o código, basta configurar `OUTPUT_DIR=/persistent` nas variáveis de ambiente da plataforma.


