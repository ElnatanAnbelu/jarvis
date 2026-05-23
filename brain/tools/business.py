"""Business tools — Nexel CRM, financials, marketing."""
from brain.tools.registry import tool


@tool(description="Register a new business under the Nexel empire.", parameters={"name": {"type": "string", "description": "Business name"}, "type": {"type": "string", "description": "Business type"}, "stage": {"type": "string", "description": "idea | mvp | growth | scaling | profitable"}, "description": {"type": "string", "description": "What the business does"}, "revenue_model": {"type": "string", "description": "How it makes money"}, "founded": {"type": "string", "description": "Founding date YYYY-MM-DD"}, "mrr": {"type": "number", "description": "Monthly recurring revenue in USD"}})
def add_business(name: str, type: str = "", stage: str = "idea", description: str = "", revenue_model: str = "", founded: str = "", mrr: float = 0) -> str:
    from control.business_tools import tool_add_business
    return tool_add_business(name, type, stage, description, revenue_model, founded, mrr)


@tool(description="Update an existing business's details — stage, MRR, description, etc.", parameters={"name": {"type": "string", "description": "Business name"}, "stage": {"type": "string", "description": "New stage"}, "mrr": {"type": "number", "description": "New MRR"}, "description": {"type": "string", "description": "New description"}, "revenue_model": {"type": "string", "description": "New revenue model"}, "type": {"type": "string", "description": "New type"}})
def update_business(name: str, **kwargs) -> str:
    from control.business_tools import tool_update_business
    return tool_update_business(name, **kwargs)


@tool(description="Get the full profile of a business — team, goals, KPIs, stage, financials summary.", parameters={"name": {"type": "string", "description": "Business name"}})
def get_business(name: str) -> str:
    from control.business_tools import tool_get_business
    return tool_get_business(name)


@tool(description="Show the full Nexel empire overview — all businesses, their stage, MRR, and combined P&L.", parameters={})
def nexel_overview() -> str:
    from control.business_tools import tool_nexel_overview
    return tool_nexel_overview()


@tool(description="Add a team member to a business.", parameters={"business": {"type": "string", "description": "Business name"}, "name": {"type": "string", "description": "Person's name"}, "role": {"type": "string", "description": "Their role"}})
def add_team_member(business: str, name: str, role: str = "") -> str:
    from control.business_tools import tool_add_team_member
    return tool_add_team_member(business, name, role)


@tool(description="Add an active goal or milestone to a business.", parameters={"business": {"type": "string"}, "title": {"type": "string", "description": "Goal title"}, "description": {"type": "string"}, "target_date": {"type": "string", "description": "YYYY-MM-DD"}})
def add_business_goal(business: str, title: str, description: str = "", target_date: str = "") -> str:
    from control.business_tools import tool_add_goal
    return tool_add_goal(business, title, description, target_date)


@tool(description="Mark a business goal as completed.", parameters={"business": {"type": "string"}, "title": {"type": "string", "description": "Goal title (partial match)"}})
def complete_goal(business: str, title: str) -> str:
    from control.business_tools import tool_complete_goal
    return tool_complete_goal(business, title)


@tool(description="Define a KPI and its target for a business.", parameters={"business": {"type": "string"}, "kpi_name": {"type": "string", "description": "KPI name e.g. 'Vendors Onboarded'"}, "target": {"type": "number", "description": "Target value"}, "unit": {"type": "string", "description": "Unit label e.g. 'vendors'"}, "period": {"type": "string", "description": "daily | weekly | monthly"}, "current": {"type": "number", "description": "Current value"}})
def set_kpi(business: str, kpi_name: str, target: float, unit: str = "", period: str = "monthly", current: float = 0) -> str:
    from control.business_tools import tool_set_kpi
    return tool_set_kpi(business, kpi_name, target, unit, period, current)


@tool(description="Update the current value of a KPI for a business.", parameters={"business": {"type": "string"}, "kpi_name": {"type": "string"}, "current": {"type": "number", "description": "New current value"}})
def update_kpi(business: str, kpi_name: str, current: float) -> str:
    from control.business_tools import tool_update_kpi
    return tool_update_kpi(business, kpi_name, current)


@tool(description="Show all KPIs for a business with progress bars and on-target status.", parameters={"business": {"type": "string"}})
def kpi_report(business: str) -> str:
    from control.business_tools import tool_kpi_report
    return tool_kpi_report(business)


