# src/core/exceptions.py
"""
Централизованная система обработки исключений.
Предоставляет иерархию кастомных исключений и декораторы для обработки ошибок.
"""

import logging
import functools
from typing import Optional, Callable, Any, Type
from enum import Enum


# ============================================================================
# ERROR CODES
# ============================================================================

class ErrorCode(Enum):
    """Коды ошибок для категоризации."""

    # Database errors (1xxx)
    DB_CONNECTION_ERROR = 1001
    DB_QUERY_ERROR = 1002
    DB_CONSTRAINT_VIOLATION = 1003
    DB_TRANSACTION_ERROR = 1004

    # Validation errors (2xxx)
    VALIDATION_ERROR = 2001
    MISSING_REQUIRED_FIELD = 2002
    INVALID_DATA_FORMAT = 2003
    DUPLICATE_ENTRY = 2004

    # External API errors (3xxx)
    API_CONNECTION_ERROR = 3001
    API_RATE_LIMIT = 3002
    API_AUTHENTICATION_ERROR = 3003
    API_NOT_FOUND = 3004
    API_SERVER_ERROR = 3005

    # Parsing errors (4xxx)
    SCRAPING_ERROR = 4001
    HTML_PARSING_ERROR = 4002
    DATA_EXTRACTION_ERROR = 4003

    # LLM errors (5xxx)
    LLM_CONNECTION_ERROR = 5001
    LLM_TIMEOUT = 5002
    LLM_INVALID_RESPONSE = 5003

    # Business logic errors (6xxx)
    RESOURCE_NOT_FOUND = 6001
    OPERATION_NOT_ALLOWED = 6002
    INVALID_STATE = 6003

    # System errors (9xxx)
    CONFIGURATION_ERROR = 9001
    FILE_SYSTEM_ERROR = 9002
    UNKNOWN_ERROR = 9999


# ============================================================================
# BASE EXCEPTIONS
# ============================================================================

class NewsAggregatorException(Exception):
    """
    Базовое исключение для всего приложения.
    Все кастомные исключения должны наследоваться от него.
    """

    def __init__(
            self,
            message: str,
            error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
            original_exception: Optional[Exception] = None,
            context: Optional[dict] = None
    ):
        self.message = message
        self.error_code = error_code
        self.original_exception = original_exception
        self.context = context or {}

        super().__init__(self.message)

    def __str__(self) -> str:
        base = f"[{self.error_code.name}] {self.message}"
        if self.context:
            base += f" | Context: {self.context}"
        if self.original_exception:
            base += f" | Original: {type(self.original_exception).__name__}: {self.original_exception}"
        return base

    def to_dict(self) -> dict:
        """Конвертация исключения в словарь для JSON response."""
        return {
            'error': True,
            'error_code': self.error_code.name,
            'error_code_value': self.error_code.value,
            'message': self.message,
            'context': self.context,
            'original_error': (
                str(self.original_exception)
                if self.original_exception else None
            )
        }


# ============================================================================
# DATABASE EXCEPTIONS
# ============================================================================

class DatabaseException(NewsAggregatorException):
    """Базовое исключение для ошибок БД."""

    def __init__(
            self,
            message: str,
            error_code: ErrorCode = ErrorCode.DB_QUERY_ERROR,
            original_exception: Optional[Exception] = None,
            context: Optional[dict] = None
    ):
        super().__init__(message, error_code, original_exception, context)


class DatabaseConnectionError(DatabaseException):
    """Ошибка подключения к БД."""

    def __init__(
            self,
            message: str = "Failed to connect to database",
            original_exception: Optional[Exception] = None,
            context: Optional[dict] = None
    ):
        super().__init__(
            message,
            ErrorCode.DB_CONNECTION_ERROR,
            original_exception,
            context
        )


