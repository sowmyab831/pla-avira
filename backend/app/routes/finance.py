"""Finance routes: bank statements, expense tracking, categorization."""
import logging
import io
import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from app.routes.auth import get_current_user
from app.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.private_scope import resolve_private_scope
import pandas as pd
import pdfplumber
from app.config import settings
from app.services.file_storage import get_file_storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/finance", tags=["finance"])

# In-memory storage for transactions (shared with chat for budget queries)
transactions_store: List[dict] = []

# In-memory storage for uploaded statement history
finance_reports_store: List[Dict[str, Any]] = []

# Persist finance state across restarts
FINANCE_STATE_FILE = Path(os.environ.get("AVIRA_DATA_DIR", "/data/documents")) / "finance_state.json"


def _save_finance_state():
    try:
        with open(FINANCE_STATE_FILE, 'w') as f:
            json.dump({"reports": finance_reports_store, "transactions": transactions_store}, f, default=str)
    except Exception as e:
        logger.error(f"Failed to save finance state: {e}")


def _load_finance_state():
    global finance_reports_store, transactions_store
    if FINANCE_STATE_FILE.exists():
        try:
            with open(FINANCE_STATE_FILE, 'r') as f:
                data = json.load(f)
                finance_reports_store = data.get("reports", [])
                transactions_store = data.get("transactions", [])
                # Backfill report_date for old reports
                for r in finance_reports_store:
                    if not r.get("report_date"):
                        r["report_date"] = r.get("uploaded_at", datetime.now().isoformat())[:10]
                    if not r.get("user_id"):
                        r["user_id"] = "default"
                # Backfill user_id on transactions (member-scoped partitions)
                for t in transactions_store:
                    if not t.get("user_id"):
                        t["user_id"] = "default"
                # Keep history sorted by statement date
                finance_reports_store.sort(key=lambda r: r.get("report_date") or r.get("uploaded_at", ""))
        except Exception as e:
            logger.error(f"Failed to load finance state: {e}")


_load_finance_state()


class Transaction(BaseModel):
    """Transaction model."""
    date: str
    description: str
    amount: float
    category: str
    is_flagged: bool = False


class ExpenseReport(BaseModel):
    """Expense report model."""
    total_spent: float
    transaction_count: int
    top_categories: dict
    flagged_transactions: List[Transaction]




