import html


def escape_html_field(value: str | None) -> str | None:
    """Экранирует HTML-символы в строковом поле для предотвращения XSS.

    Args:
        value: Значение поля для экранирования.

    Returns:
        Экранированное значение или None.
    """
    if value is not None:
        return html.escape(value)
    return value
