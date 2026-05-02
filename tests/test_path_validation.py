"""
Tests de la validación de path traversal en /process.

Cubre:
- Casos válidos (path dentro de uploads_base_path).
- Casos hostiles (escape con ..).
- Casos de error (archivo inexistente, path inválido).
"""
import pytest
from pathlib import Path
from routers.process import _validate_file_path
from config import settings


@pytest.fixture
def uploads_dir(tmp_path, monkeypatch):
    """
    Crea un directorio de uploads aislado por test y configura
    settings.uploads_base_path para que apunte ahí.
    """
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    monkeypatch.setattr(settings, "uploads_base_path", str(uploads))
    return uploads


class TestValidPaths:
    def test_normal_path_within_uploads_passes(self, uploads_dir):
        bot_dir = uploads_dir / "bot-123"
        bot_dir.mkdir()
        file_path = bot_dir / "uuid_doc.pdf"
        file_path.write_text("contenido")

        result = _validate_file_path(str(file_path))
        assert result == file_path.resolve()

    def test_dotdot_that_resolves_inside_passes(self, uploads_dir):
        # uploads/bot-x/../bot-y/file.pdf → resuelve a uploads/bot-y/file.pdf,
        # sigue dentro del base, debería pasar.
        bot_y = uploads_dir / "bot-y"
        bot_y.mkdir()
        file_path = bot_y / "file.pdf"
        file_path.write_text("contenido")

        tricky_path = str(uploads_dir / "bot-x" / ".." / "bot-y" / "file.pdf")
        result = _validate_file_path(tricky_path)
        assert result == file_path.resolve()


class TestInvalidPaths:
    def test_path_outside_uploads_rejected(self, uploads_dir, tmp_path):
        # Archivo fuera del directorio uploads.
        outside = tmp_path / "outside.pdf"
        outside.write_text("secreto")

        with pytest.raises(ValueError, match="no permitido"):
            _validate_file_path(str(outside))

    def test_dotdot_escape_rejected(self, uploads_dir):
        # uploads/../../etc/passwd — incluso si el archivo no existe, debería
        # rechazar por estar fuera del base ANTES de chequear existencia.
        escape_path = str(uploads_dir / ".." / ".." / "etc" / "passwd")
        with pytest.raises(ValueError, match="no permitido"):
            _validate_file_path(escape_path)

    def test_nonexistent_file_within_uploads_rejected(self, uploads_dir):
        # Path está dentro del directorio permitido pero el archivo no existe.
        ghost = uploads_dir / "bot-x" / "ghost.pdf"
        with pytest.raises(FileNotFoundError):
            _validate_file_path(str(ghost))

    def test_directory_instead_of_file_rejected(self, uploads_dir):
        # is_file() debe rechazar paths que apunten a directorios.
        bot_dir = uploads_dir / "bot-z"
        bot_dir.mkdir()
        with pytest.raises(FileNotFoundError):
            _validate_file_path(str(bot_dir))

    def test_prefix_lookalike_rejected(self, uploads_dir, tmp_path):
        # uploads/ vs uploads-fake/ — no debe matchear por prefix string.
        fake = tmp_path / "uploads-fake"
        fake.mkdir()
        sneaky = fake / "file.pdf"
        sneaky.write_text("contenido")

        with pytest.raises(ValueError, match="no permitido"):
            _validate_file_path(str(sneaky))
