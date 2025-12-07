"""
Invoice Service
---------------
Service for generating invoices for customers and designers.
Handles PDF generation, financial calculations, and wallet settlements.
"""

import os
from decimal import Decimal
from typing import Dict, Any, List
from datetime import date, datetime
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

try:
    from PIL import Image
except ImportError:
    Image = None

from Orders.models import Order, Invoice
from Catalog.models import Product
from Wallet.models import Wallet, WalletTransaction
from Plans.models import Subscription
from common.business_config import BusinessConfig


def extract_gst_and_commission(total_price: Decimal, gst_percentage: Decimal, commission_rate: Decimal) -> Dict[str, Decimal]:
    """
    Extract GST and commission from total price using reverse calculation.
    
    Formula:
    - Step 1: Extract GST: x + (gst% * x) = total_price
              x = total_price / (1 + gst_percentage/100)
              gst_amount = total_price - x
    
    - Step 2: Extract Commission: y + (commission% * y) = x
              y = x / (1 + commission_rate/100)
              commission_amount = x - y
    
    Returns:
        Dict with:
        - base_amount: Amount to be distributed (y)
        - gst_amount: GST amount
        - commission_amount: Commission amount
        - amount_after_gst: Amount after GST extraction (x)
    
    Example:
        total_price = 100, gst = 18%, commission = 30%
        x = 100 / 1.18 = 84.75
        gst = 100 - 84.75 = 15.25
        y = 84.75 / 1.3 = 65.2
        commission = 84.75 - 65.2 = 19.55
        base = 65.2
    """
    # Step 1: Extract GST
    # x + (gst% * x) = total_price
    # x * (1 + gst_percentage/100) = total_price
    # x = total_price / (1 + gst_percentage/100)
    amount_after_gst = total_price / (Decimal('1') + (gst_percentage / Decimal('100')))
    gst_amount = total_price - amount_after_gst
    
    # Step 2: Extract Commission from amount_after_gst
    # y + (commission% * y) = amount_after_gst
    # y * (1 + commission_rate/100) = amount_after_gst
    # y = amount_after_gst / (1 + commission_rate/100)
    base_amount = amount_after_gst / (Decimal('1') + (commission_rate / Decimal('100')))
    commission_amount = amount_after_gst - base_amount
    
    return {
        'base_amount': base_amount,
        'gst_amount': gst_amount,
        'commission_amount': commission_amount,
        'amount_after_gst': amount_after_gst,
    }


def calculate_order_breakdown(order: Order) -> Dict[str, Any]:
    """
    Calculate financial breakdown for an order.
    Each designer's GST and commission are calculated independently on their portion.
    
    Returns:
        Dict with:
        - total_amount: Total order amount
        - gst_amount: Total GST (sum of all designers)
        - base_amount: Amount before GST
        - designer_breakdown: Dict mapping designer_id to their earnings breakdown
    """
    total_amount = Decimal(str(order.total_amount))
    gst_percentage = Decimal(str(BusinessConfig.get_gst_percentage()))
    commission_rate = Decimal(str(BusinessConfig.get_commission_rate()))
    
    # Group products by designer
    designer_breakdown = {}
    
    if order.product_ids:
        product_ids = [int(pid.strip()) for pid in order.product_ids.split(',') if pid.strip()]
        products = Product.objects.filter(id__in=product_ids)
        
        for product in products:
            designer_id = product.created_by.id
            
            if designer_id not in designer_breakdown:
                designer_breakdown[designer_id] = {
                    'designer': product.created_by,
                    'products': [],
                    'product_total': Decimal('0'),
                    'gst_amount': Decimal('0'),
                    'commission_amount': Decimal('0'),
                    'wallet_amount': Decimal('0'),
                }
            
            product_price = Decimal(str(product.price or 0))
            designer_breakdown[designer_id]['products'].append(product)
            designer_breakdown[designer_id]['product_total'] += product_price
        
        # Calculate GST and commission INDEPENDENTLY for each designer using reverse calculation
        for designer_id, breakdown in designer_breakdown.items():
            designer_total = breakdown['product_total']  # This is the total price including GST and commission
            
            # Extract GST and commission from designer_total (reverse calculation)
            extracted = extract_gst_and_commission(designer_total, gst_percentage, commission_rate)
            
            breakdown['gst_amount'] = extracted['gst_amount']
            breakdown['commission_amount'] = extracted['commission_amount']
            breakdown['wallet_amount'] = extracted['base_amount']  # Base amount goes to wallet
    
    # Total GST and commission for customer invoice
    total_gst = sum(b['gst_amount'] for b in designer_breakdown.values())
    total_commission = sum(b['commission_amount'] for b in designer_breakdown.values())
    
    # Calculate total base amount (sum of all designer base amounts)
    base_amount = sum(b['wallet_amount'] for b in designer_breakdown.values())
    
    return {
        'total_amount': total_amount,
        'gst_amount': total_gst,
        'base_amount': base_amount,
        'designer_breakdown': designer_breakdown,
    }


def _draw_logo_and_company(c: canvas.Canvas, data: Dict[str, Any], page_width: float, top_y: float) -> float:
    """Draw WeDesignz logo and text on the left side of the header."""
    company = data["company_details"]
    logo_path = company.get("logo", "")
    text_logo_path = company.get("text_logo", "")
    
    logo_x = 25 * mm
    logo_size = 6 * mm  # Reduced to 6mm for better fit
    logo_width = logo_size
    logo_drawn = False
    text_logo_drawn = False
    
    # Draw logo image
    if logo_path and Image:
        try:
            if not os.path.isabs(logo_path):
                if os.path.exists(logo_path):
                    full_path = logo_path
                else:
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    full_path = os.path.join(script_dir, logo_path)
            else:
                full_path = logo_path
            
            if os.path.exists(full_path):
                img = Image.open(full_path)
                img_width, img_height = img.size
                aspect_ratio = img_width / img_height
                logo_width = logo_size * aspect_ratio
                c.drawImage(full_path, logo_x, top_y - logo_size, width=logo_width, height=logo_size, preserveAspectRatio=True)
                logo_drawn = True
        except Exception as e:
            print(f"Warning: Could not load logo image '{logo_path}': {e}")
    
    # If logo not drawn, draw placeholder
    if not logo_drawn:
        circle_radius = 3 * mm  # Reduced to 3mm
        circle_x = 30 * mm
        circle_y = top_y - circle_radius
        c.setFillColorRGB(0.80, 0.89, 0.96)
        c.setStrokeColor(colors.white)
        c.circle(circle_x, circle_y, circle_radius, stroke=0, fill=1)
        logo_text = company.get("company_name", "")
        initial = (logo_text[:1] or "A").upper()
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 7)  # Reduced to 7
        c.drawCentredString(circle_x, circle_y - 2, initial)
        logo_x = circle_x
        logo_width = circle_radius * 2
    
    # Draw text logo next to the logo
    text_logo_x = logo_x + logo_width + 2 * mm  # Reduced gap to 2mm
    text_logo_size = 5 * mm  # Reduced to 5mm
    
    if text_logo_path and Image:
        try:
            if not os.path.isabs(text_logo_path):
                if os.path.exists(text_logo_path):
                    full_text_path = text_logo_path
                else:
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    full_text_path = os.path.join(script_dir, text_logo_path)
            else:
                full_text_path = text_logo_path
            
            if os.path.exists(full_text_path):
                text_img = Image.open(full_text_path)
                text_img_width, text_img_height = text_img.size
                text_aspect_ratio = text_img_width / text_img_height
                text_logo_width = text_logo_size * text_aspect_ratio
                # Center text logo vertically with main logo
                text_logo_y_offset = (logo_size - text_logo_size) / 2
                c.drawImage(full_text_path, text_logo_x, top_y - logo_size + text_logo_y_offset, 
                           width=text_logo_width, height=text_logo_size, preserveAspectRatio=True)
                text_logo_drawn = True
        except Exception as e:
            print(f"Warning: Could not load text logo image '{text_logo_path}': {e}")
    
    # If text logo not drawn, draw company name as text
    if not text_logo_drawn:
        text_x = logo_x + logo_width + 8 * mm
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 16)  # Larger font for better visibility
        c.drawString(text_x, top_y - 6 * mm, company.get("company_name", "WeDesignz"))

    return top_y - 12 * mm  # Reduced to 12mm for smaller logos


