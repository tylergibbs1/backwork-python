"""Backwork API Client."""

from typing import Any, Dict, List, Optional, Union
import httpx

from .exceptions import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    BackworkError,
)


class BackworkClient:
    """Client for interacting with the Backwork API.
    
    Args:
        api_key: Your Backwork API key (bwk_live_* or bwk_test_*)
        base_url: Base URL for the API (default: production)
        timeout: Request timeout in seconds
    
    Example:
        >>> client = BackworkClient("bwk_live_abc123")
        >>> result = client.lookup_code("76942")
        >>> print(result["data"]["description"])
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://backworkhealth.com/api/v1",
        timeout: float = 30.0,
    ):
        if not api_key:
            raise ValueError("API key is required")
        
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        
        self._client = httpx.Client(
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "backwork-api-python/1.0.0",
            },
            timeout=timeout,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make an HTTP request to the API."""
        url = f"{self.base_url}{path}"
        
        try:
            response = self._client.request(
                method=method,
                url=url,
                params=params,
                json=json,
                headers=headers,
            )
            
            if 200 <= response.status_code < 300:
                if not response.content:
                    return {"success": True, "data": None}
                return response.json()
            
            # Handle error responses
            try:
                error_data = response.json()
                error_info = error_data.get("error", {})
                message = error_info.get("message", "Unknown error")
                code = error_info.get("code")
                hint = error_info.get("hint")
                details = error_info.get("details")
            except Exception:
                message = response.text or f"HTTP {response.status_code}"
                code = None
                hint = None
                details = None
            
            if response.status_code == 401:
                raise AuthenticationError(message, code=code, hint=hint, details=details)
            elif response.status_code == 404:
                raise NotFoundError(message, code=code, hint=hint, details=details)
            elif response.status_code == 429:
                raise RateLimitError(
                    message,
                    code=code,
                    hint=hint,
                    details=details,
                    limit=response.headers.get("X-RateLimit-Limit"),
                    remaining=response.headers.get("X-RateLimit-Remaining"),
                    reset=response.headers.get("X-RateLimit-Reset"),
                )
            elif response.status_code == 400:
                raise ValidationError(message, code=code, hint=hint, details=details)
            else:
                raise BackworkError(message, code=code, hint=hint, details=details)
                
        except httpx.HTTPError as e:
            raise BackworkError(f"HTTP error: {str(e)}")

    # Health Check
    def health(self) -> Dict[str, Any]:
        """Check API health status.
        
        Returns:
            Health status including database and Redis checks.
        """
        return self._request("GET", "/health")

    # Code Lookup
    def lookup_code(
        self,
        code: str,
        code_system: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        include: Optional[List[str]] = None,
        fuzzy: bool = True,
    ) -> Dict[str, Any]:
        """Look up a medical code and get coverage information.
        
        Args:
            code: The medical code to look up (CPT, HCPCS, ICD-10, NDC)
            code_system: Hint for code system (CPT, HCPCS, ICD10CM, ICD10PCS, NDC)
            jurisdiction: Filter policies by MAC jurisdiction code
            include: Additional data to include (rvu, policies)
            fuzzy: Enable fuzzy matching on miss
        
        Returns:
            Code information including description, policies, and optionally RVU data.
        
        Example:
            >>> result = client.lookup_code("76942", include=["rvu", "policies"])
            >>> print(result["data"]["description"])
        """
        params = {"code": code, "fuzzy": str(fuzzy).lower()}
        
        if code_system:
            params["code_system"] = code_system
        if jurisdiction:
            params["jurisdiction"] = jurisdiction
        if include:
            params["include"] = ",".join(include)
        
        return self._request("GET", "/codes/lookup", params=params)

    # Policy Search
    def list_policies(
        self,
        q: Optional[str] = None,
        mode: str = "keyword",
        policy_type: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        payer: Optional[str] = None,
        status: str = "active",
        cursor: Optional[str] = None,
        limit: int = 50,
        include: Optional[List[str]] = None,
        icd10: Optional[str] = None,
        format: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search and list policies.

        Args:
            q: Search query (max 500 characters)
            mode: Search mode (keyword or semantic)
            policy_type: Filter by policy type (LCD, Article, NCD, etc.)
            jurisdiction: Filter by MAC jurisdiction code
            payer: Filter by payer name
            status: Filter by status (active, retired, all)
            cursor: Pagination cursor
            limit: Results per page (1-100)
            include: Additional data (summary, criteria, codes)
            icd10: Filter by ICD-10 diagnosis code
            format: Response format

        Returns:
            List of policies with pagination metadata.
        """
        params = {"mode": mode, "status": status, "limit": limit}

        if q:
            params["q"] = q
        if policy_type:
            params["policy_type"] = policy_type
        if jurisdiction:
            params["jurisdiction"] = jurisdiction
        if payer:
            params["payer"] = payer
        if cursor:
            params["cursor"] = cursor
        if include:
            params["include"] = ",".join(include)
        if icd10:
            params["icd10"] = icd10
        if format:
            params["format"] = format

        return self._request("GET", "/policies", params=params)

    # Get Policy by ID
    def get_policy(
        self,
        policy_id: str,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get a single policy by ID.
        
        Args:
            policy_id: Policy ID (e.g., L33831)
            include: Additional data (criteria, codes, attachments, versions)
        
        Returns:
            Policy details with optional related data.
        
        Example:
            >>> policy = client.get_policy("L33831", include=["criteria", "codes"])
        """
        params = {}
        if include:
            params["include"] = ",".join(include)
        
        return self._request("GET", f"/policies/{policy_id}", params=params)

    # Compare Policies
    def compare_policies(
        self,
        procedure_codes: List[str],
        policy_type: Optional[str] = None,
        jurisdictions: Optional[List[str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compare policies across jurisdictions.
        
        Args:
            procedure_codes: Array of CPT/HCPCS codes to compare (max 10)
            policy_type: Filter by policy type (LCD, Article, NCD)
            jurisdictions: Specific jurisdictions to compare (all if omitted, max 10)
            idempotency_key: Unique request identifier for safe retries
        
        Returns:
            Comparison across jurisdictions with national policies.
        """
        headers = {}
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        
        body = {"procedure_codes": procedure_codes}
        if policy_type:
            body["policy_type"] = policy_type
        if jurisdictions:
            body["jurisdictions"] = jurisdictions
        
        return self._request("POST", "/policies/compare", json=body, headers=headers)

    # Policy Changes
    def get_policy_changes(
        self,
        since: Optional[str] = None,
        policy_id: Optional[str] = None,
        change_type: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Get policy change feed.
        
        Args:
            since: ISO8601 timestamp - only show changes after this date
            policy_id: Filter to a specific policy
            change_type: Filter by change type (created, updated, retired, etc.)
            cursor: Pagination cursor
            limit: Results per page (1-100)
        
        Returns:
            List of policy changes with pagination.
        """
        params = {"limit": limit}
        
        if since:
            params["since"] = since
        if policy_id:
            params["policy_id"] = policy_id
        if change_type:
            params["change_type"] = change_type
        if cursor:
            params["cursor"] = cursor
        
        return self._request("GET", "/policies/changes", params=params)

    # Coverage Criteria Search
    def search_criteria(
        self,
        q: str,
        section: Optional[str] = None,
        policy_type: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Search coverage criteria.
        
        Args:
            q: Search query for criteria text (max 500 characters)
            section: Filter by section (indications, limitations, documentation, etc.)
            policy_type: Filter by policy type (LCD, Article, NCD, PayerPolicy)
            jurisdiction: Filter by MAC jurisdiction
            cursor: Pagination cursor
            limit: Results per page (1-100)
        
        Returns:
            Matching criteria blocks with policy context.
        """
        params = {"q": q, "limit": limit}
        
        if section:
            params["section"] = section
        if policy_type:
            params["policy_type"] = policy_type
        if jurisdiction:
            params["jurisdiction"] = jurisdiction
        if cursor:
            params["cursor"] = cursor
        
        return self._request("GET", "/coverage/criteria", params=params)

    # Jurisdictions
    def list_jurisdictions(self) -> Dict[str, Any]:
        """List MAC jurisdictions.
        
        Returns:
            List of Medicare Administrative Contractor jurisdictions.
        """
        return self._request("GET", "/jurisdictions")

    # Prior Authorization Check
    def check_prior_auth(
        self,
        procedure_codes: List[str],
        diagnosis_codes: Optional[List[str]] = None,
        state: Optional[str] = None,
        payer: str = "medicare",
        criteria_page: int = 1,
        criteria_per_page: int = 25,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Check prior authorization requirements.
        
        Args:
            procedure_codes: CPT/HCPCS codes to check (max 10)
            diagnosis_codes: ICD-10 diagnosis codes for context (max 10)
            state: Two-letter state code (determines MAC jurisdiction)
            payer: Payer to check (medicare, aetna, uhc, all)
            criteria_page: Page number for criteria results
            criteria_per_page: Criteria items per page (1-100)
            idempotency_key: Unique request identifier for safe retries
        
        Returns:
            Prior auth determination with matched policies and criteria.
        
        Example:
            >>> result = client.check_prior_auth(
            ...     procedure_codes=["76942"],
            ...     diagnosis_codes=["M54.5"],
            ...     state="TX"
            ... )
            >>> print(result["data"]["pa_required"])
        """
        headers = {}
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        
        body = {
            "procedure_codes": procedure_codes,
            "payer": payer,
            "criteria_page": criteria_page,
            "criteria_per_page": criteria_per_page,
        }
        
        if diagnosis_codes:
            body["diagnosis_codes"] = diagnosis_codes
        if state:
            body["state"] = state
        
        return self._request("POST", "/prior-auth/check", json=body, headers=headers)

    # Claim Validation
    def validate_claim(
        self,
        procedure_codes: List[str],
        payer: Optional[str] = None,
        plan_type: Optional[str] = None,
        line_of_business: Optional[str] = None,
        diagnosis_codes: Optional[List[str]] = None,
        modifiers: Optional[List[str]] = None,
        state: Optional[str] = None,
        site_of_service: Optional[str] = None,
        provider_specialty: Optional[str] = None,
        age_category: Optional[str] = None,
        sex_when_policy_relevant: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        date_of_service: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate a claim for coverage and denial risk.

        This calls the current `/claims/validate` endpoint.
        Responses include aggregate `issues`, policy-only `matched_policies`,
        and all source references in `policy_sources`.
        """
        return self._validate_claim_request(
            "/claims/validate",
            procedure_codes=procedure_codes,
            payer=payer,
            plan_type=plan_type,
            line_of_business=line_of_business,
            diagnosis_codes=diagnosis_codes,
            modifiers=modifiers,
            state=state,
            date_of_service=date_of_service,
            site_of_service=site_of_service,
            provider_specialty=provider_specialty,
            age_category=age_category,
            sex_when_policy_relevant=sex_when_policy_relevant,
            idempotency_key=idempotency_key,
        )

    def validate_claim_legacy(
        self,
        procedure_codes: List[str],
        payer: Optional[str] = None,
        plan_type: Optional[str] = None,
        line_of_business: Optional[str] = None,
        diagnosis_codes: Optional[List[str]] = None,
        modifiers: Optional[List[str]] = None,
        state: Optional[str] = None,
        site_of_service: Optional[str] = None,
        provider_specialty: Optional[str] = None,
        age_category: Optional[str] = None,
        sex_when_policy_relevant: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        date_of_service: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate a claim through the deprecated `/claim-validation` endpoint."""
        return self._validate_claim_request(
            "/claim-validation",
            procedure_codes=procedure_codes,
            payer=payer,
            plan_type=plan_type,
            line_of_business=line_of_business,
            diagnosis_codes=diagnosis_codes,
            modifiers=modifiers,
            state=state,
            date_of_service=date_of_service,
            site_of_service=site_of_service,
            provider_specialty=provider_specialty,
            age_category=age_category,
            sex_when_policy_relevant=sex_when_policy_relevant,
            idempotency_key=idempotency_key,
        )

    def _validate_claim_request(
        self,
        path: str,
        procedure_codes: List[str],
        payer: Optional[str] = None,
        plan_type: Optional[str] = None,
        line_of_business: Optional[str] = None,
        diagnosis_codes: Optional[List[str]] = None,
        modifiers: Optional[List[str]] = None,
        state: Optional[str] = None,
        site_of_service: Optional[str] = None,
        provider_specialty: Optional[str] = None,
        age_category: Optional[str] = None,
        sex_when_policy_relevant: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        date_of_service: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"procedure_codes": procedure_codes}
        optional_fields = {
            "payer": payer,
            "plan_type": plan_type,
            "line_of_business": line_of_business,
            "diagnosis_codes": diagnosis_codes,
            "modifiers": modifiers,
            "state": state,
            "date_of_service": date_of_service,
            "site_of_service": site_of_service,
            "provider_specialty": provider_specialty,
            "age_category": age_category,
            "sex_when_policy_relevant": sex_when_policy_relevant,
        }
        body.update({key: value for key, value in optional_fields.items() if value is not None})

        headers = {}
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key

        return self._request("POST", path, json=body, headers=headers)

    # Prior Authorization Research
    def research_prior_auth(
        self,
        procedure_codes: List[str],
        payer: Optional[str] = None,
        state: Optional[str] = None,
        diagnosis_codes: Optional[List[str]] = None,
        clinical_context: Optional[str] = None,
        sync: bool = False,
    ) -> Dict[str, Any]:
        """Research prior authorization requirements using AI-powered web research.

        Uses web research to find prior auth requirements directly from payer websites.
        By default runs asynchronously - returns a research_id for polling with
        get_prior_auth_research(). Set sync=True to wait for completion.

        Args:
            procedure_codes: CPT/HCPCS codes to research (max 10)
            payer: Specific payer name (e.g., "UnitedHealthcare", "Aetna")
            state: Two-letter state code for jurisdiction-specific policies
            diagnosis_codes: ICD-10 diagnosis codes for clinical context
            clinical_context: Additional clinical notes (max 2000 chars)
            sync: If True, wait for completion (default: False)

        Returns:
            Research task info with research_id (async) or full results (sync).

        Example:
            >>> result = client.research_prior_auth(
            ...     procedure_codes=["27447"],
            ...     payer="UnitedHealthcare",
            ...     state="TX",
            ...     sync=True
            ... )
            >>> print(result["data"]["result"]["determination"])
        """
        body: Dict[str, Any] = {
            "procedure_codes": procedure_codes,
            "sync": sync,
        }

        if payer:
            body["payer"] = payer
        if state:
            body["state"] = state
        if diagnosis_codes:
            body["diagnosis_codes"] = diagnosis_codes
        if clinical_context:
            body["clinical_context"] = clinical_context

        return self._request("POST", "/prior-auth/research", json=body)

    def get_prior_auth_research(
        self,
        research_id: str,
    ) -> Dict[str, Any]:
        """Get the status and results of a prior authorization research task.

        Poll this endpoint until status is "completed" or "failed".

        Args:
            research_id: Research task ID from research_prior_auth()

        Returns:
            Research status and results when completed.

        Example:
            >>> result = client.get_prior_auth_research("res_abc123")
            >>> if result["data"]["status"] == "completed":
            ...     print(result["data"]["result"])
        """
        return self._request("GET", f"/prior-auth/research/{research_id}")

    # Spending
    def get_spending_by_code(
        self,
        code: Optional[str] = None,
        codes: Optional[List[str]] = None,
        year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get Medicaid spending data by HCPCS code.

        Returns aggregate Medicaid provider spending statistics per HCPCS code,
        including totals and year-over-year breakdowns from CMS claims data.

        Args:
            code: Single HCPCS code to look up
            codes: Multiple HCPCS codes (comma-separated, max 10)
            year: Filter to a specific year

        Returns:
            Spending data keyed by code with totals and yearly breakdowns.

        Example:
            >>> result = client.get_spending_by_code(code="T1019")
            >>> print(result["data"]["T1019"]["total_paid"])
        """
        params: Dict[str, Any] = {}

        if code:
            params["code"] = code
        elif codes:
            params["codes"] = ",".join(codes)

        if year:
            params["year"] = year

        return self._request("GET", "/spending/by-code", params=params)

    # Batch Code Lookup
    def batch_lookup_codes(
        self,
        codes: List[str],
        code_system: Optional[str] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Look up multiple medical codes in a single request (max 50).

        Args:
            codes: List of medical codes to look up (max 50)
            code_system: Hint for code system (CPT, HCPCS, ICD10CM, ICD10PCS, NDC)
            include: Additional data to include (rvu, policies)

        Returns:
            Batch lookup results keyed by code.

        Example:
            >>> result = client.batch_lookup_codes(["76942", "99213"])
            >>> for code_data in result["data"]:
            ...     print(code_data["description"])
        """
        body: Dict[str, Any] = {"codes": codes}

        if code_system:
            body["code_system"] = code_system
        if include:
            body["include"] = ",".join(include)

        return self._request("POST", "/codes/batch", json=body)

    # Coverage Evaluation
    def evaluate_coverage(
        self,
        policy_id: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Evaluate a policy's coverage criteria against patient/claim parameters. Requires Professional plan.

        Args:
            policy_id: Policy ID to evaluate against (e.g., L33831)
            parameters: Patient/claim parameters to evaluate

        Returns:
            Coverage evaluation result with determination.

        Example:
            >>> result = client.evaluate_coverage("L33831", {"diagnosis": "M54.5"})
            >>> print(result["data"]["determination"])
        """
        return self._request("POST", "/coverage/evaluate", json={"policy_id": policy_id, "parameters": parameters})

    # Webhooks
    def list_webhooks(self) -> Dict[str, Any]:
        """List all webhook endpoints for your organization. Requires Enterprise plan.

        Returns:
            List of webhook endpoints with their configuration.
        """
        return self._request("GET", "/webhooks")

    def create_webhook(
        self,
        url: str,
        events: List[str],
    ) -> Dict[str, Any]:
        """Create a new webhook endpoint. URL must use HTTPS. Requires Enterprise plan.

        Args:
            url: HTTPS URL to receive webhook events
            events: List of event types to subscribe to

        Returns:
            Created webhook endpoint details.

        Example:
            >>> webhook = client.create_webhook(
            ...     url="https://example.com/webhooks/backwork",
            ...     events=["policy.updated", "policy.created"]
            ... )
            >>> print(webhook["data"]["id"])
        """
        return self._request("POST", "/webhooks", json={"url": url, "events": events})

    def update_webhook(
        self,
        webhook_id: int,
        url: Optional[str] = None,
        events: Optional[List[str]] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a webhook endpoint's URL, events, or status.

        Args:
            webhook_id: ID of the webhook to update
            url: New HTTPS URL for the webhook
            events: New list of event types
            status: New status (active, paused)

        Returns:
            Updated webhook endpoint details.
        """
        body: Dict[str, Any] = {}

        if url is not None:
            body["url"] = url
        if events is not None:
            body["events"] = events
        if status is not None:
            body["status"] = status

        return self._request("PATCH", f"/webhooks/{webhook_id}", json=body)

    def delete_webhook(self, webhook_id: int) -> Dict[str, Any]:
        """Delete (soft-delete) a webhook endpoint.

        Args:
            webhook_id: ID of the webhook to delete

        Returns:
            Deletion confirmation.
        """
        return self._request("DELETE", f"/webhooks/{webhook_id}")

    def test_webhook(self, webhook_id: int) -> Dict[str, Any]:
        """Send a test event to a webhook endpoint.

        Args:
            webhook_id: ID of the webhook to test

        Returns:
            Test event delivery result.
        """
        return self._request("POST", f"/webhooks/{webhook_id}/test")

    # Compliance
    def list_unreviewed_changes(
        self,
        change_type: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List unreviewed policy changes for the authenticated organization."""
        params: Dict[str, Any] = {"limit": limit}
        if change_type:
            params["change_type"] = change_type
        if cursor:
            params["cursor"] = cursor

        return self._request("GET", "/compliance/unreviewed", params=params)

    def acknowledge_change(
        self,
        diff_id: int,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Acknowledge a single policy change."""
        body: Dict[str, Any] = {"diff_id": diff_id}
        if notes is not None:
            body["notes"] = notes

        return self._request("POST", "/compliance/ack", json=body)

    def bulk_acknowledge_changes(
        self,
        diff_ids: List[int],
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Acknowledge multiple policy changes."""
        body: Dict[str, Any] = {"diff_ids": diff_ids}
        if notes is not None:
            body["notes"] = notes

        return self._request("POST", "/compliance/ack/bulk", json=body)

    def get_compliance_stats(self) -> Dict[str, Any]:
        """Get compliance dashboard statistics."""
        return self._request("GET", "/compliance/stats")

    # Drugs
    def search_drug_formulary_evidence(
        self,
        q: str,
        payer: str = "all",
        limit: int = 25,
    ) -> Dict[str, Any]:
        """Search commercial pharmacy-benefit formulary evidence."""
        params = {"q": q, "payer": payer, "limit": limit}
        return self._request("GET", "/drugs/formulary", params=params)
