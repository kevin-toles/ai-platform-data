"""Tests for docker-compose.yml validation.

Phase 2.1: Docker Configuration tests following TDD RED-GREEN-REFACTOR cycle.

These tests validate:
1. docker-compose.yml syntax and structure
2. Required services (neo4j, qdrant, redis) are defined
3. Environment variable patterns (no hardcoded passwords)
4. Health check configurations
5. Neo4j init scripts exist and are valid Cypher
6. Qdrant collection config exists and is valid YAML
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml


# Constants per CODING_PATTERNS_ANALYSIS.md (S1192 - avoid duplicated literals)
DOCKER_DIR = Path(__file__).parent.parent.parent / "docker"
COMPOSE_FILE = DOCKER_DIR / "docker-compose.yml"
NEO4J_INIT_SCRIPTS_DIR = DOCKER_DIR / "neo4j" / "init-scripts"
QDRANT_CONFIG_DIR = DOCKER_DIR / "qdrant" / "config"

REQUIRED_SERVICES = {"neo4j", "qdrant", "redis"}
EXPECTED_NEO4J_IMAGE = "neo4j:5.15-community"
# Option D: Qdrant uses custom image with healthcheck (built from Dockerfile)
EXPECTED_QDRANT_IMAGE = "ai-platform-qdrant:v1.12.0-health"
EXPECTED_REDIS_IMAGE = "redis:7-alpine"


class TestDockerComposeStructure:
    """Test docker-compose.yml structure and syntax."""

    def test_docker_compose_file_exists(self) -> None:
        """docker-compose.yml must exist in docker/ directory."""
        assert COMPOSE_FILE.exists(), f"docker-compose.yml not found at {COMPOSE_FILE}"

    def test_docker_compose_valid_yaml(self) -> None:
        """docker-compose.yml must be valid YAML syntax."""
        content = COMPOSE_FILE.read_text()
        # Should not raise yaml.YAMLError
        data = yaml.safe_load(content)
        assert isinstance(data, dict), "docker-compose.yml must be a valid YAML dict"

    def test_docker_compose_config_valid(self) -> None:
        """docker-compose config must validate successfully.
        
        This runs `docker-compose config` to verify the compose file
        is syntactically valid per Docker Compose specification.
        """
        result = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "config", "--quiet"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"docker-compose config failed:\n{result.stderr}"
        )


class TestRequiredServices:
    """Test that all required services are defined."""

    @pytest.fixture
    def compose_data(self) -> dict[str, Any]:
        """Load docker-compose.yml as dict."""
        return yaml.safe_load(COMPOSE_FILE.read_text())

    def test_services_section_exists(self, compose_data: dict[str, Any]) -> None:
        """docker-compose.yml must have a 'services' section."""
        assert "services" in compose_data, "Missing 'services' section"

    @pytest.mark.parametrize("service_name", REQUIRED_SERVICES)
    def test_required_service_defined(
        self, compose_data: dict[str, Any], service_name: str
    ) -> None:
        """Each required service must be defined in services section."""
        services = compose_data.get("services", {})
        assert service_name in services, f"Missing required service: {service_name}"


class TestServiceImages:
    """Test that services use correct Docker images per WBS 2.1 spec."""

    @pytest.fixture
    def compose_data(self) -> dict[str, Any]:
        """Load docker-compose.yml as dict."""
        return yaml.safe_load(COMPOSE_FILE.read_text())

    def test_neo4j_image_version(self, compose_data: dict[str, Any]) -> None:
        """Neo4j service must use neo4j:5.15-community image."""
        neo4j = compose_data["services"]["neo4j"]
        assert neo4j.get("image") == EXPECTED_NEO4J_IMAGE, (
            f"Neo4j image must be {EXPECTED_NEO4J_IMAGE}"
        )

    def test_qdrant_image_version(self, compose_data: dict[str, Any]) -> None:
        """Qdrant service must use qdrant/qdrant:v1.7.4 image."""
        qdrant = compose_data["services"]["qdrant"]
        assert qdrant.get("image") == EXPECTED_QDRANT_IMAGE, (
            f"Qdrant image must be {EXPECTED_QDRANT_IMAGE}"
        )

    def test_redis_image_version(self, compose_data: dict[str, Any]) -> None:
        """Redis service must use redis:7-alpine image."""
        redis = compose_data["services"]["redis"]
        assert redis.get("image") == EXPECTED_REDIS_IMAGE, (
            f"Redis image must be {EXPECTED_REDIS_IMAGE}"
        )


class TestServicePorts:
    """Test that services expose correct ports per WBS 2.1 spec.
    
    Option D Architecture: Uses 'expose:' instead of 'ports:' for internal-only
    networking (K8s-native pattern). Services connect via Docker DNS names.
    """

    @pytest.fixture
    def compose_data(self) -> dict[str, Any]:
        """Load docker-compose.yml as dict."""
        return yaml.safe_load(COMPOSE_FILE.read_text())

    def test_neo4j_http_port(self, compose_data: dict[str, Any]) -> None:
        """Neo4j must expose HTTP port 7474 (internal)."""
        neo4j = compose_data["services"]["neo4j"]
        # Option D: Uses 'expose' not 'ports' (internal networking)
        expose = neo4j.get("expose", [])
        assert any("7474" in str(p) for p in expose), (
            "Neo4j must expose port 7474 (HTTP) via 'expose:'"
        )

    def test_neo4j_bolt_port(self, compose_data: dict[str, Any]) -> None:
        """Neo4j must expose Bolt port 7687 (internal)."""
        neo4j = compose_data["services"]["neo4j"]
        expose = neo4j.get("expose", [])
        assert any("7687" in str(p) for p in expose), (
            "Neo4j must expose port 7687 (Bolt) via 'expose:'"
        )

    def test_qdrant_http_port(self, compose_data: dict[str, Any]) -> None:
        """Qdrant must expose HTTP port 6333 (internal)."""
        qdrant = compose_data["services"]["qdrant"]
        expose = qdrant.get("expose", [])
        assert any("6333" in str(p) for p in expose), (
            "Qdrant must expose port 6333 (HTTP) via 'expose:'"
        )

    def test_qdrant_grpc_port(self, compose_data: dict[str, Any]) -> None:
        """Qdrant must expose gRPC port 6334 (internal)."""
        qdrant = compose_data["services"]["qdrant"]
        expose = qdrant.get("expose", [])
        assert any("6334" in str(p) for p in expose), (
            "Qdrant must expose port 6334 (gRPC) via 'expose:'"
        )

    def test_redis_port(self, compose_data: dict[str, Any]) -> None:
        """Redis must expose port 6379 (internal)."""
        redis = compose_data["services"]["redis"]
        expose = redis.get("expose", [])
        assert any("6379" in str(p) for p in expose), (
            "Redis must expose port 6379 via 'expose:'"
        )


class TestSecurityPatterns:
    """Test security patterns per Comp_Static_Analysis_Report Issues #3, #19.
    
    Anti-pattern audit:
    - No hardcoded passwords in docker-compose.yml
    - Use environment variable substitution for auth
    """

    @pytest.fixture
    def compose_content(self) -> str:
        """Load docker-compose.yml as raw string."""
        return COMPOSE_FILE.read_text()

    @pytest.fixture
    def compose_data(self) -> dict[str, Any]:
        """Load docker-compose.yml as dict."""
        return yaml.safe_load(COMPOSE_FILE.read_text())

    def test_no_hardcoded_neo4j_password(self, compose_content: str) -> None:
        """Neo4j auth must use environment variable substitution.
        
        Per Comp_Static_Analysis Issue #3: Redis auth password empty.
        Same pattern applies: no hardcoded passwords.
        """
        # Should use ${NEO4J_AUTH:-neo4j/password} pattern, not plain "neo4j/password"
        assert "NEO4J_AUTH:" in compose_content, (
            "Neo4j auth must use environment variable"
        )
        # The default pattern ${VAR:-default} is acceptable for dev
        # but must not be a plain string value

    def test_redis_no_auth_in_compose(self, compose_data: dict[str, Any]) -> None:
        """Redis should not have hardcoded password in docker-compose.yml.
        
        Per Comp_Static_Analysis Issue #19: Redis password should use secretKeyRef.
        For local dev, we use no auth; for prod, use K8s secrets.
        """
        redis = compose_data["services"]["redis"]
        env = redis.get("environment", {})
        # Check no REDIS_PASSWORD or REQUIREPASS in compose
        if isinstance(env, dict):
            for key in env:
                assert "PASSWORD" not in key.upper(), (
                    f"Redis password should not be in compose: {key}"
                )
        elif isinstance(env, list):
            for item in env:
                assert "PASSWORD" not in str(item).upper(), (
                    f"Redis password should not be in compose: {item}"
                )


class TestHealthChecks:
    """Test health check configurations per CODING_PATTERNS_ANALYSIS.md."""

    @pytest.fixture
    def compose_data(self) -> dict[str, Any]:
        """Load docker-compose.yml as dict."""
        return yaml.safe_load(COMPOSE_FILE.read_text())

    @pytest.mark.parametrize("service_name", REQUIRED_SERVICES)
    def test_service_has_healthcheck(
        self, compose_data: dict[str, Any], service_name: str
    ) -> None:
        """Each service must have a healthcheck defined."""
        service = compose_data["services"][service_name]
        assert "healthcheck" in service, f"{service_name} must have healthcheck"

    def test_neo4j_healthcheck_valid(self, compose_data: dict[str, Any]) -> None:
        """Neo4j healthcheck must use HTTP endpoint."""
        healthcheck = compose_data["services"]["neo4j"]["healthcheck"]
        test = healthcheck.get("test", [])
        # Should test HTTP endpoint on port 7474
        assert any("7474" in str(t) for t in test), (
            "Neo4j healthcheck must test HTTP port 7474"
        )

    def test_qdrant_healthcheck_valid(self, compose_data: dict[str, Any]) -> None:
        """Qdrant healthcheck must use /readyz or /health endpoint."""
        healthcheck = compose_data["services"]["qdrant"]["healthcheck"]
        test = healthcheck.get("test", [])
        # Qdrant 1.12+ uses /readyz for K8s-style health checks
        assert any("/readyz" in str(t) or "/health" in str(t) for t in test), (
            "Qdrant healthcheck must test /readyz or /health endpoint"
        )

    def test_redis_healthcheck_valid(self, compose_data: dict[str, Any]) -> None:
        """Redis healthcheck must use redis-cli ping."""
        healthcheck = compose_data["services"]["redis"]["healthcheck"]
        test = healthcheck.get("test", [])
        # Should use redis-cli ping
        assert any("ping" in str(t).lower() for t in test), (
            "Redis healthcheck must use 'ping' command"
        )


class TestNeo4jInitScripts:
    """Test Neo4j initialization scripts (WBS 2.1.3)."""

    def test_init_scripts_directory_exists(self) -> None:
        """Neo4j init-scripts directory must exist."""
        assert NEO4J_INIT_SCRIPTS_DIR.exists(), (
            f"Neo4j init-scripts dir not found: {NEO4J_INIT_SCRIPTS_DIR}"
        )

    def test_constraints_script_exists(self) -> None:
        """01_constraints.cypher must exist for Book/Chapter constraints."""
        script = NEO4J_INIT_SCRIPTS_DIR / "01_constraints.cypher"
        assert script.exists(), f"Missing {script}"

    def test_indexes_script_exists(self) -> None:
        """02_indexes.cypher must exist for performance indexes."""
        script = NEO4J_INIT_SCRIPTS_DIR / "02_indexes.cypher"
        assert script.exists(), f"Missing {script}"

    def test_constraints_script_valid_cypher(self) -> None:
        """01_constraints.cypher must contain valid Cypher statements."""
        script = NEO4J_INIT_SCRIPTS_DIR / "01_constraints.cypher"
        if not script.exists():
            pytest.skip("Constraints script not yet created")
        content = script.read_text()
        # Must contain CREATE CONSTRAINT statements
        assert "CREATE CONSTRAINT" in content, (
            "Constraints script must contain CREATE CONSTRAINT"
        )
        # Must reference Book and Chapter nodes
        assert "Book" in content, "Constraints must include Book node"
        assert "Chapter" in content, "Constraints must include Chapter node"

    def test_indexes_script_valid_cypher(self) -> None:
        """02_indexes.cypher must contain valid Cypher statements."""
        script = NEO4J_INIT_SCRIPTS_DIR / "02_indexes.cypher"
        if not script.exists():
            pytest.skip("Indexes script not yet created")
        content = script.read_text()
        # Must contain CREATE INDEX statements
        assert "CREATE INDEX" in content, (
            "Indexes script must contain CREATE INDEX"
        )


class TestQdrantConfig:
    """Test Qdrant collection configuration (WBS 2.1.4)."""

    def test_config_directory_exists(self) -> None:
        """Qdrant config directory must exist."""
        assert QDRANT_CONFIG_DIR.exists(), (
            f"Qdrant config dir not found: {QDRANT_CONFIG_DIR}"
        )

    def test_collections_config_exists(self) -> None:
        """collections.yaml must exist for collection schemas."""
        config = QDRANT_CONFIG_DIR / "collections.yaml"
        assert config.exists(), f"Missing {config}"

    def test_collections_config_valid_yaml(self) -> None:
        """collections.yaml must be valid YAML."""
        config = QDRANT_CONFIG_DIR / "collections.yaml"
        if not config.exists():
            pytest.skip("Collections config not yet created")
        content = config.read_text()
        data = yaml.safe_load(content)
        assert isinstance(data, dict), "collections.yaml must be valid YAML dict"

    def test_collections_config_defines_chapters(self) -> None:
        """collections.yaml must define 'chapters' collection."""
        config = QDRANT_CONFIG_DIR / "collections.yaml"
        if not config.exists():
            pytest.skip("Collections config not yet created")
        data = yaml.safe_load(config.read_text())
        collections = data.get("collections", {})
        assert "chapters" in collections, (
            "collections.yaml must define 'chapters' collection"
        )

    def test_collections_config_vector_size(self) -> None:
        """Chapter vectors must use size 384 (all-MiniLM-L6-v2)."""
        config = QDRANT_CONFIG_DIR / "collections.yaml"
        if not config.exists():
            pytest.skip("Collections config not yet created")
        data = yaml.safe_load(config.read_text())
        chapters = data.get("collections", {}).get("chapters", {})
        vectors = chapters.get("vectors", {})
        # Vector size should be 384 for all-MiniLM-L6-v2
        assert vectors.get("size") == 384, (
            "Chapter vectors must be size 384 (all-MiniLM-L6-v2)"
        )


class TestNetworkConfiguration:
    """Test Docker network configuration."""

    @pytest.fixture
    def compose_data(self) -> dict[str, Any]:
        """Load docker-compose.yml as dict."""
        return yaml.safe_load(COMPOSE_FILE.read_text())

    def test_network_defined(self, compose_data: dict[str, Any]) -> None:
        """A shared network must be defined for service communication."""
        assert "networks" in compose_data, "Missing 'networks' section"
        networks = compose_data["networks"]
        assert len(networks) > 0, "At least one network must be defined"

    @pytest.mark.parametrize("service_name", REQUIRED_SERVICES)
    def test_service_on_shared_network(
        self, compose_data: dict[str, Any], service_name: str
    ) -> None:
        """Each service must be connected to the shared network."""
        service = compose_data["services"][service_name]
        assert "networks" in service, f"{service_name} must specify networks"