@router.post("/upload-statement")
async def upload_bank_statement(files: List[UploadFile] = File(...), user_id: str = "default", user=Depends(get_current_user), db: AsyncSession = Depends(get_session)) -> dict:
    """
    Upload and parse one or more bank statements (CSV or PDF).

    Returns combined parsed transactions with categorization.
    """
    all_transactions: List[dict] = []
    file_ids: List[str] = []
    uploaded_files: List[str] = []
    report_dates: List[str] = []
    user_id = await resolve_private_scope(user_id, user, db)

    try:
        for file in files:
            content = await file.read()

            if not file.filename:
                continue

            if len(content) > settings.max_upload_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"{file.filename} exceeds the "
                           f"{settings.max_upload_bytes // (1024*1024)}MB upload limit"
                )

            # Save file to persistent storage
            storage = get_file_storage()
            file_id = storage.save_file(
                file_content=content,
                filename=file.filename,
                category="finance",
                user_id=user_id,
                metadata={"type": "bank_statement"}
            )
            file_ids.append(file_id)
            uploaded_files.append(file.filename)

            if file.filename.endswith(".csv"):
                report_date, transactions = _parse_csv(content)
            elif file.filename.endswith(".pdf"):
                report_date, transactions = _parse_pdf(content)
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported file format: {file.filename}")

            report_dates.append(report_date)
            all_transactions.extend(transactions)

            logger.info(f"Parsed {len(transactions)} transactions from {file.filename}, saved as {file_id}")

        # Categorize and flag combined transactions
        categorized = _categorize_transactions(all_transactions)
        flagged = _flag_large_spends(categorized)

        # Store transactions for budget queries
        global transactions_store, finance_reports_store
        flagged_dicts = [{**t.dict(), "user_id": user_id} for t in flagged]
        # Use the latest extracted statement date across all uploaded files
        latest_report_date = max(report_dates) if report_dates else datetime.now().strftime("%Y-%m-%d")
        report = {
            "id": f"report_{datetime.now().timestamp()}",
            "user_id": user_id,
            "file_ids": file_ids,
            "uploaded_files": uploaded_files,
            "report_date": latest_report_date,
            "transactions": flagged_dicts,
            "summary": _generate_summary(flagged).dict(),
            "uploaded_at": datetime.now().isoformat(),
        }
        finance_reports_store.append(report)
        # Keep finance history sorted by document date
        finance_reports_store.sort(key=lambda r: r.get("report_date") or r.get("uploaded_at", ""))
        # Flat store = union of all reports' transactions (each stamped with user_id)
        transactions_store = [t for r in finance_reports_store for t in r.get("transactions", [])]
        _save_finance_state()

        return {
            "file_ids": file_ids,
            "uploaded_files": uploaded_files,
            "transactions": [t.dict() for t in flagged],
            "summary": _generate_summary(flagged),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error parsing statement: {e}")
        raise HTTPException(status_code=400, detail=f"Could not parse statement: {e}")


def _extract_pdf_date(full_text: str) -> str:
    """Try to find a statement/report date in the PDF text."""
    date_patterns = [
        (r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})', "%d %B %Y"),
        (r'(\d{1,2}\s+\w{3}\s+\d{4})', "%d %b %Y"),
        (r'(\d{4}-\d{2}-\d{2})', "%Y-%m-%d"),
        (r'(\d{2}/\d{2}/\d{4})', "%d/%m/%Y"),
        (r'(\d{2}/\d{2}/\d{4})', "%m/%d/%Y"),
    ]
    for pattern, fmt in date_patterns:
        m = re.search(pattern, full_text)
        if m:
            try:
                return datetime.strptime(m.group(1), fmt).strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                continue
    return datetime.now().strftime("%Y-%m-%d")


def _parse_csv(content: bytes) -> tuple[str, List[dict]]:
    """Parse CSV bank statement with flexible US-style dates."""
    try:
        df = pd.read_csv(io.BytesIO(content), thousands=',')
    except Exception as e:
        logger.error(f"CSV read error: {e}")
        return datetime.now().strftime("%Y-%m-%d"), []

    # Normalize column names
    df.columns = [str(c).strip().lower() for c in df.columns]
    col_map = {}
    for c in df.columns:
        if c in ['date', 'transaction date', 'posting date', 'transaction_date']:
            col_map['date'] = c
        elif c in ['description', 'merchant', 'payee', 'transaction description', 'details']:
            col_map['description'] = c
        elif c in ['amount', 'transaction amount', 'amount ($)', 'amounts']:
            col_map['amount'] = c

    if not set(['date', 'description', 'amount']).issubset(col_map):
        if len(df.columns) >= 3:
            col_map = {'date': df.columns[0], 'description': df.columns[1], 'amount': df.columns[2]}
        else:
            logger.error("CSV missing required Date/Description/Amount columns")
            return datetime.now().strftime("%Y-%m-%d"), []

    # Parse dates - assume US MM/DD/YYYY first, then fallback to generic parser
    raw_dates = df[col_map['date']].astype(str).str.strip()
    parsed_dates = pd.to_datetime(raw_dates, format='%m/%d/%Y', errors='coerce')
    mask = parsed_dates.isna()
    if mask.any():
        parsed_dates[mask] = pd.to_datetime(raw_dates[mask], errors='coerce', dayfirst=False)

    # Parse amounts, strip $ and commas
    raw_amounts = df[col_map['amount']].astype(str).str.replace(r'[\$,]', '', regex=True)
    amounts = pd.to_numeric(raw_amounts, errors='coerce')

    transactions = []
    latest: Optional[datetime] = None
    for i in range(len(df)):
        d = parsed_dates.iloc[i]
        if pd.isna(d):
            continue
        amt = float(amounts.iloc[i]) if not pd.isna(amounts.iloc[i]) else 0.0
        if amt == 0:
            continue
        desc = str(df[col_map['description']].iloc[i]).strip()
        transactions.append({
            "date": d.strftime("%Y-%m-%d"),
            "description": desc,
            "amount": amt,
        })
        if latest is None or d > latest:
            latest = d

    report_date = latest.strftime("%Y-%m-%d") if latest else datetime.now().strftime("%Y-%m-%d")
    return report_date, transactions