def _draw_invoice_meta(c: canvas.Canvas, data: Dict[str, Any], page_width: float, top_y: float) -> float:
    """Draw invoice metadata on the right side of the header."""
    inv = data["invoice"]
    invoice_type = data.get("invoice_type", "customer")  # Get invoice type from data
    right_margin = 25 * mm
    col_x = page_width - right_margin
    
    # Use "BILL" for designer, "INVOICE" for customer
    document_title = "BILL" if invoice_type == "designer" else "INVOICE"
    
    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(colors.black)
    c.drawRightString(col_x, top_y - 5 * mm, document_title)

    # Calculate positions: labels on left, values on right with proper spacing
    # We'll use a fixed label start position and ensure values align to the right
    label_start_x = col_x - 80 * mm  # Start labels 80mm from right edge
    value_x = col_x  # Values align to right margin
    
    c.setFont("Helvetica", 9)
    meta_y = top_y - 15 * mm
    c.setFillColor(colors.black)
    
    # Invoice Number: label on left, value on right with proper spacing
    label_text = "Invoice Number:"
    c.setFont("Helvetica", 9)
    c.drawString(label_start_x, meta_y, label_text)
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(value_x, meta_y, f"{inv.get('invoice_number', '')}")
    
    # Order Number: label on left, value on right (only for customer invoices)
    if invoice_type != "designer":  # Hide Order Number for designer bills
        meta_y -= 6 * mm
        c.setFont("Helvetica", 9)
        c.drawString(label_start_x, meta_y, "Order Number:")
        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(value_x, meta_y, f"{inv.get('order_number', '')}")
    
    # Invoice Date: label on left, value on right
    meta_y -= 6 * mm
    c.setFont("Helvetica", 9)
    c.drawString(label_start_x, meta_y, "Invoice Date:")
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(value_x, meta_y, f"{inv.get('invoice_date', '')}")

    return top_y - 30 * mm  # Adjusted for 3 rows


def _draw_company_contact(c: canvas.Canvas, data: Dict[str, Any], page_width: float, y: float) -> float:
    """Draw company contact info in an attractive footer."""
    company = data["company_details"]
    
    # Draw a subtle line separator
    left_margin = 25 * mm
    right_margin = 25 * mm
    line_y = y + 8 * mm
    
    c.setStrokeColorRGB(0.85, 0.85, 0.85)
    c.setLineWidth(0.5)
    c.line(left_margin, line_y, page_width - right_margin, line_y)
    
    # Footer content with better styling
    footer_y = y
    
    # Left side: Contact Email ID
    c.setFont("Helvetica-Bold", 8)
    c.setFillColorRGB(0.22, 0.55, 0.80)
    c.drawString(left_margin, footer_y, "Contact Email ID:")
    
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.black)
    email = company.get('company_email', 'info@wedesignz.com')
    c.drawString(left_margin, footer_y - 4 * mm, email)
    
    # Right side: Support Link
    support_link = company.get('company_support_link', 'https://support.wedesignz.com')
    c.setFont("Helvetica-Bold", 8)
    c.setFillColorRGB(0.22, 0.55, 0.80)
    c.drawRightString(page_width - right_margin, footer_y, "Support Link:")
    
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.black)
    c.drawRightString(page_width - right_margin, footer_y - 4 * mm, support_link)
    
    return footer_y - 8 * mm


def _draw_billed_and_from_blocks(c: canvas.Canvas, data: Dict[str, Any], page_width: float, start_y: float) -> float:
    """Draw billed to and from blocks with proper text wrapping."""
    billed = data["billed_to"]
    sender = data["from_details"]
    company = data.get("company_details", {})

    left_margin = 25 * mm
    right_margin = 25 * mm
    mid_x = page_width / 2
    
    # Column width for each section (to prevent overlap)
    col_width = (mid_x - left_margin - 5 * mm)  # Leave 5mm gap between columns

    # BILLED TO section
    c.setFont("Helvetica-Bold", 9)
    c.setFillColorRGB(0.22, 0.55, 0.80)
    c.drawString(left_margin, start_y, "BILLED TO")

    c.setFont("Helvetica", 9)
    c.setFillColor(colors.black)
    text_y = start_y - 5 * mm
    
    # Company/Individual Name (with wrapping)
    company_name = billed.get("client_company", "")
    wrapped_lines = _wrap_text(company_name, col_width, c, "Helvetica", 9)
    for line in wrapped_lines:
        c.drawString(left_margin, text_y, line)
        text_y -= 4 * mm
    
    # Address Line 1 (with wrapping)
    if billed.get("client_address_line1"):
        addr1 = billed.get("client_address_line1", "")
        wrapped_lines = _wrap_text(addr1, col_width, c, "Helvetica", 9)
        for line in wrapped_lines:
            c.drawString(left_margin, text_y, line)
            text_y -= 4 * mm
    
    # Address Line 2 (with wrapping)
    if billed.get("client_address_line2"):
        addr2 = billed.get("client_address_line2", "")
        wrapped_lines = _wrap_text(addr2, col_width, c, "Helvetica", 9)
        for line in wrapped_lines:
            c.drawString(left_margin, text_y, line)
            text_y -= 4 * mm
    
    # GST Number (if available)
    if billed.get("client_gst_number"):
        c.setFont("Helvetica", 8)
        c.drawString(left_margin, text_y, f"GSTIN: {billed.get('client_gst_number')}")
        text_y -= 4 * mm

    # FROM section (WeDesignz fixed address)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColorRGB(0.22, 0.55, 0.80)
    c.drawString(mid_x + 5 * mm, start_y, "FROM")

    c.setFont("Helvetica", 9)
    c.setFillColor(colors.black)
    from_y = start_y - 5 * mm
    
    # WeDesignz Company Name
    sender_name = sender.get("sender_name", "WeDesignz")
    wrapped_lines = _wrap_text(sender_name, col_width, c, "Helvetica", 9)
    for line in wrapped_lines:
        c.drawString(mid_x + 5 * mm, from_y, line)
        from_y -= 4 * mm
    
    # WeDesignz Address Line 1 (with wrapping)
    if sender.get("sender_address_line1"):
        addr1 = sender.get("sender_address_line1", "")
        wrapped_lines = _wrap_text(addr1, col_width, c, "Helvetica", 9)
        for line in wrapped_lines:
            c.drawString(mid_x + 5 * mm, from_y, line)
            from_y -= 4 * mm
    
    # WeDesignz Address Line 2 (with wrapping)
    if sender.get("sender_address_line2"):
        addr2 = sender.get("sender_address_line2", "")
        wrapped_lines = _wrap_text(addr2, col_width, c, "Helvetica", 9)
        for line in wrapped_lines:
            c.drawString(mid_x + 5 * mm, from_y, line)
            from_y -= 4 * mm
    
    # WeDesignz GST Number
    sender_gst = sender.get("sender_gst_number", "")
    if sender_gst:
        c.setFont("Helvetica", 8)
        c.drawString(mid_x + 5 * mm, from_y, f"GSTIN: {sender_gst}")

    # Calculate the lowest point used
    lowest_y = min(text_y, from_y - 4 * mm)
    return lowest_y - 4 * mm


