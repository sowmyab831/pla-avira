"""Bills routes: receipt upload, OCR parsing, itemization."""
import logging
import io
import re
import base64
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
import httpx

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/bills", tags=["bills"])

# In-memory storage for bills (shared with chat)
bills_store: List[Dict[str, Any]] = []


class BillItem(BaseModel):
    """Individual item on a bill."""
    name: str
    quantity: float = 1
    price: float
    category: Optional[str] = None


class Bill(BaseModel):
    """Parsed bill model."""
    id: str
    vendor: str
    date: str
    items: List[BillItem]
    subtotal: float
    tax: float
    total: float
    payment_method: Optional[str] = None
    raw_text: Optional[str] = None
    uploaded_at: str


# Category mappings for common items
ITEM_CATEGORIES = {
    # Groceries
    "milk": "Groceries", "bread": "Groceries", "eggs": "Groceries", "cheese": "Groceries",
    "fruit": "Groceries", "vegetable": "Groceries", "meat": "Groceries", "chicken": "Groceries",
    "rice": "Groceries", "pasta": "Groceries", "cereal": "Groceries", "yogurt": "Groceries",
    # Household
    "paper": "Household", "towel": "Household", "soap": "Household", "detergent": "Household",
    "cleaner": "Household", "tissue": "Household", "trash": "Household",
    # Personal Care
    "shampoo": "Personal Care", "toothpaste": "Personal Care", "deodorant": "Personal Care",
    # Electronics
    "battery": "Electronics", "charger": "Electronics", "cable": "Electronics",
    # Dining
    "coffee": "Dining", "sandwich": "Dining", "burger": "Dining", "pizza": "Dining",
}


def categorize_item(item_name: str) -> str:
    """Categorize an item based on its name."""
    item_lower = item_name.lower()
    for keyword, category in ITEM_CATEGORIES.items():
        if keyword in item_lower:
            return category
    return "Other"


async def extract_text_with_ollama(image_base64: str) -> str:
    """Use Ollama vision model to extract text from receipt image."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.ollama_host}/api/generate",
                json={
                    "model": "llava",  # Vision model
                    "prompt": """Extract all text from this receipt image. 
                    Format the output as:
                    VENDOR: [store name]
                    DATE: [date if visible]
                    ITEMS:
                    - [item name] $[price]
                    SUBTOTAL: $[amount]
                    TAX: $[amount]
                    TOTAL: $[amount]
                    
                    If you can't read something, use [UNCLEAR].""",
                    "images": [image_base64],
                    "stream": False,
                },
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
    except Exception as e:
        logger.error(f"Ollama vision extraction failed: {e}")
        return ""


def parse_receipt_text(text: str) -> Dict[str, Any]:
    """Parse extracted receipt text into structured data."""
    result = {
        "vendor": "Unknown",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "items": [],
        "subtotal": 0.0,
        "tax": 0.0,
        "total": 0.0,
    }
    
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Extract vendor
        if line.upper().startswith("VENDOR:"):
            result["vendor"] = line.split(":", 1)[1].strip()
        
        # Extract date
        elif line.upper().startswith("DATE:"):
            date_str = line.split(":", 1)[1].strip()
            # Try to parse date
            for fmt in ["%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%B %d, %Y"]:
                try:
                    result["date"] = datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                    break
                except:
                    continue
        
        # Extract items (format: - item $price or item ... $price)
        elif line.startswith("-") or re.search(r'\$[\d.]+', line):
            price_match = re.search(r'\$?([\d]+\.[\d]{2})', line)
            if price_match:
                price = float(price_match.group(1))
                # Get item name (everything before the price)
                item_name = re.sub(r'\$?[\d]+\.[\d]{2}', '', line).strip()
                item_name = item_name.lstrip('-').strip()
                if item_name and price > 0:
                    result["items"].append({
                        "name": item_name,
                        "price": price,
                        "quantity": 1,
                        "category": categorize_item(item_name),
                    })
        
        # Extract totals
        elif "SUBTOTAL" in line.upper():
            match = re.search(r'\$?([\d]+\.[\d]{2})', line)
            if match:
                result["subtotal"] = float(match.group(1))
        
        elif "TAX" in line.upper():
            match = re.search(r'\$?([\d]+\.[\d]{2})', line)
            if match:
                result["tax"] = float(match.group(1))
        
        elif "TOTAL" in line.upper() and "SUBTOTAL" not in line.upper():
            match = re.search(r'\$?([\d]+\.[\d]{2})', line)
            if match:
                result["total"] = float(match.group(1))
    
    # Calculate totals if not found
    if result["subtotal"] == 0 and result["items"]:
        result["subtotal"] = sum(item["price"] for item in result["items"])
    
    if result["total"] == 0:
        result["total"] = result["subtotal"] + result["tax"]
    
    return result


