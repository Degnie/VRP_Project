"""Tests de infraestructura de empaquetado y CI (RNF-004, RNF-005, RNF-007).

No ejercitan build real de Docker ni ejecutan el pipeline — verifican que
los artefactos exigidos por el SPEC existan con el contenido mínimo
requerido, mismo patrón de verificación estática que el resto de la suite
usa para reglas no funcionales de configuración.
"""

from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


class TestDockerPackaging:
    """spec: RNF-004"""

    def test_backend_dockerfile_exists(self):
        assert (ROOT / "backend_python" / "Dockerfile").is_file()

    def test_frontend_dockerfile_exists(self):
        assert (ROOT / "frontend" / "Dockerfile").is_file()

    def test_backend_dockerfile_runs_as_non_root_user(self):
        content = (ROOT / "backend_python" / "Dockerfile").read_text(encoding="utf-8")
        assert "USER " in content
        assert "USER root" not in content

    def test_frontend_dockerfile_runs_as_non_root_user(self):
        content = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
        assert "USER " in content
        assert "USER root" not in content


class TestContinuousIntegration:
    """spec: RNF-005"""

    def test_ci_workflow_exists(self):
        assert (ROOT / ".github" / "workflows" / "ci.yml").is_file()

    def test_ci_workflow_runs_pytest(self):
        content = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        assert "pytest" in content

    def test_ci_workflow_runs_traceability_check(self):
        content = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        assert "check_traceability.py" in content

    def test_ci_workflow_triggers_on_pull_request(self):
        content = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        assert "pull_request" in content


class TestImageBuildValidation:
    """spec: RNF-007"""

    def test_ci_workflow_builds_backend_image(self):
        content = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        assert "docker build" in content
        assert "backend_python/Dockerfile" in content

    def test_ci_workflow_builds_frontend_image(self):
        content = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        assert "docker build -t vrp-frontend frontend/" in content

    def test_ci_workflow_does_not_push_images(self):
        # RNF-007 exige solo build de validación, sin publicar a ningún
        # registro — "docker push" no debe aparecer en el workflow.
        content = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        assert "docker push" not in content