def _parse_pdf(content: bytes) -> tuple[str, List[dict]]:
    """Parse PDF bank statement."""
    report_date = datetime.now().strftime("%Y-%m-%d")
    try:
        transactions = []
        full_text = ""
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
                # Extract tables from PDF
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        for row in table[1:]:  # Skip header
                            if len(row) >= 3:
                                transactions.append({
                                    "date": row[0],
                                    "description": row[1],
                                    "amount": float(row[2].replace("$", "").replace(",", "")),
                                })
        report_date = _extract_pdf_date(full_text)
        return report_date, transactions
    except Exception as e:
        logger.error(f"PDF parsing error: {e}")
        return report_date, []


def _categorize_transactions(transactions: List[dict]) -> List[Transaction]:
    """Categorize transactions using broader keyword matching."""
    categories = {
        "Phone/Internet/TV": ["spectrum", "mobile", "internet charge", "wind", "apple.com/bill", "platinum uber one credit", "uber one", "comcast", "at&t", "verizon", "t-mobile"],
        "E-commerce/Shopping": ["amazon", "aplpay", "clipp.com", "walmart", "target", "ebay", "etsy", "best buy"],
        "Dining": ["thai", "mcdonald", "taste of india", "restaurant", "grill", "cafe", "kitchen", "pizza", "sushi", "burger", "taco", "starbucks", "dunkin", "panera"],
        "Grocery": ["lowe's foods", "harris teeter", "grocery", "kroger", "safeway", "trader joe", "whole foods", "aldi", "publix", "food lion"],
        "Transport/Tolls": ["ezpass", "sunpass", "quick pass", "driveezmd", "tesla", "uber", "lyft", "lycatel", "shell", "exxon", "bp", "gas", "parking"],
        "Travel/Hotels": ["gaylord", "razorpay", "hotel", "resort", "airbnb", "booking", "expedia", "marriott", "hilton", "airlines", "flight"],
        "Government/Fees": ["gov*nc dmv", "dmv", "renewal membership fee", "irs", "tax", "renewal", "fee", "gov "],
        "Entertainment/Subscriptions": ["netflix", "spotify", "disney", "hulu", "hbo", "youtube", "membership", "subscription", "cinema"],
        "Utilities/Insurance": ["electric", "water", "gas", "city of", "utility", "insurance", "allstate", "state farm"],
        "Payments/Credits": ["online payment - thank you", "mobile payment - thank you", "payment - thank", "credit", "autopay", "bill pay"],
    }
    
    categorized = []
    for txn in transactions:
        desc = str(txn.get("description", "")).lower()
        category = "Other"
        
        for cat, keywords in categories.items():
            if any(kw in desc for kw in keywords):
                category = cat
                break
        
        categorized.append(Transaction(
            date=txn["date"],
            description=txn["description"],
            amount=txn["amount"],
            category=category,
        ))
    
    return categorized


def _flag_large_spends(transactions: List[Transaction], threshold: float = 500.0) -> List[Transaction]:
    """Flag large positive spends above threshold."""
    for txn in transactions:
        if txn.amount > threshold:
            txn.is_flagged = True
    return transactions


def _generate_summary(transactions: List[Transaction]) -> ExpenseReport:
    """Generate expense summary from spending only (positive amounts)."""
    spending = [t for t in transactions if t.amount > 0]
    total = sum(t.amount for t in spending)
    categories = {}
    for t in spending:
        categories[t.category] = categories.get(t.category, 0) + t.amount
    
    flagged = [t for t in transactions if t.is_flagged]
    
    return ExpenseReport(
        total_spent=total,
        transaction_count=len(spending),
        top_categories=dict(sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]),
        flagged_transactions=flagged,
    )


