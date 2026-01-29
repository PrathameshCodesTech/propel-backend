"""
AI-powered analytics ask endpoint using Gemini.
"""
import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from analytics.gemini_client import ask_gemini, get_last_gemini_error
from analytics.analytics_executor import run_plan, extract_json
from analytics.models import FieldCatalog
from .views import get_org


PLANNER_SYSTEM = """You are a query planner for a real estate analytics system. 
Given a user's question, generate a JSON plan to answer it.

IMPORTANT: Understand the question intent:
- Questions about "how many employees" → use "employee" dataset with empty metrics (count)
- Questions about "total revenue" → use "org_kpi" dataset with "revenue_booked" metric
- Questions about "marketing campaigns" → use "marketing_campaign" dataset
- Questions about "customers" → use "customer" dataset
- Questions about "projects" → use "project" dataset
- Questions about "bookings" → use "booking" dataset

Available datasets:
- marketing_campaign: Marketing campaigns with spend, leads, bookings, ROI
- location_demand: Location-wise demand metrics (enquiries, bookings, demand_score)
- org_kpi: Organization-level KPIs (revenue_booked, revenue_collected, outstanding, etc.)
- project_kpi: Project-level KPIs (units, revenue, construction_percent)
- customer: Customer records with status, project, channel
- booking: Booking records with booking_value, booking_date, project, customer
- project: Projects with name, location, status, budget
- unit: Units with status, price, project
- employee: Employee records with role, department, organization, employee_code

Return ONLY valid JSON with this structure:
{
  "dataset": "dataset_name",
  "metrics": ["metric_field_key1", "metric_field_key2"],
  "dimensions": ["dimension_field_key1"],
  "filters": {"field_key": "value"},
  "chart_type": "bar|line|pie|table|answer",
  "limit": 50
}

Rules:
- Use "answer" chart_type for simple questions like "what's my total revenue?" (no dimensions, no chart needed)
- Use "bar", "line", or "pie" for comparisons/breakdowns when user asks for charts
- When user asks for "pie chart", "bar graph", "line chart" → ALWAYS include at least one dimension
- For pie/bar/line charts: if no metrics specified, use empty metrics array (will count by dimension)
- For "units" or "portfolio units" → group by "status" or "project__name" dimension
- For "employees" → group by "role" or "department" dimension
- For "customers" → group by "status" or "channel" dimension
- Always include organization filter (will be added automatically)
- Limit should be <= 50
- Metrics are numeric fields to aggregate (Sum/Avg). Can be empty for count-based charts
- Dimensions are fields to group by - REQUIRED for pie/bar/line charts
- Filters are exact matches (date filters use ISO format YYYY-MM-DD)

Example for "what's my total revenue?":
{
  "dataset": "org_kpi",
  "metrics": ["revenue_booked"],
  "dimensions": [],
  "filters": {},
  "chart_type": "answer",
  "limit": 1
}

Example for "show me marketing campaigns by channel":
{
  "dataset": "marketing_campaign",
  "metrics": ["spend"],
  "dimensions": ["channel"],
  "filters": {},
  "chart_type": "pie",
  "limit": 20
}

Example for "how many employees are there?":
{
  "dataset": "employee",
  "metrics": [],
  "dimensions": [],
  "filters": {},
  "chart_type": "answer",
  "limit": 1
}

Example for "show employees by role":
{
  "dataset": "employee",
  "metrics": [],
  "dimensions": ["role"],
  "filters": {},
  "chart_type": "bar",
  "limit": 50
}

Example for "Portfolio Units give this in pie chart" or "show units in pie chart":
{
  "dataset": "unit",
  "metrics": [],
  "dimensions": ["status"],
  "filters": {},
  "chart_type": "pie",
  "limit": 50
}

Example for "show units by project in bar graph":
{
  "dataset": "unit",
  "metrics": [],
  "dimensions": ["project__name"],
  "filters": {},
  "chart_type": "bar",
  "limit": 50
}

Example for "show revenue by project in line chart":
{
  "dataset": "project_kpi",
  "metrics": ["revenue_booked"],
  "dimensions": ["project__name"],
  "filters": {},
  "chart_type": "line",
  "limit": 50
}

Example for "show customers by status in pie chart":
{
  "dataset": "customer",
  "metrics": [],
  "dimensions": ["status"],
  "filters": {},
  "chart_type": "pie",
  "limit": 50
}

Example for "Show me projects in a pie chart":
{
  "dataset": "project",
  "metrics": [],
  "dimensions": ["status"],
  "filters": {},
  "chart_type": "pie",
  "limit": 50
}

Example for "show projects by name in pie chart":
{
  "dataset": "project",
  "metrics": [],
  "dimensions": ["name"],
  "filters": {},
  "chart_type": "pie",
  "limit": 50
}"""