class DatabaseConstraintViolation(DatabaseException):
    """Нарушение constraint БД (например, unique constraint)."""

    def __init__(
            self,
            message: str = "Database constraint violation",
            original_exception: Optional[Exception] = None,
            context: Optional[dict] = None
    ):
        super().__init__(
            message,
            ErrorCode.DB_CONSTRAINT_VIOLATION,
            original_exception,
            context
        )


# ============================================================================
# VALIDATION EXCEPTIONS
# ============================================================================

class ValidationException(NewsAggregatorException):
    """Базовое исключение для ошибок валидации."""

    def __init__(
            self,
            message: str,
            error_code: ErrorCode = ErrorCode.VALIDATION_ERROR,
            original_exception: Optional[Exception] = None,
            context: Optional[dict] = None
    ):
        super().__init__(message, error_code, original_exception, context)


class MissingRequiredFieldError(ValidationException):
    """Отсутствует обязательное поле."""

    def __init__(
            self,
            field_name: str,
            context: Optional[dict] = None
    ):
        message = f"Missing required field: {field_name}"
        context = context or {}
        context['field_name'] = field_name
        super().__init__(
            message,
            ErrorCode.MISSING_REQUIRED_FIELD,
            context=context
        )


class InvalidDataFormatError(ValidationException):
    """Неверный формат данных."""

    def __init__(
            self,
            field_name: str,
            expected_format: str,
            actual_value: Any,
            context: Optional[dict] = None
    ):
        message = f"Invalid format for field '{field_name}': expected {expected_format}, got {type(actual_value).__name__}"
        context = context or {}
        context.update({
            'field_name': field_name,
            'expected_format': expected_format,
            'actual_type': type(actual_value).__name__
        })
        super().__init__(
            message,
            ErrorCode.INVALID_DATA_FORMAT,
            context=context
        )


class DuplicateEntryError(ValidationException):
    """Попытка создать дубликат записи."""

    def __init__(
            self,
            entity_type: str,
            identifier: str,
            context: Optional[dict] = None
    ):
        message = f"Duplicate {entity_type} with identifier: {identifier}"
        context = context or {}
        context.update({
            'entity_type': entity_type,
            'identifier': identifier
        })
        super().__init__(
            message,
            ErrorCode.DUPLICATE_ENTRY,
            context=context
        )


# ============================================================================
# EXTERNAL API EXCEPTIONS
# ============================================================================

class ExternalAPIException(NewsAggregatorException):
    """Базовое исключение для ошибок внешних API."""

    def __init__(
            self,
            message: str,
            error_code: ErrorCode = ErrorCode.API_CONNECTION_ERROR,
            original_exception: Optional[Exception] = None,
            context: Optional[dict] = None
    ):
        super().__init__(message, error_code, original_exception, context)


class APIRateLimitError(ExternalAPIException):
    """Превышен лимит запросов к API."""

    def __init__(
            self,
            api_name: str,
            retry_after: Optional[int] = None,
            context: Optional[dict] = None
    ):
        message = f"Rate limit exceeded for {api_name}"
        if retry_after:
            message += f", retry after {retry_after} seconds"

        context = context or {}
        context.update({
            'api_name': api_name,
            'retry_after': retry_after
        })
        super().__init__(
            message,
            ErrorCode.API_RATE_LIMIT,
            context=context
        )


class APINotFoundError(ExternalAPIException):
    """Ресурс не найден (HTTP 404)."""

    def __init__(
            self,
            url: str,
            context: Optional[dict] = None
    ):
        message = f"Resource not found: {url}"
        context = context or {}
        context['url'] = url
        super().__init__(
            message,
            ErrorCode.API_NOT_FOUND,
            context=context
        )


# ============================================================================
# PARSING EXCEPTIONS
# ============================================================================

class ParsingException(NewsAggregatorException):
    """Базовое исключение для ошибок парсинга."""

    def __init__(
            self,
            message: str,
            error_code: ErrorCode = ErrorCode.SCRAPING_ERROR,
            original_exception: Optional[Exception] = None,
            context: Optional[dict] = None
    ):
        super().__init__(message, error_code, original_exception, context)