@router.get("/summary")
async def get_expense_summary(user_id: str = "default", user=Depends(get_current_user), db: AsyncSession = Depends(get_session)) -> dict:
    """Get expense summary for user (or member profile via user_id=member_<id>)."""
    user_id = await resolve_private_scope(user_id, user, db)
    txns = [t for t in transactions_store if t.get("user_id", "default") == user_id]
    if not txns:
        return {
            "total_spent": 0,
            "transaction_count": 0,
            "top_categories": {},
            "flagged_transactions": [],
        }
    spending = [t for t in txns if (t.get("amount") or 0) > 0]
    categories: Dict[str, float] = {}
    for t in spending:
        cat = t.get("category") or "Other"
        categories[cat] = categories.get(cat, 0) + t["amount"]
    return {
        "total_spent": round(sum(t["amount"] for t in spending), 2),
        "transaction_count": len(spending),
        "top_categories": dict(sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]),
        "flagged_transactions": [t for t in txns if t.get("is_flagged")],
    }


@router.get("/files")
async def list_finance_files(user_id: str = "default", user=Depends(get_current_user), db: AsyncSession = Depends(get_session)) -> dict:
    """List all uploaded financial documents."""
    user_id = await resolve_private_scope(user_id, user, db)
    storage = get_file_storage()
    files = storage.list_files(category="finance", user_id=user_id)
    return {
        "files": files,
        "count": len(files)
    }


_SUBSCRIPTION_HINTS = re.compile(
    r"spectrum|apple\.com|apple services|amazon prime|amazon digital|amzn|microsoft|msbill|"
    r"netflix|spotify|hulu|disney|hbo|youtube|uber one|windsurf|icloud|google storage|"
    r"openai|chatgpt|anthropic|claude|adobe|dropbox|audible|paramount|peacock|roblox|"
    r"gym|fitness|membership|subscription|monthly|patreon|substack|linkedin|x premium|"
    r"comcast|xfinity|at&t|verizon|t-mobile|internet|mobile|wireless|insurance|utility|utilities",
    re.I,
)


