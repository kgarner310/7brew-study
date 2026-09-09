"""API endpoint behaviour."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


class TestHealth:
    def test_reports_ok_with_a_live_database(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["database"] == "ok"
        assert body["version"]


class TestJurisdictionEndpoints:
    def test_lists_all_seeded_jurisdictions(self, seeded_client: TestClient) -> None:
        response = seeded_client.get("/v1/jurisdictions", params={"limit": 200})
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 70  # 50 states + DC + 5 territories + BIE + US + 12 circuits
        assert len(body["items"]) == 70

    def test_filters_by_type(self, seeded_client: TestClient) -> None:
        response = seeded_client.get(
            "/v1/jurisdictions", params={"jurisdiction_type": "state", "limit": 200}
        )
        assert response.json()["total"] == 50

    def test_gets_one_by_slug(self, seeded_client: TestClient) -> None:
        response = seeded_client.get("/v1/jurisdictions/nc")
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "North Carolina"
        assert body["federal_circuit"] == "4th"
        assert body["idea_part_b_applicable"] is True

    def test_gets_one_by_postal_code(self, seeded_client: TestClient) -> None:
        assert seeded_client.get("/v1/jurisdictions/NC").json()["slug"] == "nc"

    def test_reports_zero_coverage_honestly(self, seeded_client: TestClient) -> None:
        """An un-ingested jurisdiction must report zeros, not be hidden."""
        body = seeded_client.get("/v1/jurisdictions/nc").json()
        assert body["authority_count"] == 0
        assert body["coverage"]["statutes"] == 0
        assert body["coverage"]["due_process"] == 0
        assert body["manifest_verified_sites"] == 0

    def test_unknown_slug_returns_404(self, seeded_client: TestClient) -> None:
        response = seeded_client.get("/v1/jurisdictions/atlantis")
        assert response.status_code == 404
        assert response.json()["error"] == "not_found"

    def test_paging_is_bounded(self, seeded_client: TestClient) -> None:
        assert seeded_client.get("/v1/jurisdictions", params={"limit": 5000}).status_code == 422


class TestConceptEndpoints:
    def test_lists_the_taxonomy(self, seeded_client: TestClient) -> None:
        body = seeded_client.get("/v1/concepts", params={"limit": 100}).json()
        assert body["total"] == 43

    def test_filters_by_idea_part(self, seeded_client: TestClient) -> None:
        body = seeded_client.get(
            "/v1/concepts", params={"idea_part": "part_c", "limit": 100}
        ).json()
        assert body["total"] == 4

    def test_gets_one_with_children(self, seeded_client: TestClient) -> None:
        body = seeded_client.get("/v1/concepts/evaluation").json()
        assert body["name"] == "Evaluation"
        child_slugs = {child["slug"] for child in body["children"]}
        assert "initial-evaluation" in child_slugs

    def test_exposes_aliases_for_client_side_matching(self, seeded_client: TestClient) -> None:
        body = seeded_client.get("/v1/concepts/initial-evaluation").json()
        assert "mtss" in body["aliases"]
        assert body["parent_slug"] == "evaluation"

    def test_unknown_concept_returns_404(self, seeded_client: TestClient) -> None:
        assert seeded_client.get("/v1/concepts/nonsense").status_code == 404


class TestAuthorityAndPropositionEndpoints:
    def test_authorities_empty_before_ingestion(self, seeded_client: TestClient) -> None:
        assert seeded_client.get("/v1/authorities").json()["total"] == 0

    def test_propositions_empty_before_seeding(self, seeded_client: TestClient) -> None:
        assert seeded_client.get("/v1/propositions").json()["total"] == 0

    def test_authority_404_for_unknown_id(self, seeded_client: TestClient) -> None:
        unknown = "00000000-0000-0000-0000-000000000000"
        assert seeded_client.get(f"/v1/authorities/{unknown}").status_code == 404

    def test_malformed_uuid_is_rejected(self, seeded_client: TestClient) -> None:
        assert seeded_client.get("/v1/authorities/not-a-uuid").status_code == 422


class TestSearch:
    def test_finds_concepts_by_name(self, seeded_client: TestClient) -> None:
        hits = seeded_client.get("/v1/search", params={"q": "manifestation"}).json()
        assert any(h["entity_type"] == "concept" for h in hits)
        assert any("Manifestation" in h["title"] for h in hits)

    def test_requires_a_minimum_query_length(self, seeded_client: TestClient) -> None:
        assert seeded_client.get("/v1/search", params={"q": "a"}).status_code == 422

    def test_returns_empty_for_no_match(self, seeded_client: TestClient) -> None:
        assert seeded_client.get("/v1/search", params={"q": "zzzznotathing"}).json() == []

    def test_respects_the_limit(self, seeded_client: TestClient) -> None:
        hits = seeded_client.get("/v1/search", params={"q": "e", "limit": 3}).json()
        assert len(hits) <= 3


class TestSecurityPosture:
    def test_no_cors_headers_by_default(self, seeded_client: TestClient) -> None:
        """Deny-by-default: an empty origin allowlist means no browser access."""
        response = seeded_client.get("/v1/concepts", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in {k.lower() for k in response.headers}

    def test_oversized_request_body_is_rejected(self, seeded_client: TestClient) -> None:
        payload = {"issue": "x" * 3_000_000, "detail": "compact"}
        response = seeded_client.post("/v1/research", json=payload)
        assert response.status_code in (413, 422)

    def test_request_id_is_echoed(self, seeded_client: TestClient) -> None:
        response = seeded_client.get("/health", headers={"X-Request-ID": "test-request-123"})
        assert response.headers["x-request-id"] == "test-request-123"

    def test_request_id_is_generated_when_absent(self, seeded_client: TestClient) -> None:
        assert seeded_client.get("/health").headers.get("x-request-id")

    def test_openapi_documents_every_endpoint(self, seeded_client: TestClient) -> None:
        paths = seeded_client.get("/openapi.json").json()["paths"]
        assert {
            "/health",
            "/v1/jurisdictions",
            "/v1/jurisdictions/{slug}",
            "/v1/concepts",
            "/v1/concepts/{slug}",
            "/v1/authorities",
            "/v1/authorities/{authority_id}",
            "/v1/propositions",
            "/v1/propositions/{proposition_id}",
            "/v1/search",
            "/v1/research",
        } <= set(paths)
