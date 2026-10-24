"""Restore the configured SQLite database without loading Django settings."""
import sys

from django.core.exceptions import ValidationError

from aplicativos.integracoes.services.arion_database import rollback_to_previous


def main():
    try:
        rollback_to_previous()
    except ValidationError as exc:
        print("Rollback nao aplicado: " + " ".join(str(item) for item in exc.messages), file=sys.stderr)
        return 1
    print("SQLite configurado como ativo para o proximo inicio. Reinicie servidor web e integration_worker.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