@tool(description="Add a business contact to the CRM — investor, vendor, customer, partner, or advisor.", parameters={"business": {"type": "string"}, "name": {"type": "string"}, "role": {"type": "string", "description": "investor | vendor | customer | partner | advisor"}, "company": {"type": "string"}, "email": {"type": "string"}, "phone": {"type": "string"}, "notes": {"type": "string"}, "pipeline_stage": {"type": "string", "description": "lead | contacted | negotiating | closed"}})
def add_contact(business: str, name: str, role: str = "", company: str = "", email: str = "", phone: str = "", notes: str = "", pipeline_stage: str = "lead") -> str:
    from control.business_tools import tool_add_contact
    return tool_add_contact(business, name, role, company, email, phone, notes, pipeline_stage)


@tool(description="Log a meeting, call, email, or message with a business contact.", parameters={"contact_name": {"type": "string"}, "interaction_type": {"type": "string", "description": "meeting | call | email | message | deal"}, "notes": {"type": "string", "description": "What was discussed"}, "business": {"type": "string"}, "date_str": {"type": "string", "description": "YYYY-MM-DD"}})
def log_interaction(contact_name: str, interaction_type: str, notes: str, business: str = "", date_str: str = "") -> str:
    from control.business_tools import tool_log_interaction
    return tool_log_interaction(contact_name, interaction_type, notes, business, date_str)


@tool(description="Move a contact to a new pipeline stage.", parameters={"contact_name": {"type": "string"}, "stage": {"type": "string", "description": "lead | contacted | negotiating | closed | churned"}})
def update_pipeline(contact_name: str, stage: str) -> str:
    from control.business_tools import tool_update_pipeline
    return tool_update_pipeline(contact_name, stage)


@tool(description="Set a follow-up reminder date for a contact.", parameters={"contact_name": {"type": "string"}, "follow_up_date": {"type": "string", "description": "YYYY-MM-DD"}})
def set_follow_up(contact_name: str, follow_up_date: str) -> str:
    from control.business_tools import tool_set_follow_up
    return tool_set_follow_up(contact_name, follow_up_date)


@tool(description="Show the full deal pipeline — all contacts grouped by stage.", parameters={"business": {"type": "string", "description": "Filter by business (optional)"}})
def show_pipeline(business: str = "") -> str:
    from control.business_tools import tool_show_pipeline
    return tool_show_pipeline(business)


@tool(description="Show contacts who need a follow-up — overdue or not contacted in N days.", parameters={"days_since": {"type": "integer", "description": "Flag contacts not touched in this many days (default: 14)"}})
def follow_ups_due(days_since: int = 14) -> str:
    from control.business_tools import tool_follow_ups_due
    return tool_follow_ups_due(days_since)


@tool(description="Show the full interaction history with a contact.", parameters={"contact_name": {"type": "string"}, "limit": {"type": "integer", "description": "Max entries to show"}})
def contact_history(contact_name: str, limit: int = 10) -> str:
    from control.business_tools import tool_contact_history
    return tool_contact_history(contact_name, limit)


@tool(description="Log a revenue entry for a business.", parameters={"business": {"type": "string"}, "amount": {"type": "number", "description": "Amount in USD"}, "category": {"type": "string", "description": "e.g. subscription, commission, one-time"}, "date_str": {"type": "string", "description": "YYYY-MM-DD"}, "notes": {"type": "string"}})
def log_revenue(business: str, amount: float, category: str = "", date_str: str = "", notes: str = "") -> str:
    from control.business_tools import tool_log_revenue
    return tool_log_revenue(business, amount, category, date_str, notes)


@tool(description="Log an expense for a business.", parameters={"business": {"type": "string"}, "amount": {"type": "number", "description": "Amount in USD"}, "category": {"type": "string", "description": "e.g. hosting, marketing, salaries"}, "date_str": {"type": "string", "description": "YYYY-MM-DD"}, "notes": {"type": "string"}})
def log_expense(business: str, amount: float, category: str = "", date_str: str = "", notes: str = "") -> str:
    from control.business_tools import tool_log_expense
    return tool_log_expense(business, amount, category, date_str, notes)


@tool(description="Show revenue, expenses, and profit for a business.", parameters={"business": {"type": "string"}, "period": {"type": "string", "description": "month | year | all"}})
def financial_summary(business: str, period: str = "month") -> str:
    from control.business_tools import tool_financial_summary
    return tool_financial_summary(business, period)


@tool(description="Show consolidated P&L across all Nexel businesses.", parameters={})
def nexel_financials() -> str:
    from control.business_tools import tool_nexel_financials
    return tool_nexel_financials()


@tool(description="Show cash flow projection for a business — average burn, net monthly, status.", parameters={"business": {"type": "string"}})
def cash_flow(business: str) -> str:
    from control.business_tools import tool_cash_flow
    return tool_cash_flow(business)