def _wrap_text(text: str, max_width: float, c: canvas.Canvas, font_name: str, font_size: int) -> List[str]:
    """Wrap text to fit within max_width using canvas stringWidth."""
    if not text:
        return [""]
    
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = " ".join(current_line + [word])
        width = c.stringWidth(test_line, font_name, font_size)
        
        if width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(" ".join(current_line))
    
    return lines if lines else [text]


def _draw_items_table(c: canvas.Canvas, data: Dict[str, Any], page_width: float, start_y: float) -> float:
    """Draw items table with header row and borders."""
    items: List[Dict[str, Any]] = data.get("items", [])

    left_margin = 25 * mm
    right_margin = 25 * mm
    table_width = page_width - left_margin - right_margin

    col_widths = [
        0.10 * table_width,
        0.40 * table_width,
        0.10 * table_width,
        0.20 * table_width,
        0.20 * table_width,
    ]

    header_height = 12 * mm
    row_height = 12 * mm

    c.setFillColorRGB(0.80, 0.89, 0.96)
    c.rect(left_margin, start_y - header_height, table_width, header_height, stroke=0, fill=1)

    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.black)

    headers = ["ITEM", "DESCRIPTION", "QTY", "RATE", "AMOUNT"]
    x = left_margin + 2 * mm
    y_text = start_y - header_height + 3 * mm

    # Draw headers with proper alignment
    for i, title in enumerate(headers):
        if i in [2, 3, 4]:  # QTY, RATE, AMOUNT - center or right align
            # Center align headers for QTY, RATE, AMOUNT
            col_center_x = x + col_widths[i] / 2
            c.drawCentredString(col_center_x, y_text, title)
        else:  # ITEM, DESCRIPTION - left align
            c.drawString(x, y_text, title)
        x += col_widths[i]

    c.setFont("Helvetica", 8)
    current_y = start_y - header_height

    # Draw all items (should be 2: Individual Design + GST)
    for row_index, item in enumerate(items):
        current_y -= row_height

        # Alternate row colors
        if row_index % 2 == 0:
            c.setFillColorRGB(0.96, 0.96, 0.96)
            c.rect(left_margin, current_y, table_width, row_height, stroke=0, fill=1)

        c.setFillColor(colors.black)
        x = left_margin + 2 * mm
        
        # Item number
        c.drawString(x, current_y + 4 * mm, str(item.get("item_no", "")))
        x += col_widths[0]

        # Description
        c.drawString(x, current_y + 4 * mm, str(item.get("description", "")))
        x += col_widths[1]

        # Quantity (center aligned, show actual count for GST and Commission rows)
        qty = item.get("quantity", "")
        description = item.get("description", "")
        if qty == "-":
            qty_display = "-"
        else:
            # Show actual quantity (number of designs)
            qty_display = str(qty) if qty else "-"
        col_center_x = x + col_widths[2] / 2
        c.drawCentredString(col_center_x, current_y + 4 * mm, qty_display)
        x += col_widths[2]

        # Rate (center aligned, show "-" for GST and Commission rows)
        currency = data.get("currency", "")
        rate = item.get("rate", 0)
        amount = item.get("amount", 0)

        # For GST and Commission rows, rate column shows "-"
        if description.startswith("GST") or description.startswith("Platform Commission") or rate == "-":
            rate_display = "-"
        else:
            rate_display = f"{currency}{rate:,.2f}"
        col_center_x = x + col_widths[3] / 2
        c.drawCentredString(col_center_x, current_y + 4 * mm, rate_display)
        x += col_widths[3]

        # Amount (center aligned)
        amount_display = f"{currency}{amount:,.2f}"
        col_center_x = x + col_widths[4] / 2
        c.drawCentredString(col_center_x, current_y + 4 * mm, amount_display)

    c.setStrokeColorRGB(0.80, 0.80, 0.80)
    c.line(left_margin, current_y, left_margin + table_width, current_y)

    return current_y - 5 * mm