@router.post("/upload")
async def upload_bill(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Upload a bill/receipt image and extract itemized data.
    
    Supports: JPG, PNG, PDF
    Uses Ollama vision model for OCR.
    """
    try:
        content = await file.read()
        
        # Check file type
        filename_lower = file.filename.lower()
        if not any(filename_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.pdf']):
            raise HTTPException(status_code=400, detail="Supported formats: JPG, PNG, PDF")
        
        # Convert to base64 for Ollama
        image_base64 = base64.b64encode(content).decode('utf-8')
        
        # Extract text using vision model
        extracted_text = await extract_text_with_ollama(image_base64)
        
        if not extracted_text:
            # Fallback: try basic OCR or return error
            raise HTTPException(status_code=500, detail="Could not extract text from image. Try a clearer photo.")
        
        # Parse the extracted text
        parsed = parse_receipt_text(extracted_text)
        
        # Create bill record
        bill = {
            "id": f"bill_{datetime.now().timestamp()}",
            "vendor": parsed["vendor"],
            "date": parsed["date"],
            "items": parsed["items"],
            "subtotal": parsed["subtotal"],
            "tax": parsed["tax"],
            "total": parsed["total"],
            "raw_text": extracted_text,
            "filename": file.filename,
            "uploaded_at": datetime.now().isoformat(),
        }
        
        # Store bill
        global bills_store
        bills_store.append(bill)
        
        logger.info(f"Parsed bill from {file.filename}: {len(parsed['items'])} items, total ${parsed['total']}")
        
        return {
            "success": True,
            "bill": bill,
            "message": f"Extracted {len(parsed['items'])} items totaling ${parsed['total']:.2f}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing bill: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def get_bills(limit: int = 50) -> Dict[str, Any]:
    """Get all uploaded bills."""
    return {
        "success": True,
        "count": len(bills_store),
        "bills": bills_store[-limit:],
    }


@router.get("/summary")
async def get_bills_summary() -> Dict[str, Any]:
    """Get spending summary from all bills."""
    if not bills_store:
        return {
            "success": True,
            "message": "No bills uploaded yet",
            "total_bills": 0,
            "total_spent": 0,
            "by_vendor": {},
            "by_category": {},
        }
    
    total_spent = sum(b.get("total", 0) for b in bills_store)
    
    by_vendor = {}
    by_category = {}
    
    for bill in bills_store:
        vendor = bill.get("vendor", "Unknown")
        by_vendor[vendor] = by_vendor.get(vendor, 0) + bill.get("total", 0)
        
        for item in bill.get("items", []):
            category = item.get("category", "Other")
            by_category[category] = by_category.get(category, 0) + item.get("price", 0)
    
    return {
        "success": True,
        "total_bills": len(bills_store),
        "total_spent": total_spent,
        "by_vendor": dict(sorted(by_vendor.items(), key=lambda x: x[1], reverse=True)),
        "by_category": dict(sorted(by_category.items(), key=lambda x: x[1], reverse=True)),
    }


@router.get("/spending-habits")
async def get_spending_habits() -> Dict[str, Any]:
    """Analyze spending habits and provide suggestions."""
    if not bills_store:
        return {
            "success": True,
            "message": "Upload bills to analyze spending habits",
            "habits": [],
            "suggestions": [],
        }
    
    # Analyze patterns
    by_category = {}
    by_day_of_week = {i: 0 for i in range(7)}
    
    for bill in bills_store:
        # Category spending
        for item in bill.get("items", []):
            category = item.get("category", "Other")
            by_category[category] = by_category.get(category, 0) + item.get("price", 0)
        
        # Day of week spending
        try:
            bill_date = datetime.fromisoformat(bill.get("date", ""))
            by_day_of_week[bill_date.weekday()] += bill.get("total", 0)
        except:
            pass
    
    # Generate habits
    habits = []
    suggestions = []
    
    # Top spending categories
    sorted_categories = sorted(by_category.items(), key=lambda x: x[1], reverse=True)
    if sorted_categories:
        top_category = sorted_categories[0]
        habits.append(f"Your top spending category is {top_category[0]} (${top_category[1]:.2f})")
        
        if top_category[0] == "Dining":
            suggestions.append("Consider meal prepping to reduce dining expenses")
        elif top_category[0] == "Groceries":
            suggestions.append("Try making a shopping list to avoid impulse purchases")
    
    # Day of week patterns
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    max_day = max(by_day_of_week.items(), key=lambda x: x[1])
    if max_day[1] > 0:
        habits.append(f"You spend most on {day_names[max_day[0]]}s")
        if max_day[0] >= 5:  # Weekend
            suggestions.append("Weekend spending is high - plan activities in advance")
    
    # Average bill size
    avg_bill = sum(b.get("total", 0) for b in bills_store) / len(bills_store)
    habits.append(f"Your average bill is ${avg_bill:.2f}")
    
    if avg_bill > 100:
        suggestions.append("Consider splitting large shopping trips into smaller, planned visits")
    
    return {
        "success": True,
        "habits": habits,
        "suggestions": suggestions,
        "by_category": dict(sorted_categories[:5]),
        "by_day_of_week": {day_names[k]: v for k, v in by_day_of_week.items()},
    }