def get_schema_for_gemini() -> str:
    """Build schema string from FieldCatalog for Gemini prompt."""
    datasets = {}
    for field in FieldCatalog.objects.filter(is_enabled=True).order_by("dataset", "label"):
        if field.dataset not in datasets:
            datasets[field.dataset] = []
        datasets[field.dataset].append({
            "key": field.key,
            "label": field.label,
            "type": field.data_type,
            "synonyms": field.synonyms.split(",") if field.synonyms else [],
        })
    
    schema_parts = []
    for dataset, fields in datasets.items():
        schema_parts.append(f"\n{dataset}:")
        for f in fields[:50]:  # Limit per dataset
            synonyms_str = f" (synonyms: {', '.join(f['synonyms'][:3])})" if f['synonyms'] else ""
            schema_parts.append(f"  - {f['key']} ({f['type']}): {f['label']}{synonyms_str}")
    
    return "\n".join(schema_parts)


class AskAPIView(APIView):
    """
    POST /api/analytics/ask/
    Natural language query → Gemini plan → Execute → Return chart/table/answer.
    Requires authentication + org admin (user must have employee_profile.organization).
    """
    permission_classes = [IsAuthenticated]

    def _create_fallback_plan(self, prompt_lower: str) -> dict:
        """Create a smart fallback plan based on keywords in the prompt."""
        # Detect chart type request
        chart_type = "answer"
        if "pie" in prompt_lower or "pie chart" in prompt_lower:
            chart_type = "pie"
        elif "bar" in prompt_lower or "bar chart" in prompt_lower:
            chart_type = "bar"
        elif "line" in prompt_lower or "line chart" in prompt_lower or "trend" in prompt_lower:
            chart_type = "line"
        elif "table" in prompt_lower or "list" in prompt_lower or "show" in prompt_lower:
            chart_type = "table"

        # Detect dataset and create appropriate plan
        if any(word in prompt_lower for word in ["employee", "staff", "team", "people", "worker"]):
            if any(word in prompt_lower for word in ["by role", "by department", "breakdown"]):
                return {"dataset": "employee", "metrics": [], "dimensions": ["role"], "filters": {}, "chart_type": chart_type if chart_type != "answer" else "bar", "limit": 50}
            return {"dataset": "employee", "metrics": [], "dimensions": [], "filters": {}, "chart_type": "answer", "limit": 1}

        elif any(word in prompt_lower for word in ["customer", "client", "buyer"]):
            if any(word in prompt_lower for word in ["by status", "breakdown", "by stage"]):
                return {"dataset": "customer", "metrics": [], "dimensions": ["status"], "filters": {}, "chart_type": chart_type if chart_type != "answer" else "pie", "limit": 50}
            return {"dataset": "customer", "metrics": [], "dimensions": [], "filters": {}, "chart_type": "answer", "limit": 1}

        elif any(word in prompt_lower for word in ["project", "development", "site"]):
            if any(word in prompt_lower for word in ["by status", "breakdown"]):
                return {"dataset": "project", "metrics": [], "dimensions": ["status"], "filters": {}, "chart_type": chart_type if chart_type != "answer" else "pie", "limit": 50}
            if "list" in prompt_lower or "show" in prompt_lower or "all" in prompt_lower or "graph" in prompt_lower or "chart" in prompt_lower:
                # Respect bar/pie/line from prompt; default bar for "show projects"
                return {"dataset": "project", "metrics": [], "dimensions": ["name"], "filters": {}, "chart_type": chart_type if chart_type != "answer" else "bar", "limit": 50}
            return {"dataset": "project", "metrics": [], "dimensions": [], "filters": {}, "chart_type": "answer", "limit": 1}

        elif any(word in prompt_lower for word in ["booking", "booked", "reservation"]):
            if any(word in prompt_lower for word in ["by project", "breakdown"]):
                return {"dataset": "booking", "metrics": ["booking_value"], "dimensions": ["project"], "filters": {}, "chart_type": chart_type if chart_type != "answer" else "bar", "limit": 50}
            return {"dataset": "booking", "metrics": ["booking_value"], "dimensions": [], "filters": {}, "chart_type": "answer", "limit": 1}

        elif any(word in prompt_lower for word in ["unit", "flat", "apartment", "inventory"]):
            if any(word in prompt_lower for word in ["by status", "breakdown"]):
                return {"dataset": "unit", "metrics": [], "dimensions": ["status"], "filters": {}, "chart_type": chart_type if chart_type != "answer" else "pie", "limit": 50}
            return {"dataset": "unit", "metrics": [], "dimensions": [], "filters": {}, "chart_type": "answer", "limit": 1}

        elif any(word in prompt_lower for word in ["marketing", "campaign", "ads", "advertising"]):
            if any(word in prompt_lower for word in ["by channel", "breakdown"]):
                return {"dataset": "marketing_campaign", "metrics": ["spend"], "dimensions": ["channel"], "filters": {}, "chart_type": chart_type if chart_type != "answer" else "pie", "limit": 50}
            return {"dataset": "marketing_campaign", "metrics": ["spend", "leads", "bookings"], "dimensions": [], "filters": {}, "chart_type": "answer", "limit": 1}

        elif any(word in prompt_lower for word in ["revenue", "sales", "income", "money"]):
            return {"dataset": "org_kpi", "metrics": ["revenue_booked", "revenue_collected"], "dimensions": [], "filters": {}, "chart_type": "answer", "limit": 1}

        # Default fallback
        return {"dataset": "org_kpi", "metrics": ["revenue_booked"], "dimensions": [], "filters": {}, "chart_type": "answer", "limit": 1}

    def _apply_chart_type_from_prompt(self, prompt_lower: str, plan: dict) -> None:
        """Override plan['chart_type'] from user's words (bar graph → bar, pie chart → pie)."""
        dimensions = plan.get("dimensions", [])
        # Explicit chart type from user
        if "pie chart" in prompt_lower or " pie " in prompt_lower or prompt_lower.strip().startswith("pie "):
            plan["chart_type"] = "pie"
        elif "bar graph" in prompt_lower or "bar chart" in prompt_lower or ("bar" in prompt_lower and "chart" in prompt_lower):
            plan["chart_type"] = "bar"
        elif "line chart" in prompt_lower or "line graph" in prompt_lower or ("line" in prompt_lower and "chart" in prompt_lower):
            plan["chart_type"] = "line"
        # Default when dimensions exist but plan said table/answer
        elif dimensions and plan.get("chart_type") in ("table", "answer"):
            plan["chart_type"] = "pie"

    def post(self, request):
        prompt = request.data.get("prompt", "").strip()
        if not prompt:
            return Response({"error": "Prompt is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get org from authenticated user
        org = get_org(request)
        if not org:
            return Response(
                {"error": "No organization mapped to user. Org admin access required."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Handle simple greetings/help without LLM
        prompt_lower = prompt.lower()
        if prompt_lower in ("hi", "hello", "help", "what can you do?"):
            return Response({
                "prompt": prompt,
                "plan": None,
                "answer": "I can help you analyze your organization's data. Try asking:\n- 'What's my total revenue?'\n- 'Show me marketing campaigns by channel'\n- 'List my top projects by revenue'\n- 'What's my total bookings this month?'",
                "chart": None,
                "table": None,
            })
        
        # Build schema for Gemini
        schema = get_schema_for_gemini()
        full_system_prompt = f"{PLANNER_SYSTEM}\n\nAvailable fields:{schema}"
        
        # Call Gemini
        gemini_response = ask_gemini(prompt, full_system_prompt)
        if not gemini_response:
            # Smart fallback when Gemini fails; include reason so user can fix (e.g. install package, set API key)
            gemini_error = get_last_gemini_error()
            fallback_plan = self._create_fallback_plan(prompt_lower)
            self._apply_chart_type_from_prompt(prompt_lower, fallback_plan)
            result = run_plan(fallback_plan, org)
            return Response({
                "prompt": prompt,
                "plan": fallback_plan,
                "answer": result.get("answer", "Unable to process query. Please try rephrasing."),
                "chart": result.get("chart"),
                "table": result.get("table"),
                "gemini_failed": True,
                "gemini_error": gemini_error,
            })
        
        # Extract JSON plan
        plan = extract_json(gemini_response)
        if not plan:
            return Response({
                "prompt": prompt,
                "plan": None,
                "answer": "Could not parse query plan. Please try rephrasing.",
                "chart": None,
                "table": None,
            })
        
        # Fix chart_type from user's words (bar graph → bar, pie chart → pie)
        self._apply_chart_type_from_prompt(prompt_lower, plan)
        
        # Execute plan
        try:
            result = run_plan(plan, org)
            print(f"DEBUG ask_views: Result chart: {result.get('chart')}")
            print(f"DEBUG ask_views: Result keys: {result.keys()}")
            return Response({
                "prompt": prompt,
                "plan": plan,
                "answer": result.get("answer", "Query executed successfully."),
                "chart": result.get("chart"),
                "table": result.get("table"),
            })
        except Exception as e:
            return Response({
                "prompt": prompt,
                "plan": plan,
                "answer": f"Error executing query: {str(e)}",
                "chart": None,
                "table": None,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SchemaAPIView(APIView):
    """
    GET /api/analytics/schema/
    Returns available fields/datasets for frontend schema display.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        datasets = {}
        for field in FieldCatalog.objects.filter(is_enabled=True).order_by("dataset", "label"):
            if field.dataset not in datasets:
                datasets[field.dataset] = []
            datasets[field.dataset].append({
                "key": field.key,
                "label": field.label,
                "type": field.data_type,
                "synonyms": [s.strip() for s in field.synonyms.split(",") if s.strip()] if field.synonyms else [],
            })
        
        return Response({"datasets": datasets})