class HTMLParsingError(ParsingException):
    """Ошибка парсинга HTML."""

    def __init__(
            self,
            url: str,
            selector: Optional[str] = None,
            original_exception: Optional[Exception] = None,
            context: Optional[dict] = None
    ):
        message = f"Failed to parse HTML from {url}"
        if selector:
            message += f" using selector '{selector}'"

        context = context or {}
        context.update({
            'url': url,
            'selector': selector
        })
        super().__init__(
            message,
            ErrorCode.HTML_PARSING_ERROR,
            original_exception,
            context
        )


# ============================================================================
# LLM EXCEPTIONS
# ============================================================================

class LLMException(NewsAggregatorException):
    """Базовое исключение для ошибок LLM."""

    def __init__(
            self,
            message: str,
            error_code: ErrorCode = ErrorCode.LLM_CONNECTION_ERROR,
            original_exception: Optional[Exception] = None,
            context: Optional[dict] = None
    ):
        super().__init__(message, error_code, original_exception, context)


class LLMTimeoutError(LLMException):
    """Таймаут при обращении к LLM."""

    def __init__(
            self,
            model_name: str,
            timeout_seconds: int,
            context: Optional[dict] = None
    ):
        message = f"LLM timeout: {model_name} did not respond within {timeout_seconds}s"
        context = context or {}
        context.update({
            'model_name': model_name,
            'timeout_seconds': timeout_seconds
        })
        super().__init__(
            message,
            ErrorCode.LLM_TIMEOUT,
            context=context
        )


# ============================================================================
# BUSINESS LOGIC EXCEPTIONS
# ============================================================================

class ResourceNotFoundException(NewsAggregatorException):
    """Ресурс не найден в системе."""

    def __init__(
            self,
            resource_type: str,
            resource_id: str,
            context: Optional[dict] = None
    ):
        message = f"{resource_type} not found: {resource_id}"
        context = context or {}
        context.update({
            'resource_type': resource_type,
            'resource_id': resource_id
        })
        super().__init__(
            message,
            ErrorCode.RESOURCE_NOT_FOUND,
            context=context
        )


# ============================================================================
# ERROR HANDLING DECORATORS
# ============================================================================

def handle_database_errors(func: Callable) -> Callable:
    """
    Декоратор для обработки ошибок БД.
    Конвертирует SQLAlchemy ошибки в кастомные исключения.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger = logging.getLogger(func.__module__)

            # Импорт здесь чтобы избежать circular import
            from sqlalchemy.exc import (
                IntegrityError,
                OperationalError,
                DatabaseError
            )

            if isinstance(e, IntegrityError):
                logger.error(f"Database constraint violation in {func.__name__}: {e}")
                raise DatabaseConstraintViolation(
                    message=str(e),
                    original_exception=e,
                    context={'function': func.__name__}
                )
            elif isinstance(e, OperationalError):
                logger.error(f"Database connection error in {func.__name__}: {e}")
                raise DatabaseConnectionError(
                    message=str(e),
                    original_exception=e,
                    context={'function': func.__name__}
                )
            elif isinstance(e, DatabaseError):
                logger.error(f"Database error in {func.__name__}: {e}")
                raise DatabaseException(
                    message=str(e),
                    original_exception=e,
                    context={'function': func.__name__}
                )
            else:
                # Если это не SQLAlchemy ошибка, пробрасываем дальше
                raise

    return wrapper


def handle_api_errors(api_name: str) -> Callable:
    """
    Декоратор для обработки ошибок внешних API.

    Args:
        api_name: Название API для контекста
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger = logging.getLogger(func.__module__)

                # Проверка HTTP ошибок
                if hasattr(e, 'status_code'):
                    status_code = e.status_code

                    if status_code == 404:
                        logger.warning(f"API resource not found in {func.__name__}")
                        raise APINotFoundError(
                            url=str(kwargs.get('url', 'unknown')),
                            context={
                                'api_name': api_name,
                                'function': func.__name__
                            }
                        )
                    elif status_code == 429:
                        logger.warning(f"API rate limit exceeded in {func.__name__}")
                        retry_after = getattr(e, 'retry_after', None)
                        raise APIRateLimitError(
                            api_name=api_name,
                            retry_after=retry_after,
                            context={'function': func.__name__}
                        )
                    elif status_code >= 500:
                        logger.error(f"API server error in {func.__name__}: {e}")
                        raise ExternalAPIException(
                            message=f"{api_name} server error",
                            error_code=ErrorCode.API_SERVER_ERROR,
                            original_exception=e,
                            context={
                                'api_name': api_name,
                                'function': func.__name__,
                                'status_code': status_code
                            }
                        )

                # Общая обработка
                logger.error(f"API error in {func.__name__}: {e}")
                raise ExternalAPIException(
                    message=f"Error calling {api_name}",
                    original_exception=e,
                    context={
                        'api_name': api_name,
                        'function': func.__name__
                    }
                )

        return wrapper

    return decorator