def _norm_merchant(desc: str) -> str:
    n = re.sub(r"[^a-z0-9 ]", " ", desc.lower())
    n = re.sub(r"\b\d{3,}\b", " ", n)
    n = re.sub(r"\b(inc|llc|co|corp|ltd)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def detect_recurring(user_id: str = "default") -> dict:
    """Detect recurring charges/subscriptions for a profile partition.

    user_id is the partition key: 'default' for the owner, 'member_<id>' for
    family member profiles.
    """
    txns = [t for t in transactions_store
            if (t.get("amount") or 0) > 0 and t.get("user_id", "default") == user_id]
    if not txns:
        return {"recurring": [], "count": 0}

    groups: Dict[str, List[dict]] = {}
    for t in txns:
        key = _norm_merchant(str(t.get("description", "")))
        if key:
            groups.setdefault(key, []).append(t)

    recurring = []
    for key, items in groups.items():
        desc = items[0].get("description", key)
        is_repeat = len(items) >= 2
        is_sub = bool(_SUBSCRIPTION_HINTS.search(desc))
        if not (is_repeat or is_sub):
            continue
        total = round(sum(float(t.get("amount", 0)) for t in items), 2)
        dates = sorted(t.get("date", "") for t in items)
        recurring.append({
            "merchant": re.sub(r"\s+", " ", desc).strip().title(),
            "count": len(items),
            "total": total,
            "avg": round(total / len(items), 2),
            "first": dates[0],
            "last": dates[-1],
            "category": items[0].get("category") or "Other",
            "likely_subscription": is_sub,
        })

    recurring.sort(key=lambda r: (not r["likely_subscription"], -r["total"]))
    return {"recurring": recurring, "count": len(recurring)}


@router.get("/recurring")
async def list_recurring(user_id: str = "default", user=Depends(get_current_user), db: AsyncSession = Depends(get_session)) -> dict:
    """List recurring charges/subscriptions for a profile."""
    return detect_recurring(await resolve_private_scope(user_id, user, db))


@router.post("/analyze")
async def analyze_financial_document(
    document_text: str,
    document_type: str = "bank_statement",
    user_id: str = "default"
) -> dict:
    """
    AI-powered financial document analysis with savings recommendations.
    
    Provides:
    - Document summary
    - Spending analysis
    - Savings opportunities
    - Budget recommendations
    - Financial health assessment
    
    DISCLAIMER: This is AI analysis for informational purposes only.
    Not professional financial advice.
    """
    from app.services.finance_analyzer import get_finance_analyzer
    from app.config import settings
    
    analyzer = get_finance_analyzer()
    analysis = await analyzer.analyze_financial_document(
        document_text=document_text,
        document_type=document_type,
        ollama_host=settings.ollama_host,
        ollama_model=settings.ollama_model
    )
    
    return analysis


@router.get("/budget-templates")
async def get_budget_templates(income_level: str = "moderate") -> dict:
    """Get budget templates based on income level."""
    from app.services.finance_analyzer import get_finance_analyzer
    
    analyzer = get_finance_analyzer()
    template = analyzer.get_budget_templates(income_level)
    
    return {
        "success": True,
        "template": template
    }


@router.post("/health-score")
async def calculate_financial_health(
    income: float,
    expenses: float,
    savings: float,
    debt: float
) -> dict:
    """Calculate financial health score."""
    from app.services.finance_analyzer import get_finance_analyzer
    analyzer = get_finance_analyzer()
    score = analyzer.calculate_financial_health_score(income, expenses, savings, debt)
    return {"success": True, "health_score": score}


# ── Financial Planner ────────────────────────────────────────────────────────

from pydantic import BaseModel as _BM

class _EmergencyFundReq(_BM):
    monthly_expenses: float
    months: int = 6

class _DebtPayoffReq(_BM):
    debts: List[Dict[str, Any]]
    extra_monthly: float = 0
    method: str = "avalanche"  # avalanche | snowball

class _RetirementReq(_BM):
    current_age: int
    retirement_age: int
    current_savings: float
    monthly_contribution: float
    annual_return: float = 0.07
    annual_inflation: float = 0.03

class _SavingsGoalReq(_BM):
    goal_amount: float
    current_saved: float = 0
    monthly_contribution: float
    annual_return: float = 0.05

class _NetWorthReq(_BM):
    assets: List[Dict[str, Any]]
    liabilities: List[Dict[str, Any]]
    years_ahead: int = 10

class _BudgetReq(_BM):
    annual_income: float

class _GoalReq(_BM):
    name: str
    target: float
    deadline: str  # YYYY-MM-DD
    monthly_allocation: float

class _GoalProgressReq(_BM):
    amount_saved: float


@router.post("/planner/emergency-fund")
async def planner_emergency_fund(body: _EmergencyFundReq):
    from app.services.financial_planner import emergency_fund_needed
    return {"success": True, **emergency_fund_needed(body.monthly_expenses, body.months)}


@router.post("/planner/debt-payoff")
async def planner_debt_payoff(body: _DebtPayoffReq):
    from app.services.financial_planner import debt_payoff
    return {"success": True, **debt_payoff(body.debts, body.extra_monthly, body.method)}


@router.post("/planner/retirement")
async def planner_retirement(body: _RetirementReq):
    from app.services.financial_planner import retirement_projection
    return {"success": True, **retirement_projection(
        body.current_age, body.retirement_age, body.current_savings,
        body.monthly_contribution, body.annual_return, body.annual_inflation
    )}


@router.post("/planner/savings-goal")
async def planner_savings_goal(body: _SavingsGoalReq):
    from app.services.financial_planner import savings_goal_timeline
    return {"success": True, **savings_goal_timeline(
        body.goal_amount, body.current_saved, body.monthly_contribution, body.annual_return
    )}


@router.post("/planner/net-worth")
async def planner_net_worth(body: _NetWorthReq):
    from app.services.financial_planner import net_worth_trajectory
    return {"success": True, "trajectory": net_worth_trajectory(
        body.assets, body.liabilities, body.years_ahead
    )}


@router.post("/planner/budget-503020")
async def planner_budget(body: _BudgetReq):
    from app.services.financial_planner import budget_503020
    return {"success": True, **budget_503020(body.annual_income)}


@router.post("/planner/goals")
async def planner_add_goal(body: _GoalReq):
    from app.services.financial_planner import add_goal
    return {"success": True, "goal": add_goal(body.name, body.target, body.deadline, body.monthly_allocation)}


@router.get("/planner/goals")
async def planner_list_goals():
    from app.services.financial_planner import list_goals
    return {"success": True, "goals": list_goals()}


@router.patch("/planner/goals/{goal_id}")
async def planner_update_goal(goal_id: str, body: _GoalProgressReq):
    from app.services.financial_planner import update_goal_progress
    g = update_goal_progress(goal_id, body.amount_saved)
    if not g:
        raise HTTPException(404, "Goal not found")
    return {"success": True, "goal": g}


@router.delete("/planner/goals/{goal_id}")
async def planner_delete_goal(goal_id: str):
    from app.services.financial_planner import delete_goal
    if not delete_goal(goal_id):
        raise HTTPException(404, "Goal not found")
    return {"success": True, "deleted": goal_id}


@router.post("/planner/summary")
async def planner_summary(
    income: float, expenses: float, savings: float, debt: float,
    current_age: int = 35, retirement_age: int = 65,
    monthly_contribution: float = 500
):
    """Full financial plan summary with LLM narrative."""
    from app.services.financial_planner import (
        emergency_fund_needed, budget_503020, retirement_projection,
        calculate_financial_health_score, generate_plan_narrative
    )
    monthly_expenses = expenses / 12 if expenses > 0 else 0
    e_fund = emergency_fund_needed(monthly_expenses)
    budget = budget_503020(income)
    health = calculate_financial_health_score(income, expenses, savings, debt)
    retirement = retirement_projection(current_age, retirement_age, savings, monthly_contribution)
    context = {
        "annual_income": income, "annual_expenses": expenses,
        "current_savings": savings, "total_debt": debt,
        "health_score": health, "emergency_fund": e_fund,
        "budget_503020": budget, "retirement_projection": retirement,
    }
    narrative = await generate_plan_narrative(context)
    return {
        "success": True,
        "emergency_fund": e_fund,
        "budget": budget,
        "health_score": health,
        "retirement": retirement,
        "narrative": narrative,
    }


@router.get("/history")
async def list_finance_history(user_id: str = "default", user=Depends(get_current_user), db: AsyncSession = Depends(get_session)) -> dict:
    """List all uploaded bank statement summaries, sorted by statement date."""
    user_id = await resolve_private_scope(user_id, user, db)
    docs = [r for r in finance_reports_store if r.get("user_id") == user_id]
    docs.sort(key=lambda r: r.get("report_date") or r.get("uploaded_at", ""))
    return {
        "success": True,
        "history": docs[-20:],
        "count": len(docs),
    }


@router.delete("/history/{report_id}")
async def delete_finance_report(report_id: str, user_id: str = "default", user=Depends(get_current_user), db: AsyncSession = Depends(get_session)) -> dict:
    """Delete a finance report and its stored files."""
    global finance_reports_store, transactions_store
    user_id = await resolve_private_scope(user_id, user, db)
    idx = next((i for i, r in enumerate(finance_reports_store) if r.get("id") == report_id and r.get("user_id") == user_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Report not found")

    report = finance_reports_store.pop(idx)
    storage = get_file_storage()
    for file_id in report.get("file_ids", []):
        try:
            storage.delete_file(file_id)
        except Exception as e:
            logger.warning(f"Failed to delete finance file {file_id}: {e}")

    # Rebuild in-memory transactions from remaining reports
    transactions_store = [t for r in finance_reports_store for t in r.get("transactions", [])]
    _save_finance_state()

    return {"success": True, "deleted": report_id}