def _draw_totals_section(c: canvas.Canvas, data: Dict[str, Any], page_width: float, start_y: float) -> float:
    """Draw totals section on the lower-right side."""
    inv = data["invoice"]
    currency = data.get("currency", "")
    invoice_type = data.get("invoice_type", "customer")

    # Use total_due from data if available, otherwise calculate from items
    total_due = data.get("total_due", 0)
    if total_due == 0:
        items: List[Dict[str, Any]] = data.get("items", [])
        total_due = sum(float(i.get("amount", 0)) for i in items)

    box_width = 70 * mm
    right_margin = 25 * mm
    box_x = page_width - right_margin - box_width
    
    # For customer invoices, show subtotal, GST, and total
    if invoice_type == "customer":
        gst_amount = data.get("gst_amount", 0)
        gst_percentage = data.get("gst_percentage", 18)
        subtotal = data.get("subtotal", total_due - gst_amount)
        
        # Calculate box height based on number of lines
        box_height = 40 * mm  # Increased height for GST line
        box_y = start_y - box_height
        
        # Draw background box
        c.setFillColorRGB(0.22, 0.55, 0.80)
        c.rect(box_x, box_y + box_height - 9 * mm, box_width, 9 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(box_x + box_width / 2, box_y + box_height - 6 * mm, "TOTAL AMOUNT")
        
        # Draw subtotal, GST, and total
        c.setFillColor(colors.black)
        y_pos = box_y + box_height - 15 * mm
        
        # Subtotal
        c.setFont("Helvetica", 9)
        c.drawString(box_x + 2 * mm, y_pos, "Subtotal:")
        c.drawRightString(box_x + box_width - 2 * mm, y_pos, f"{currency}{subtotal:,.2f}")
        y_pos -= 6 * mm
        
        # GST
        c.drawString(box_x + 2 * mm, y_pos, f"GST ({gst_percentage}%):")
        c.drawRightString(box_x + box_width - 2 * mm, y_pos, f"{currency}{gst_amount:,.2f}")
        y_pos -= 8 * mm
        
        # Total Amount (bold and larger)
        c.setFont("Helvetica-Bold", 16)
        c.drawRightString(box_x + box_width - 2 * mm, y_pos, f"{currency}{total_due:,.2f}")
        
        return box_y - 6 * mm
    else:
        # For designer invoices, keep the original simple layout
        box_height = 25 * mm
        box_y = start_y - box_height

        c.setFillColorRGB(0.22, 0.55, 0.80)
        c.rect(box_x, box_y + box_height - 9 * mm, box_width, 9 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(box_x + box_width / 2, box_y + box_height - 6 * mm, "TOTAL AMOUNT")

        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(box_x + box_width / 2, box_y + 9 * mm, f"{currency}{total_due:,.2f}")

        return box_y - 6 * mm


def _draw_thank_you(c: canvas.Canvas, data: Dict[str, Any], page_width: float, y: float) -> float:
    """Draw thank you note centered near the bottom with attractive styling."""
    c.setFont("Helvetica-Bold", 10)
    c.setFillColorRGB(0.22, 0.55, 0.80)
    c.drawCentredString(page_width / 2, y, "Thank you for doing business with us")
    return y - 6 * mm


def generate_invoice_pdf(invoice_data: Dict[str, Any], output_path: str) -> None:
    """Generate a PDF invoice."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    page_width, page_height = A4
    c = canvas.Canvas(output_path, pagesize=A4)

    top_margin = page_height - 30 * mm
    left_margin = 25 * mm

    y = top_margin
    y_left = _draw_logo_and_company(c, invoice_data, page_width, y)
    y_right = _draw_invoice_meta(c, invoice_data, page_width, y)
    y = min(y_left, y_right) - 4 * mm

    c.setStrokeColorRGB(0.90, 0.90, 0.90)
    c.setLineWidth(0.5)
    c.line(left_margin, y, page_width - left_margin, y)
    y -= 8 * mm

    y = _draw_billed_and_from_blocks(c, invoice_data, page_width, y)

    c.setStrokeColorRGB(0.90, 0.90, 0.90)
    c.line(left_margin, y, page_width - left_margin, y)
    y -= 6 * mm

    y = _draw_items_table(c, invoice_data, page_width, y)

    y_totals_bottom = _draw_totals_section(c, invoice_data, page_width, y - 4 * mm)

    footer_y = 32 * mm
    footer_bottom = _draw_company_contact(c, invoice_data, page_width, footer_y)
    _draw_thank_you(c, invoice_data, page_width, footer_bottom - 4 * mm)

    c.showPage()
    c.save()


def get_company_details() -> Dict[str, Any]:
    """Get WeDesignz company details for invoices."""
    from django.conf import settings
    import os
    
    # Helper function to find logo file
    def find_logo_file(filename):
        static_root = getattr(settings, 'STATIC_ROOT', None)
        if static_root:
            logo_path = os.path.join(static_root, 'Logos', filename)
            if os.path.exists(logo_path):
                return logo_path
        # Fallback to staticfiles directory
        base_dir = getattr(settings, 'BASE_DIR', os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        logo_path = os.path.join(base_dir, 'staticfiles', 'Logos', filename)
        if os.path.exists(logo_path):
            return logo_path
        return ""
    
    # Try to find logo (prefer PNG, fallback to SVG)
    logo_path = find_logo_file('ONLY LOGO.png')
    if not logo_path:
        logo_path = find_logo_file('ONLY LOGO.svg')
    
    # Try to find text logo (prefer PNG, fallback to SVG)
    text_logo_path = find_logo_file('ONLY TEXT.png')
    if not text_logo_path:
        text_logo_path = find_logo_file('ONLY TEXT.svg')
    
    return {
        "logo": logo_path,
        "text_logo": text_logo_path,
        "company_name": "WeDesignz",
        "company_email": "support@wedesignz.com",
        "company_bank_details": "IBAN ESXX XXXX XXXX XXX",  # Update with actual bank details
        "company_gst_number": "08IXHPS5429F2ZX",
        "company_address_line1": "B-117, Akar Tower, B-block, Old RTO road, Yogi Tower",
        "company_address_line2": "Bhilwara - 311001",
        "company_support_link": "https://support.wedesignz.com",  # Update with actual support link
    }


def get_user_address(user: User) -> Dict[str, str]:
    """Get user address details for invoice including GST number."""
    from Profiles.models import DesignerProfile, Studio, StudioBusinessDetails
    from Profiles.models import Addresses
    
    # Get company/individual name
    company_name = user.get_full_name() or user.username
    
    # Try to get address from Addresses model (for customers)
    address_line1 = ""
    address_line2 = ""
    gst_number = None
    
    # Check if user has addresses
    addresses = Addresses.objects.filter(created_by=user).order_by('-is_permanent', '-created_at')
    primary_address = addresses.first()
    
    if primary_address:
        address_parts = []
        if primary_address.address_line_1:
            address_parts.append(primary_address.address_line_1)
        if primary_address.address_line_2:
            address_parts.append(primary_address.address_line_2)
        if primary_address.landmark:
            address_parts.append(primary_address.landmark)
        
        address_line1 = ", ".join(address_parts) if address_parts else ""
        
        city_state_parts = []
        if primary_address.city:
            city_state_parts.append(primary_address.city)
        if primary_address.state:
            city_state_parts.append(primary_address.state)
        if primary_address.postal_code:
            city_state_parts.append(primary_address.postal_code)
        
        address_line2 = ", ".join(city_state_parts) if city_state_parts else ""
    
    # Try to get GST number from StudioBusinessDetails (if user is a designer)
    try:
        designer_profile = DesignerProfile.objects.filter(created_by=user).first()
        if designer_profile:
            studio = Studio.objects.filter(created_by=user).first()
            if studio:
                business_details = StudioBusinessDetails.objects.filter(studio=studio).first()
                if business_details and business_details.gst_number:
                    gst_number = business_details.gst_number
                if business_details and business_details.legal_business_name:
                    company_name = business_details.legal_business_name
    except:
        pass
    
    return {
        "client_company": company_name,
        "client_address_line1": address_line1,
        "client_address_line2": address_line2,
        "client_gst_number": gst_number,
    }


def create_customer_invoice(order: Order) -> Invoice:
    """Create and generate customer invoice for the full order amount."""
    breakdown = calculate_order_breakdown(order)
    
    invoice = Invoice()
    invoice.invoice_number = invoice.generate_invoice_number()
    invoice.invoice_type = 'customer'
    invoice.order = order
    invoice.user = order.created_by
    invoice.subtotal = breakdown['total_amount'] - breakdown['gst_amount']
    invoice.gst_amount = breakdown['gst_amount']
    invoice.commission_amount = Decimal('0')
    invoice.total_amount = breakdown['total_amount']
    invoice.payment_due_date = timezone.now().date()
    invoice.save()
    
    # Prepare invoice data for PDF
    company_details = get_company_details()
    user_address = get_user_address(order.created_by)
    
    # Get products for invoice items
    items = []
    if order.product_ids:
        product_ids = [int(pid.strip()) for pid in order.product_ids.split(',') if pid.strip()]
        products = Product.objects.filter(id__in=product_ids)
        
        # Count total products
        total_quantity = len(products)
        
        if total_quantity > 0:
            # Calculate rate per item (base_amount + commission, before GST)
            # amount_after_gst = base_amount + commission = total_amount - gst_amount
            amount_after_gst_total = float(breakdown['total_amount']) - float(breakdown['gst_amount'])
            rate_per_item = amount_after_gst_total / total_quantity
            
            # Only Individual Design row (GST will be shown in totals section)
            items.append({
                "item_no": 1,
                "description": "Individual Design",
                "quantity": total_quantity,
                "rate": rate_per_item,
                "amount": amount_after_gst_total,  # quantity * rate
            })
    
    invoice_data = {
        "invoice": {
            "invoice_number": invoice.invoice_number,
            "order_number": order.order_number or f"ORD-{order.id}",
            "invoice_date": invoice.invoice_date.strftime('%B %d, %Y'),
            "payment_due_date": invoice.payment_due_date.strftime('%b %d, %Y') if invoice.payment_due_date else "",
        },
        "invoice_type": "customer",  # Add invoice type for PDF title
        "company_details": company_details,
        "billed_to": user_address,
        "from_details": {
            "sender_name": company_details.get("company_name", "WeDesignz"),
            "sender_address_line1": company_details.get("company_address_line1", ""),
            "sender_address_line2": company_details.get("company_address_line2", ""),
            "sender_gst_number": company_details.get("company_gst_number", ""),
        },
        "items": items,
        "currency": "Rs",
        "total_due": float(breakdown['total_amount']),
        "gst_amount": float(breakdown['gst_amount']),
        "gst_percentage": BusinessConfig.get_gst_percentage(),
        "subtotal": float(breakdown['total_amount']) - float(breakdown['gst_amount']),
    }
    
    invoice.invoice_data = invoice_data
    invoice.save()
    
    # Generate PDF
    media_root = getattr(settings, 'MEDIA_ROOT', 'media')
    invoice_dir = os.path.join(media_root, 'invoices')
    pdf_filename = f"{invoice.invoice_number}.pdf"
    pdf_path = os.path.join(invoice_dir, pdf_filename)
    
    generate_invoice_pdf(invoice_data, pdf_path)
    
    invoice.pdf_file_path = pdf_path
    invoice.save()
    
    # Send email to customer asynchronously
    try:
        from common.tasks import send_customer_invoice_email_async
        send_customer_invoice_email_async.delay(invoice.id, order.id)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Failed to queue customer invoice email: {str(e)}', exc_info=True)
    
    return invoice


def create_designer_invoice(order: Order, designer: User, breakdown: Dict[str, Any]) -> Invoice:
    """Create and generate designer invoice for GST + Commission."""
    invoice = Invoice()
    invoice.invoice_number = invoice.generate_bill_number()  # Use BILL prefix
    invoice.invoice_type = 'designer'
    invoice.order = order
    invoice.user = designer
    invoice.subtotal = breakdown['product_total']
    invoice.gst_amount = breakdown['gst_amount']
    invoice.commission_amount = breakdown['commission_amount']
    invoice.total_amount = breakdown['gst_amount'] + breakdown['commission_amount']
    invoice.payment_due_date = timezone.now().date()
    invoice.save()
    
    # Prepare invoice data
    company_details = get_company_details()
    user_address = get_user_address(designer)
    
    # Calculate base amount for commission calculation display
    base_for_commission = breakdown['product_total'] - breakdown['gst_amount']
    
    # Determine purchase type and plan name
    plan_name = None
    if order.subscription and order.subscription.plan:
        plan_name = order.subscription.plan.plan_name  # 'basic', 'prime', or 'premium'
    
    # Create items based on purchase type
    items = []
    
    if plan_name:
        # Purchase with subscription - capitalize plan name
        plan_display = plan_name.capitalize()  # 'Basic', 'Prime', or 'Premium'
        
        items.append({
            "item_no": 1,
            "description": f"GST on Designs of {plan_display} Plan",
            "quantity": "-",
            "rate": "-",
            "amount": float(breakdown['gst_amount']),
        })
        items.append({
            "item_no": 2,
            "description": f"Platform Commission on {plan_display} Plan",
            "quantity": "-",
            "rate": "-",
            "amount": float(breakdown['commission_amount']),
        })
    else:
        # Purchase without subscription (individual design)
        items.append({
            "item_no": 1,
            "description": "GST on individual design",
            "quantity": "-",
            "rate": "-",
            "amount": float(breakdown['gst_amount']),
        })
        items.append({
            "item_no": 2,
            "description": "Platform Commission on individual Design after GST",
            "quantity": "-",
            "rate": "-",
            "amount": float(breakdown['commission_amount']),
        })
    
    invoice_data = {
        "invoice": {
            "invoice_number": invoice.invoice_number,
            # Remove order_number for designer invoices
            "invoice_date": invoice.invoice_date.strftime('%B %d, %Y'),
            "payment_due_date": invoice.payment_due_date.strftime('%b %d, %Y') if invoice.payment_due_date else "",
        },
        "invoice_type": "designer",  # Add invoice type for PDF title
        "company_details": company_details,
        "billed_to": user_address,
        "from_details": {
            "sender_name": company_details.get("company_name", "WeDesignz"),
            "sender_address_line1": company_details.get("company_address_line1", ""),
            "sender_address_line2": company_details.get("company_address_line2", ""),
            "sender_gst_number": company_details.get("company_gst_number", ""),
        },
        "items": items,
        "currency": "Rs",
        "total_due": float(breakdown['gst_amount'] + breakdown['commission_amount']),
    }
    
    invoice.invoice_data = invoice_data
    invoice.save()
    
    # Generate PDF
    media_root = getattr(settings, 'MEDIA_ROOT', 'media')
    invoice_dir = os.path.join(media_root, 'invoices')
    pdf_filename = f"{invoice.invoice_number}.pdf"
    pdf_path = os.path.join(invoice_dir, pdf_filename)
    
    generate_invoice_pdf(invoice_data, pdf_path)
    
    invoice.pdf_file_path = pdf_path
    invoice.save()
    
    # Send email to designer asynchronously
    try:
        from common.tasks import send_designer_invoice_email_async
        # Prepare breakdown data for serialization
        breakdown_data = {
            'product_total': float(breakdown['product_total']),
            'gst_amount': float(breakdown['gst_amount']),
            'commission_amount': float(breakdown['commission_amount']),
            'wallet_amount': float(breakdown['wallet_amount']),
            'product_ids': [p.id for p in breakdown['products']],  # Store product IDs to fetch in task
        }
        send_designer_invoice_email_async.delay(invoice.id, order.id, breakdown_data)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Failed to queue designer invoice email: {str(e)}', exc_info=True)
    
    return invoice


def create_monthly_designer_bill(designer: User, purchase_type_breakdowns: Dict[str, Dict[str, Any]], period_start: date, period_end: date) -> Invoice:
    """
    Create monthly bill for designer with separate rows for each purchase type.
    
    Args:
        designer: Designer user
        purchase_type_breakdowns: Dict with keys like 'individual', 'basic', 'prime', 'premium'
            Each value is a dict with 'gst_amount', 'commission_amount', 'product_total', 'orders'
        period_start: Start date of billing period
        period_end: End date of billing period
    """
    invoice = Invoice()
    invoice.invoice_number = invoice.generate_bill_number()
    invoice.invoice_type = 'designer'
    invoice.order = None  # No single order for monthly bills
    invoice.user = designer
    
    # Calculate totals
    total_gst = sum(Decimal(str(breakdown['gst_amount'])) for breakdown in purchase_type_breakdowns.values())
    total_commission = sum(Decimal(str(breakdown['commission_amount'])) for breakdown in purchase_type_breakdowns.values())
    total_product_total = sum(Decimal(str(breakdown['product_total'])) for breakdown in purchase_type_breakdowns.values())
    
    invoice.subtotal = total_product_total
    invoice.gst_amount = total_gst
    invoice.commission_amount = total_commission
    invoice.total_amount = total_gst + total_commission
    invoice.payment_due_date = timezone.now().date()
    invoice.save()
    
    # Prepare invoice data
    company_details = get_company_details()
    user_address = get_user_address(designer)
    
    # Create items for each purchase type
    items = []
    item_no = 1
    
    # Order: individual, basic, prime, premium
    purchase_type_order = ['individual', 'basic', 'prime', 'premium']
    
    for purchase_type in purchase_type_order:
        if purchase_type not in purchase_type_breakdowns:
            continue
            
        breakdown = purchase_type_breakdowns[purchase_type]
        gst_amount = float(breakdown['gst_amount'])
        commission_amount = float(breakdown['commission_amount'])
        design_count = breakdown.get('design_count', 0)
        
        if gst_amount > 0:
            if purchase_type == 'individual':
                items.append({
                    "item_no": item_no,
                    "description": "GST on individual design",
                    "quantity": design_count,  # Show actual count of designs
                    "rate": "-",
                    "amount": gst_amount,
                })
            else:
                plan_display = purchase_type.capitalize()  # 'Basic', 'Prime', 'Premium'
                items.append({
                    "item_no": item_no,
                    "description": f"GST on Designs of {plan_display} Plan",
                    "quantity": design_count,  # Show actual count of designs
                    "rate": "-",
                    "amount": gst_amount,
                })
            item_no += 1
        
        if commission_amount > 0:
            if purchase_type == 'individual':
                items.append({
                    "item_no": item_no,
                    "description": "Platform Commission on individual Design after GST",
                    "quantity": design_count,  # Show actual count of designs
                    "rate": "-",
                    "amount": commission_amount,
                })
            else:
                plan_display = purchase_type.capitalize()
                items.append({
                    "item_no": item_no,
                    "description": f"Platform Commission on {plan_display} Plan",
                    "quantity": design_count,  # Show actual count of designs
                    "rate": "-",
                    "amount": commission_amount,
                })
            item_no += 1
    
    invoice_data = {
        "invoice": {
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date.strftime('%B %d, %Y'),
            "payment_due_date": invoice.payment_due_date.strftime('%b %d, %Y') if invoice.payment_due_date else "",
        },
        "invoice_type": "designer",
        "company_details": company_details,
        "billed_to": user_address,
        "from_details": {
            "sender_name": company_details.get("company_name", "WeDesignz"),
            "sender_address_line1": company_details.get("company_address_line1", ""),
            "sender_address_line2": company_details.get("company_address_line2", ""),
            "sender_gst_number": company_details.get("company_gst_number", ""),
        },
        "items": items,
        "currency": "Rs",
        "total_due": float(total_gst + total_commission),
    }
    
    invoice.invoice_data = invoice_data
    invoice.save()
    
    # Generate PDF
    media_root = getattr(settings, 'MEDIA_ROOT', 'media')
    invoice_dir = os.path.join(media_root, 'invoices')
    pdf_filename = f"{invoice.invoice_number}.pdf"
    pdf_path = os.path.join(invoice_dir, pdf_filename)
    
    generate_invoice_pdf(invoice_data, pdf_path)
    
    invoice.pdf_file_path = pdf_path
    invoice.save()
    
    return invoice


def process_order_invoices(order: Order) -> Dict[str, Any]:
    """
    Main function to process invoices and wallet settlements for an order.
    Called when payment is successfully captured.
    
    Returns:
        Dict with customer_invoice, designer_invoices list, and wallet_transactions list
    """
    breakdown = calculate_order_breakdown(order)
    
    # Create customer invoice
    customer_invoice = create_customer_invoice(order)
    
    # Process each designer
    designer_invoices = []
    wallet_transactions = []
    
    for designer_id, designer_breakdown in breakdown['designer_breakdown'].items():
        designer = designer_breakdown['designer']
        
        # Add money to designer wallet
        wallet, _ = Wallet.objects.get_or_create(created_by=designer)
        wallet.balance = Decimal(str(wallet.balance)) + designer_breakdown['wallet_amount']
        wallet.save()
        
        # Create wallet transaction
        transaction = WalletTransaction.objects.create(
            wallet_transaction_type='credit',
            amount=designer_breakdown['wallet_amount'],
            description=f"Earnings from order {order.order_number}",
            reference_id=f"order_{order.id}",
            created_by=designer
        )
        wallet.attach_wallet_transaction(transaction)
        wallet_transactions.append(transaction)
        
        # Create designer invoice
        designer_invoice = create_designer_invoice(order, designer, designer_breakdown)
        designer_invoices.append(designer_invoice)
    
    return {
        'customer_invoice': customer_invoice,
        'designer_invoices': designer_invoices,
        'wallet_transactions': wallet_transactions,
    }


def create_designer_invoice_for_subscription(subscription: Subscription, designer: User, breakdown: Dict[str, Any]) -> Invoice:
    """Create and generate designer invoice (bill) for subscription settlement."""
    invoice = Invoice()
    invoice.invoice_number = invoice.generate_invoice_number()
    invoice.invoice_type = 'designer'
    invoice.order = None  # No order for subscription settlements
    invoice.subscription = subscription
    invoice.user = designer
    invoice.subtotal = breakdown['product_total']
    invoice.gst_amount = breakdown['gst_amount']
    invoice.commission_amount = breakdown['commission_amount']
    invoice.total_amount = breakdown['gst_amount'] + breakdown['commission_amount']
    invoice.payment_due_date = timezone.now().date()
    invoice.save()
    
    # Prepare invoice data
    company_details = get_company_details()
    user_address = get_user_address(designer)
    
    # Calculate base amount for commission calculation display
    base_for_commission = breakdown['product_total'] - breakdown['gst_amount']
    
    # Create more descriptive items
    items = [
        {
            "item_no": 1,
            "description": f"GST (18% on Design Sales of Rs {breakdown['product_total']:.2f})",
            "quantity": 1,
            "rate": float(breakdown['gst_amount']),
            "amount": float(breakdown['gst_amount']),
        },
        {
            "item_no": 2,
            "description": f"Platform Commission on Rs {base_for_commission:.2f} after GST",
            "quantity": "-",
            "rate": "-",
            "amount": float(breakdown['commission_amount']),
        },
    ]
    
    # Create subscription reference number
    subscription_ref = f"SUB-{subscription.id}"
    
    invoice_data = {
        "invoice": {
            "invoice_number": invoice.invoice_number,
            "order_number": subscription_ref,  # Use subscription reference instead of order number
            "invoice_date": invoice.invoice_date.strftime('%B %d, %Y'),
            "payment_due_date": invoice.payment_due_date.strftime('%b %d, %Y') if invoice.payment_due_date else "",
        },
        "invoice_type": "designer",
        "company_details": company_details,
        "billed_to": user_address,
        "from_details": {
            "sender_name": company_details.get("company_name", "WeDesignz"),
            "sender_address_line1": company_details.get("company_address_line1", ""),
            "sender_address_line2": company_details.get("company_address_line2", ""),
            "sender_gst_number": company_details.get("company_gst_number", ""),
        },
        "items": items,
        "currency": "Rs",
        "total_due": float(breakdown['gst_amount'] + breakdown['commission_amount']),
    }
    
    invoice.invoice_data = invoice_data
    invoice.save()
    
    # Generate PDF
    media_root = getattr(settings, 'MEDIA_ROOT', 'media')
    invoice_dir = os.path.join(media_root, 'invoices')
    pdf_filename = f"{invoice.invoice_number}.pdf"
    pdf_path = os.path.join(invoice_dir, pdf_filename)
    
    generate_invoice_pdf(invoice_data, pdf_path)
    
    invoice.pdf_file_path = pdf_path
    invoice.save()
    
    # Send email to designer asynchronously
    try:
        from common.tasks import send_designer_subscription_invoice_email_async
        # Prepare breakdown data for serialization
        breakdown_data = {
            'product_total': float(breakdown['product_total']),
            'gst_amount': float(breakdown['gst_amount']),
            'commission_amount': float(breakdown['commission_amount']),
            'wallet_amount': float(breakdown['wallet_amount']),
            'download_count': breakdown.get('download_count', 0),
            'product_ids': [p.id for p in breakdown['products']],
        }
        send_designer_subscription_invoice_email_async.delay(invoice.id, subscription.id, breakdown_data)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Failed to queue designer subscription invoice email: {str(e)}', exc_info=True)
    
    return invoice


def process_monthly_subscription_settlement(
    subscription: Subscription, 
    period_start: date, 
    period_end: date
) -> Dict[str, Any]:
    """
    Process monthly settlement for annual subscriptions based on purchase date.
    Settles every 30 days from purchase date (not calendar months).
    
    Example:
    - Annual subscription purchased March 14: Rs 1200, 120 downloads
    - First settlement period: March 14 - April 14 (30 days)
    - Second settlement period: April 15 - May 14 (30 days)
    - Monthly price: Rs 100, Monthly downloads: 10
    
    If customer used 7 downloads in period (5 from Designer1, 2 from Designer2):
    - Unused: 3 downloads
    - Settlement: Calculate as if 10 downloads were used
    - Unused 3 downloads distributed proportionally: Designer1 gets 5/7, Designer2 gets 2/7
    """
    from datetime import timedelta
    
    # Calculate monthly allocation
    annual_price = Decimal(str(subscription.plan.price))
    monthly_price = annual_price / Decimal('12')
    
    # Calculate monthly download allocation
    total_annual_downloads = subscription.plan.no_of_free_downloads
    monthly_downloads_allowed = total_annual_downloads // 12
    
    # Get all subscription orders for this period
    subscription_orders = Order.objects.filter(
        subscription=subscription,
        order_type='subscription',
        status='success',
        created_at__gte=timezone.make_aware(datetime.combine(period_start, datetime.min.time())),
        created_at__lt=timezone.make_aware(datetime.combine(period_end, datetime.max.time())) + timedelta(days=1)
    )
    
    # Collect all products downloaded in this period
    all_products = []
    total_downloads_used = 0
    
    for order in subscription_orders:
        if order.product_ids:
            product_ids = [int(pid.strip()) for pid in order.product_ids.split(',') if pid.strip()]
            products = Product.objects.filter(id__in=product_ids)
            all_products.extend(products)
            total_downloads_used += len(product_ids)
    
    # If no downloads used, no settlement (amount remains with platform)
    # But still update last_settled_month to track that this period was processed
    if total_downloads_used == 0:
        subscription.last_settled_month = period_end
        # Reset monthly counter for next period
        subscription.current_period_downloads_used = 0
        subscription.current_period_start = period_end  # Next period starts from period_end
        subscription.save()
        return {
            'subscription_id': subscription.id,
            'period_start': period_start.strftime('%Y-%m-%d'),
            'period_end': period_end.strftime('%Y-%m-%d'),
            'total_downloads_used': 0,
            'total_downloads_settled': 0,
            'message': 'No downloads used in this period, no settlement'
        }
    
    # Step 1: Extract base amount from monthly price (includes GST and commission)
    gst_percentage = Decimal(str(BusinessConfig.get_gst_percentage()))
    commission_rate = Decimal(str(BusinessConfig.get_commission_rate()))
    
    # Extract base from monthly_price (reverse calculation)
    monthly_extracted = extract_gst_and_commission(monthly_price, gst_percentage, commission_rate)
    monthly_base_amount = monthly_extracted['base_amount']  # This is the Rs 65.2
    
    # Step 2: Distribute monthly price proportionally based on actual downloads used
    # Group products by designer first
    designer_breakdown = {}
    
    for product in all_products:
        designer_id = product.created_by.id
        
        if designer_id not in designer_breakdown:
            designer_breakdown[designer_id] = {
                'designer': product.created_by,
                'products': [],
                'download_count': 0,
                'product_total': Decimal('0'),  # Total price including GST and commission
                'gst_amount': Decimal('0'),
                'commission_amount': Decimal('0'),
                'wallet_amount': Decimal('0'),
            }
        
        designer_breakdown[designer_id]['products'].append(product)
        designer_breakdown[designer_id]['download_count'] += 1
    
    # Distribute monthly_price proportionally based on actual downloads
    for designer_id, breakdown in designer_breakdown.items():
        # Calculate proportion: designer downloads / total downloads used
        proportion = Decimal(str(breakdown['download_count'])) / Decimal(str(total_downloads_used))
        breakdown['product_total'] = monthly_price * proportion  # Designer's share of monthly price
    
    # Step 3: Extract GST and commission from each designer's share
    for designer_id, breakdown in designer_breakdown.items():
        # Extract GST and commission from designer's product_total (which includes GST and commission)
        extracted = extract_gst_and_commission(breakdown['product_total'], gst_percentage, commission_rate)
        breakdown['gst_amount'] = extracted['gst_amount']
        breakdown['commission_amount'] = extracted['commission_amount']
        breakdown['wallet_amount'] = extracted['base_amount']  # Base amount goes to wallet
    
    # Process settlements for each designer
    designer_invoices = []
    wallet_transactions = []
    
    for designer_id, breakdown in designer_breakdown.items():
        designer = breakdown['designer']
        
        # Add money to designer wallet
        wallet, _ = Wallet.objects.get_or_create(created_by=designer)
        wallet.balance = Decimal(str(wallet.balance)) + breakdown['wallet_amount']
        wallet.save()
        
        # Create wallet transaction
        transaction = WalletTransaction.objects.create(
            wallet_transaction_type='credit',
            amount=breakdown['wallet_amount'],
            description=f"Earnings from subscription {subscription.id} - {period_start.strftime('%b %d')} to {period_end.strftime('%b %d, %Y')} ({breakdown['download_count']} downloads + unused allocation)",
            reference_id=f"subscription_{subscription.id}_{period_start.strftime('%Y%m%d')}",
            created_by=designer
        )
        wallet.attach_wallet_transaction(transaction)
        wallet_transactions.append(transaction)
        
        # Create designer invoice (bill) for subscription settlement
        designer_invoice = create_designer_invoice_for_subscription(subscription, designer, breakdown)
        designer_invoices.append(designer_invoice)
    
    # Update last settled date (use period_end as the settlement date)
    subscription.last_settled_month = period_end
    # Reset monthly counter for next period
    subscription.current_period_downloads_used = 0
    subscription.current_period_start = period_end  # Next period starts from period_end
    subscription.save()
    
    # Calculate unused downloads for reporting
    unused_downloads = monthly_downloads_allowed - total_downloads_used
    
    return {
        'subscription_id': subscription.id,
        'period_start': period_start.strftime('%Y-%m-%d'),
        'period_end': period_end.strftime('%Y-%m-%d'),
        'total_downloads_used': total_downloads_used,
        'total_downloads_settled': monthly_downloads_allowed,
        'unused_downloads': unused_downloads,
        'monthly_price': float(monthly_price),
        'monthly_base_amount': float(monthly_extracted['base_amount']),
        'designer_breakdown': {
            designer_id: {
                'designer_id': designer_id,
                'download_count': breakdown['download_count'],
                'product_total': float(breakdown['product_total']),
                'gst_amount': float(breakdown['gst_amount']),
                'commission_amount': float(breakdown['commission_amount']),
                'wallet_amount': float(breakdown['wallet_amount']),
            }
            for designer_id, breakdown in designer_breakdown.items()
        },
        'designer_invoices': [inv.id for inv in designer_invoices],
        'wallet_transactions': [txn.id for txn in wallet_transactions],
    }


def process_subscription_settlement(subscription: Subscription) -> Dict[str, Any]:
    """
    Process subscription settlement for monthly subscriptions when subscription period ends.
    Distributes subscription price across actual downloads used.
    
    Example:
    - Subscription: Rs 400, 20 downloads allowed
    - Actual downloads: 10 (6 from designer1, 4 from designer2)
    - Per download price: Rs 400 / 10 = Rs 40
    - Designer1: 6 × Rs 40 = Rs 240
    - Designer2: 4 × Rs 40 = Rs 160
    - Then apply GST and commission calculations
    """
    from datetime import timedelta
    
    # For monthly subscriptions, calculate period end date (30 days from creation)
    period_end = subscription.created_at + timedelta(days=30)
    
    # Get all subscription orders for this subscription period
    subscription_orders = Order.objects.filter(
        subscription=subscription,
        order_type='subscription',
        status='success',
        created_at__gte=subscription.created_at,
        created_at__lt=period_end
    )
    
    # Collect all products downloaded
    all_products = []
    total_downloads = 0
    
    for order in subscription_orders:
        if order.product_ids:
            product_ids = [int(pid.strip()) for pid in order.product_ids.split(',') if pid.strip()]
            products = Product.objects.filter(id__in=product_ids)
            all_products.extend(products)
            total_downloads += len(product_ids)
    
    if total_downloads == 0:
        # No downloads used, nothing to distribute
        # But still mark subscription as expired and settlement processed
        subscription.status = 'expired'
        subscription.settlement_processed = True
        subscription.save()
        return {
            'subscription_id': subscription.id,
            'total_downloads': 0,
            'message': 'No downloads used in this subscription period'
        }
    
    # Step 1: Extract base amount from subscription price (includes GST and commission)
    subscription_price = Decimal(str(subscription.plan.price))
    gst_percentage = Decimal(str(BusinessConfig.get_gst_percentage()))
    commission_rate = Decimal(str(BusinessConfig.get_commission_rate()))
    
    # Extract base from subscription_price (reverse calculation)
    subscription_extracted = extract_gst_and_commission(subscription_price, gst_percentage, commission_rate)
    subscription_base_amount = subscription_extracted['base_amount']
    
    # Step 2: Distribute subscription price proportionally based on actual downloads used
    # Group products by designer
    designer_breakdown = {}
    
    for product in all_products:
        designer_id = product.created_by.id
        
        if designer_id not in designer_breakdown:
            designer_breakdown[designer_id] = {
                'designer': product.created_by,
                'products': [],
                'download_count': 0,
                'product_total': Decimal('0'),  # Total price including GST and commission
                'gst_amount': Decimal('0'),
                'commission_amount': Decimal('0'),
                'wallet_amount': Decimal('0'),
            }
        
        designer_breakdown[designer_id]['products'].append(product)
        designer_breakdown[designer_id]['download_count'] += 1
    
    # Distribute subscription_price proportionally based on actual downloads
    for designer_id, breakdown in designer_breakdown.items():
        # Calculate proportion: designer downloads / total downloads
        proportion = Decimal(str(breakdown['download_count'])) / Decimal(str(total_downloads))
        breakdown['product_total'] = subscription_price * proportion  # Designer's share of subscription price
    
    # Step 3: Extract GST and commission from each designer's share
    for designer_id, breakdown in designer_breakdown.items():
        # Extract GST and commission from designer's product_total (which includes GST and commission)
        extracted = extract_gst_and_commission(breakdown['product_total'], gst_percentage, commission_rate)
        breakdown['gst_amount'] = extracted['gst_amount']
        breakdown['commission_amount'] = extracted['commission_amount']
        breakdown['wallet_amount'] = extracted['base_amount']  # Base amount goes to wallet
    
    # Process settlements for each designer
    designer_invoices = []
    wallet_transactions = []
    
    for designer_id, breakdown in designer_breakdown.items():
        designer = breakdown['designer']
        
        # Add money to designer wallet
        wallet, _ = Wallet.objects.get_or_create(created_by=designer)
        wallet.balance = Decimal(str(wallet.balance)) + breakdown['wallet_amount']
        wallet.save()
        
        # Create wallet transaction
        transaction = WalletTransaction.objects.create(
            wallet_transaction_type='credit',
            amount=breakdown['wallet_amount'],
            description=f"Earnings from subscription {subscription.id} ({breakdown['download_count']} downloads)",
            reference_id=f"subscription_{subscription.id}",
            created_by=designer
        )
        wallet.attach_wallet_transaction(transaction)
        wallet_transactions.append(transaction)
        
        # Create designer invoice (bill) for subscription settlement
        designer_invoice = create_designer_invoice_for_subscription(subscription, designer, breakdown)
        designer_invoices.append(designer_invoice)
    
    # Mark subscription as expired and settlement processed
    subscription.status = 'expired'
    subscription.settlement_processed = True
    subscription.save()
    
    # Calculate per download price for reporting
    per_download_price = subscription_price / Decimal(str(total_downloads)) if total_downloads > 0 else Decimal('0')
    
    return {
        'subscription_id': subscription.id,
        'total_downloads': total_downloads,
        'per_download_price': float(per_download_price),
        'subscription_price': float(subscription_price),
        'subscription_base_amount': float(subscription_extracted['base_amount']),
        'designer_breakdown': {
            designer_id: {
                'designer_id': designer_id,
                'download_count': breakdown['download_count'],
                'product_total': float(breakdown['product_total']),
                'gst_amount': float(breakdown['gst_amount']),
                'commission_amount': float(breakdown['commission_amount']),
                'wallet_amount': float(breakdown['wallet_amount']),
            }
            for designer_id, breakdown in designer_breakdown.items()
        },
        'designer_invoices': [inv.id for inv in designer_invoices],
        'wallet_transactions': [txn.id for txn in wallet_transactions],
    }

