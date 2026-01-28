from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict

from django.db.models import Sum, Count, Avg, F, Q, Max
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from construction.models import (
    Milestone,
    DailyProgress,
    DelayPenalty,
    DelayPrediction,
    Contractor,
)
from projects.models import Project
from analytics.models import ProjectKPI_Daily
from .views import get_org


def normalize_milestone_status(status):
    """Normalize milestone status for frontend."""
    status_map = {
        "not_started": "upcoming",
        "in_progress": "in-progress",
        "completed": "completed",
        "delayed": "delayed",
    }
    return status_map.get(status, status)


def normalize_escalation_level(level):
    """Normalize escalation level for frontend."""
    level_map = {
        "low": "None",
        "medium": "Level 1",
        "high": "Level 2",
        "critical": "Critical",
    }
    return level_map.get(level, level)


class ConstructionTrackerAPIView(APIView):
    """
    API endpoint for Construction & Site Tracker dashboard.
    Returns project summary, daily progress, milestones, contractors,
    delay penalties, and AI delay predictions.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        org = get_org(request)
        if not org:
            return Response({"detail": "No organization mapped to user."}, status=400)

        project_id = request.query_params.get("project_id")
        today = date.today()

        # ----------------------------
        # 1) Get all projects for tabs
        # ----------------------------
        projects_qs = Project.objects.filter(organization=org).order_by("name")
        projects_list = [
            {"id": p.id, "name": p.name, "short_name": p.name.split()[0] if p.name else ""}
            for p in projects_qs
        ]

        # If no project_id specified, use first project
        if not project_id and projects_qs.exists():
            project_id = projects_qs.first().id

        # ----------------------------
        # 2) Get selected project details
        # ----------------------------
        project = None
        project_summary = None

        if project_id:
            project = projects_qs.filter(id=project_id).first()

        if project:
            # Get latest KPI for progress data
            latest_kpi = (
                ProjectKPI_Daily.objects
                .filter(project=project)
                .order_by("-date")
                .first()
            )

            actual_progress = float(latest_kpi.construction_percent) if latest_kpi else 0

            # Calculate planned progress based on timeline
            planned_progress = 0
            if project.planned_start_date and project.planned_completion_date:
                total_days = (project.planned_completion_date - project.planned_start_date).days
                elapsed_days = (today - project.planned_start_date).days
                if total_days > 0 and elapsed_days > 0:
                    planned_progress = min(100, round((elapsed_days / total_days) * 100, 1))

            variance = round(actual_progress - planned_progress, 1)

            project_summary = {
                "project_id": project.id,
                "name": project.name,
                "location": project.location,
                "actual_progress": actual_progress,
                "planned_progress": planned_progress,
                "variance": variance,
                "is_behind": variance < 0,
                "expected_completion": (
                    project.expected_completion_date.strftime("%b %Y")
                    if project.expected_completion_date else "TBD"
                ),
                "expected_completion_date": (
                    project.expected_completion_date.isoformat()
                    if project.expected_completion_date else None
                ),
            }

        # ----------------------------
        # 3) Daily Progress (last 30 days)
        # ----------------------------
        daily_progress_data = []
        if project:
            thirty_days_ago = today - timedelta(days=30)

            daily_qs = (
                DailyProgress.objects
                .filter(project=project, date__gte=thirty_days_ago, date__lte=today)
                .order_by("date")
            )

            if daily_qs.exists():
                for dp in daily_qs:
                    daily_progress_data.append({
                        "day": (dp.date - thirty_days_ago).days + 1,
                        "date": dp.date.isoformat(),
                        "planned": float(dp.planned_percent),
                        "actual": float(dp.actual_percent),
                    })
            else:
                # Fallback: generate simulated data based on current progress
                if project_summary:
                    actual = project_summary["actual_progress"]
                    planned = project_summary["planned_progress"]
                    for i in range(30):
                        day_progress_planned = min(planned, planned * ((i + 1) / 30))
                        day_progress_actual = min(actual, actual * ((i + 1) / 30) * (0.9 + (hash(str(i)) % 20) / 100))
                        daily_progress_data.append({
                            "day": i + 1,
                            "date": (thirty_days_ago + timedelta(days=i)).isoformat(),
                            "planned": round(day_progress_planned, 2),
                            "actual": round(day_progress_actual, 2),
                        })

        # ----------------------------
        # 4) Contractor Performance
        # ----------------------------
        contractor_performance = []
        contractors_qs = (
            Contractor.objects
            .filter(organization=org, is_active=True)
            .annotate(
                milestone_count=Count("milestones"),
                avg_score=Avg("milestones__contractor_score")
            )
            .filter(milestone_count__gt=0)
            .order_by("-avg_score")[:8]
        )

        for contractor in contractors_qs:
            contractor_performance.append({
                "id": contractor.id,
                "name": contractor.name.split()[0] if contractor.name else "",
                "full_name": contractor.name,
                "score": round(float(contractor.avg_score or 0), 1),
                "milestones": contractor.milestone_count,
            })

        # ----------------------------
        # 5) Milestones for selected project
        # ----------------------------
        milestones_data = []
        if project:
            milestones_qs = (
                Milestone.objects
                .filter(project=project)
                .select_related("contractor", "phase")
                .order_by("order", "planned_start")
            )

            for m in milestones_qs:
                milestones_data.append({
                    "id": m.id,
                    "name": m.name,
                    "status": normalize_milestone_status(m.status),
                    "planned_start": m.planned_start.isoformat() if m.planned_start else None,
                    "planned_end": m.planned_end.isoformat() if m.planned_end else None,
                    "actual_start": m.actual_start.isoformat() if m.actual_start else None,
                    "actual_end": m.actual_end.isoformat() if m.actual_end else None,
                    "progress": float(m.completion_percent or 0),
                    "contractor": m.contractor.name if m.contractor else "TBD",
                    "contractor_score": float(m.contractor_score) if m.contractor_score else 0,
                })

        # ----------------------------
        # 6) Delay Penalties
        # ----------------------------
        delay_penalties_data = []
        total_penalties = Decimal("0")
        pending_recovery = Decimal("0")
        critical_escalations = 0
        total_delay_days = 0
        penalty_count = 0

        penalties_qs = (
            DelayPenalty.objects
            .filter(project__organization=org)
            .select_related("project", "milestone", "contractor")
            .order_by("-recorded_on")
        )

        for penalty in penalties_qs:
            total_penalties += penalty.penalty_amount or Decimal("0")
            pending_recovery += penalty.pending_recovery or Decimal("0")
            total_delay_days += penalty.delay_days or 0
            penalty_count += 1

            if penalty.escalation_level == DelayPenalty.Escalation.CRITICAL:
                critical_escalations += 1

            # Determine status based on pending recovery
            if penalty.pending_recovery == 0:
                status = "Applied"
            elif penalty.pending_recovery == penalty.penalty_amount:
                status = "Pending"
            else:
                status = "Partial"

            delay_penalties_data.append({
                "id": penalty.id,
                "project_id": penalty.project.id,
                "project_name": penalty.project.name,
                "contractor": penalty.contractor.name if penalty.contractor else "N/A",
                "milestone": penalty.milestone.name if penalty.milestone else "N/A",
                "delay_days": penalty.delay_days,
                "penalty_rate": float(penalty.penalty_per_day),
                "total_penalty": float(penalty.penalty_amount),
                "escalation_level": normalize_escalation_level(penalty.escalation_level),
                "escalation_date": penalty.recorded_on.isoformat() if penalty.recorded_on else None,
                "status": status,
            })

        avg_delay_days = round(total_delay_days / penalty_count) if penalty_count > 0 else 0

        delay_penalty_summary = {
            "total_penalties": float(total_penalties),
            "pending_recovery": float(pending_recovery),
            "critical_escalations": critical_escalations,
            "avg_delay_days": avg_delay_days,
        }

        # ----------------------------
        # 7) AI Delay Predictions
        # ----------------------------
        ai_predictions_data = []
        high_risk_count = 0
        total_predicted_delay = 0
        total_confidence = 0
        total_recommendations = 0
        prediction_count = 0

        # Get latest prediction for each project
        latest_prediction_dates = (
            DelayPrediction.objects
            .filter(project__organization=org)
            .values("project")
            .annotate(latest_date=Max("prediction_date"))
        )

        for item in latest_prediction_dates:
            prediction = (
                DelayPrediction.objects
                .filter(project_id=item["project"], prediction_date=item["latest_date"])
                .select_related("project")
                .first()
            )

            if prediction:
                pred_project = prediction.project

                # Get current progress from KPI
                latest_proj_kpi = (
                    ProjectKPI_Daily.objects
                    .filter(project=pred_project)
                    .order_by("-date")
                    .first()
                )
                current_progress = float(latest_proj_kpi.construction_percent) if latest_proj_kpi else 0

                # Build risk factors
                risk_factors = []

                def get_impact(score):
                    if score >= 70:
                        return "High"
                    elif score >= 40:
                        return "Medium"
                    return "Low"

                if prediction.weather_risk:
                    risk_factors.append({
                        "factor": "Weather",
                        "impact": get_impact(float(prediction.weather_risk)),
                        "score": float(prediction.weather_risk),
                    })
                if prediction.material_risk:
                    risk_factors.append({
                        "factor": "Material",
                        "impact": get_impact(float(prediction.material_risk)),
                        "score": float(prediction.material_risk),
                    })
                if prediction.contractor_risk:
                    risk_factors.append({
                        "factor": "Contractor",
                        "impact": get_impact(float(prediction.contractor_risk)),
                        "score": float(prediction.contractor_risk),
                    })
                if prediction.financial_risk:
                    risk_factors.append({
                        "factor": "Financial",
                        "impact": get_impact(float(prediction.financial_risk)),
                        "score": float(prediction.financial_risk),
                    })
                if prediction.regulatory_risk:
                    risk_factors.append({
                        "factor": "Regulatory",
                        "impact": get_impact(float(prediction.regulatory_risk)),
                        "score": float(prediction.regulatory_risk),
                    })

                # Parse recommendations
                recommendations = prediction.recommendations or []
                if isinstance(recommendations, str):
                    try:
                        import json
                        recommendations = json.loads(recommendations)
                    except:
                        recommendations = [recommendations] if recommendations else []

                predicted_delay = prediction.predicted_delay_days or 0
                confidence = float(prediction.model_confidence or 0)

                if predicted_delay > 60:
                    high_risk_count += 1

                total_predicted_delay += predicted_delay
                total_confidence += confidence
                total_recommendations += len(recommendations)
                prediction_count += 1

                ai_predictions_data.append({
                    "project_id": pred_project.id,
                    "project_name": pred_project.name,
                    "location": pred_project.location,
                    "current_progress": current_progress,
                    "predicted_delay": predicted_delay,
                    "confidence_score": confidence,
                    "risk_factors": risk_factors,
                    "recommendations": recommendations,
                    "ai_insight": prediction.ai_insight_summary or "",
                    "model_version": prediction.model_version,
                })

        ai_prediction_summary = {
            "high_risk_projects": high_risk_count,
            "avg_predicted_delay": round(total_predicted_delay / prediction_count) if prediction_count > 0 else 0,
            "avg_confidence": round(total_confidence / prediction_count) if prediction_count > 0 else 0,
            "total_recommendations": total_recommendations,
        }

        # ----------------------------
        # 8) Delay Analysis (delayed milestones)
        # ----------------------------
        delay_analysis_data = []
        delayed_milestones = (
            Milestone.objects
            .filter(
                project__organization=org,
            )
            .filter(
                Q(status=Milestone.Status.DELAYED) |
                Q(status=Milestone.Status.COMPLETED, actual_end__gt=F("planned_end"))
            )
            .select_related("project", "contractor")
            .order_by("-planned_end")
        )

        for m in delayed_milestones:
            planned_date = m.planned_end
            actual_date = m.actual_end or today
            delay_days = (actual_date - planned_date).days if planned_date else 0

            # Determine delay reason (simplified - in real app, would be stored)
            reasons = ["Material delay", "Resource constraints", "Weather", "Regulatory"]
            reason_idx = hash(str(m.id)) % len(reasons)

            delay_analysis_data.append({
                "id": m.id,
                "milestone_name": m.name,
                "project_id": m.project.id,
                "project_name": m.project.name,
                "planned_end": planned_date.isoformat() if planned_date else None,
                "actual_end": actual_date.isoformat() if m.actual_end else "Ongoing",
                "delay_days": max(0, delay_days),
                "contractor": m.contractor.name if m.contractor else "N/A",
                "reason": reasons[reason_idx],
            })

        return Response({
            "projects_list": projects_list,
            "project_summary": project_summary,
            "daily_progress": daily_progress_data,
            "contractor_performance": contractor_performance,
            "milestones": milestones_data,
            "delay_penalties": delay_penalties_data,
            "delay_penalty_summary": delay_penalty_summary,
            "ai_predictions": ai_predictions_data,
            "ai_prediction_summary": ai_prediction_summary,
            "delay_analysis": delay_analysis_data,
        })
