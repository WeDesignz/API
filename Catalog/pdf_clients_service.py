from math import ceil
from typing import Dict, List, Tuple

from django.db.models import QuerySet

from Catalog.models import PDFClient, Product
from common.business_config import BusinessConfig


def _get_allowed_designs_per_pdf() -> List[int]:
    """
    Return allowed designs-per-PDF options for admin client PDFs.
    The global configuration already restricts values to <= 100.
    """
    options = BusinessConfig.get_paid_pdf_designs_options()
    # Ensure deterministic ordering and uniqueness
    unique_sorted = sorted({int(x) for x in options if int(x) > 0})
    return unique_sorted or [20, 50, 100]


def normalize_designs_per_pdf(designs_per_pdf: int) -> int:
    """
    Clamp designs_per_pdf to the nearest allowed option (20, 50, 100 by config).
    Admin UI will send 100, but this guards against misconfiguration.
    """
    allowed = _get_allowed_designs_per_pdf()
    if designs_per_pdf in allowed:
        return designs_per_pdf
    # Pick the smallest allowed that is >= requested, or the largest if all smaller
    greater_or_equal = [x for x in allowed if x >= designs_per_pdf]
    if greater_or_equal:
        return greater_or_equal[0]
    return allowed[-1]


def get_available_products_qs(client: PDFClient) -> QuerySet:
    """
    Base queryset of products that can be used for a PDF client.
    Excludes any product IDs that were already used for this client.
    """
    used_ids = client.used_product_ids or []
    used_ids_int = [int(pk) for pk in used_ids if isinstance(pk, (int, float, str)) and str(pk).strip()]
    qs = Product.objects.filter(
        status="active",
        visibility_status="show",
    ).exclude(product_number__isnull=True).exclude(product_number="").order_by("id")
    if used_ids_int:
        qs = qs.exclude(id__in=used_ids_int)
    return qs


def select_products_for_client_pdfs(
    client: PDFClient,
    designs_per_pdf: int,
    requested_pdfs: int,
    max_pdfs_per_job: int = 10,
) -> Dict[str, object]:
    """
    Select non-overlapping products for a PDF client job.

    Returns a dict with:
      - designs_per_pdf: normalized designs-per-PDF value
      - requested_pdfs: requested count (input)
      - actual_pdfs: number of PDFs that can be generated (may be less than requested)
      - included_product_ids_by_pdf: list of product-id lists, one per PDF
      - total_designs_available: number of candidate designs before slicing
      - total_designs_used: total number of product IDs assigned across all PDFs
    """
    normalized_dpp = normalize_designs_per_pdf(designs_per_pdf)
    requested = max(1, int(requested_pdfs))
    requested = min(requested, max_pdfs_per_job)

    base_qs = get_available_products_qs(client)
    # Materialize IDs once to preserve ordering and allow simple chunking
    available_ids: List[int] = list(base_qs.values_list("id", flat=True))
    total_available = len(available_ids)
    if total_available == 0:
        return {
            "designs_per_pdf": normalized_dpp,
            "requested_pdfs": requested,
            "actual_pdfs": 0,
            "included_product_ids_by_pdf": [],
            "total_designs_available": 0,
            "total_designs_used": 0,
        }

    max_possible_pdfs = ceil(total_available / float(normalized_dpp))
    actual_pdfs = min(requested, max_possible_pdfs, max_pdfs_per_job)
    included_product_ids_by_pdf: List[List[int]] = []

    start_index = 0
    for _ in range(actual_pdfs):
        end_index = start_index + normalized_dpp
        chunk = available_ids[start_index:end_index]
        if not chunk:
            break
        included_product_ids_by_pdf.append(chunk)
        start_index = end_index

    total_used = sum(len(chunk) for chunk in included_product_ids_by_pdf)

    return {
        "designs_per_pdf": normalized_dpp,
        "requested_pdfs": requested,
        "actual_pdfs": len(included_product_ids_by_pdf),
        "included_product_ids_by_pdf": included_product_ids_by_pdf,
        "total_designs_available": total_available,
        "total_designs_used": total_used,
    }