def retry_on_error(
        max_attempts: int = 3,
        delay_seconds: float = 1.0,
        backoff_factor: float = 2.0,
        exception_types: tuple = (Exception,)
) -> Callable:
    """
    Декоратор для повторных попыток при ошибках.

    Args:
        max_attempts: Максимальное количество попыток
        delay_seconds: Начальная задержка между попытками
        backoff_factor: Множитель для экспоненциальной задержки
        exception_types: Типы исключений для повтора
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import time

            logger = logging.getLogger(func.__module__)
            attempt = 0
            current_delay = delay_seconds

            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exception_types as e:
                    attempt += 1

                    if attempt >= max_attempts:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}: {e}"
                        )
                        raise

                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed for {func.__name__}, "
                        f"retrying in {current_delay}s: {e}"
                    )

                    time.sleep(current_delay)
                    current_delay *= backoff_factor

        return wrapper

    return decorator


# ============================================================================
# ERROR LOGGER
# ============================================================================

class ErrorLogger:
    """Централизованный логгер ошибок."""

    def __init__(self, logger_name: str = __name__):
        self.logger = logging.getLogger(logger_name)

    def log_exception(
            self,
            exception: Exception,
            context: Optional[dict] = None,
            log_level: int = logging.ERROR
    ):
        """
        Логирование исключения с контекстом.

        Args:
            exception: Исключение для логирования
            context: Дополнительный контекст
            log_level: Уровень логирования
        """
        if isinstance(exception, NewsAggregatorException):
            message = str(exception)
            if context:
                message += f" | Additional context: {context}"

            self.logger.log(log_level, message, exc_info=True)

            # Дополнительное структурированное логирование
            self.logger.log(
                log_level,
                "Exception details",
                extra={
                    'error_code': exception.error_code.name,
                    'error_code_value': exception.error_code.value,
                    'context': {**exception.context, **(context or {})}
                }
            )
        else:
            # Обычное исключение
            message = f"Unexpected error: {type(exception).__name__}: {exception}"
            if context:
                message += f" | Context: {context}"

            self.logger.log(log_level, message, exc_info=True)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Error codes
    'ErrorCode',

    # Base exceptions
    'NewsAggregatorException',

    # Database exceptions
    'DatabaseException',
    'DatabaseConnectionError',
    'DatabaseConstraintViolation',

    # Validation exceptions
    'ValidationException',
    'MissingRequiredFieldError',
    'InvalidDataFormatError',
    'DuplicateEntryError',

    # API exceptions
    'ExternalAPIException',
    'APIRateLimitError',
    'APINotFoundError',

    # Parsing exceptions
    'ParsingException',
    'HTMLParsingError',

    # LLM exceptions
    'LLMException',
    'LLMTimeoutError',

    # Business logic exceptions
    'ResourceNotFoundException',

    # Decorators
    'handle_database_errors',
    'handle_api_errors',
    'retry_on_error',

    # Utilities
    'ErrorLogger',
]