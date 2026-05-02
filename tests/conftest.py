"""
Configuración global de pytest.

- Setea variables de entorno requeridas por config.Settings ANTES de que
  cualquier módulo del proyecto las importe (Settings tiene fail-fast en
  imports si no están las API keys).
- Agrega la raíz del proyecto al sys.path para imports sin instalar el paquete.
"""
import os
import sys
from pathlib import Path

# Las settings hacen fail-fast en import si faltan estas variables.
# Para tests, valores fake bastan — los servicios que las usan estarán mockeados.
os.environ.setdefault("OPENAI_API_KEY", "test-fake-key")
os.environ.setdefault("INTERNAL_API_KEY", "test-internal-key")

# Permite imports tipo `from config import settings` sin instalar el paquete.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
