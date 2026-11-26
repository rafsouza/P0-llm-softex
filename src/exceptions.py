class EventExtractorError(Exception):
    """Exceção base da aplicação."""


class EmptyInputError(EventExtractorError):
    """Entrada vazia ou composta apenas por espaços em branco."""


class ConfigurationError(EventExtractorError):
    """Configuração de acesso ausente ou com formato inválido."""


class MissingCredentialError(ConfigurationError):
    """Credencial obrigatória de acesso ao LLM não configurada."""


class InvalidCredentialError(EventExtractorError):
    """Credencial rejeitada pelo servidor LLM (HTTP 401 ou 403)."""


class ModelUnavailableError(EventExtractorError):
    """Modelo escolhido não encontrado (HTTP 404) ou serviço indisponível (HTTP 503)."""


class CommunicationError(EventExtractorError):
    """Falha de rede ou comunicação ao tentar alcançar o servidor LLM."""


class LLMTimeoutError(EventExtractorError):
    """Tempo limite excedido aguardando resposta do servidor LLM."""


class InvalidResponseError(EventExtractorError):
    """Resposta vazia, JSON inválido ou estrutura inesperada retornada pelo LLM."""