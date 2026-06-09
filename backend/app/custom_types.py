from sqlalchemy.types import TypeDecorator, TEXT

class CIText(TypeDecorator):
    """Case-insensitive text type for PostgreSQL."""
    impl = TEXT
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import CITEXT
            return dialect.type_descriptor(CITEXT())
        else:
            return dialect.type_descriptor(TEXT())