@tool(description="Generate the full business briefing — all active businesses, KPI status, follow-ups due, and Nexel P&L snapshot.", parameters={})
def business_briefing() -> str:
    from control.business_tools import business_briefing as _run
    return _run()


@tool(description="Calculate estimated taxes for a business based on annual profit.", parameters={"business": {"type": "string"}, "tax_rate_pct": {"type": "number", "description": "Tax rate percentage (default: 30)"}})
def tax_estimate(business: str, tax_rate_pct: float = 30.0) -> str:
    from control.business_tools import tool_tax_estimate
    return tool_tax_estimate(business, tax_rate_pct)


@tool(description="Export all financial records for a business to an Excel file for an accountant.", parameters={"business": {"type": "string"}, "output_path": {"type": "string", "description": "Custom save path (optional)"}})
def export_for_accountant(business: str, output_path: str = "") -> str:
    from control.business_tools import tool_export_for_accountant
    return tool_export_for_accountant(business, output_path)


@tool(description="Generate ad copy variants for a product on a specific platform.", parameters={"product": {"type": "string"}, "platform": {"type": "string", "description": "meta | tiktok | google | twitter | linkedin | telegram | instagram"}, "audience": {"type": "string"}, "tone": {"type": "string", "description": "confident | friendly | urgent | professional"}, "goal": {"type": "string", "description": "sign-ups | sales | awareness | downloads"}, "variants": {"type": "integer", "description": "Number of variants (default: 3)"}, "context": {"type": "string"}})
def generate_ad_copy(product: str, platform: str, audience: str = "", tone: str = "confident", goal: str = "sign-ups", variants: int = 3, context: str = "") -> str:
    from control.marketing import generate_ad_copy as _run
    return _run(product, platform, audience, tone, goal, variants, context)


@tool(description="Generate a weekly social media content calendar with ready-to-post captions and hashtags.", parameters={"business": {"type": "string"}, "platform": {"type": "string", "description": "instagram | twitter | tiktok | linkedin | telegram"}, "posts": {"type": "integer", "description": "Number of posts (default: 7)"}, "content_pillars": {"type": "string"}, "brand_voice": {"type": "string"}})
def social_media_calendar(business: str, platform: str = "instagram", posts: int = 7, content_pillars: str = "", brand_voice: str = "") -> str:
    from control.marketing import social_media_calendar as _run
    return _run(business, platform, posts, content_pillars, brand_voice)


@tool(description="Generate a complete marketing campaign strategy — concept, channels, timeline, metrics, A/B tests.", parameters={"business": {"type": "string"}, "goal": {"type": "string", "description": "Campaign goal"}, "budget_usd": {"type": "number"}, "duration_days": {"type": "integer"}, "channels": {"type": "string"}, "context": {"type": "string"}})
def campaign_strategy(business: str, goal: str, budget_usd: float = 0, duration_days: int = 30, channels: str = "", context: str = "") -> str:
    from control.marketing import campaign_strategy as _run
    return _run(business, goal, budget_usd, duration_days, channels, context)


@tool(description="Write an investor pitch, vendor proposal, client proposal, one-pager, or executive summary.", parameters={"business": {"type": "string"}, "type": {"type": "string", "description": "investor | vendor | partner | client | one_pager | executive_summary"}, "ask": {"type": "string"}, "context": {"type": "string"}})
def pitch_writer(business: str, type: str = "investor", ask: str = "", context: str = "") -> str:
    from control.marketing import pitch_writer as _run
    return _run(business, type, context, ask)


@tool(description="Research a market, trend, or topic and synthesize the findings into a sharp analysis.", parameters={"topic": {"type": "string"}, "business": {"type": "string", "description": "Related business for context (optional)"}})
def market_research(topic: str, business: str = "") -> str:
    from control.marketing import market_research as _run
    return _run(topic, business)


@tool(description="Generate a strategic review for a business using real KPI, financial, and market data.", parameters={"business": {"type": "string"}, "question": {"type": "string", "description": "Specific strategic question (optional)"}})
def strategic_review(business: str, question: str = "") -> str:
    from control.marketing import strategic_review as _run
    return _run(business, question)


@tool(description="Research a specific competitor and return intelligence on their pricing, features, funding, and how to compete.", parameters={"business": {"type": "string", "description": "Your business"}, "competitor": {"type": "string", "description": "Competitor name or description"}})
def competitor_scan(business: str, competitor: str) -> str:
    from control.marketing import competitor_scan as _run
    return _run(business, competitor)
