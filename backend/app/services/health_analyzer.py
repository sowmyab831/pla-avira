"""
Health Report Analyzer - AI-Powered Health Analysis
Analyzes health reports and provides insights with doctor recommendations
"""
import logging
import httpx
from typing import Dict, Any, Optional
from datetime import datetime

from app.services.llm_client import generate as llm_generate

logger = logging.getLogger(__name__)


class HealthAnalyzer:
    """
    AI-powered health report analysis with:
    - Report summarization
    - Health insights and trends
    - Doctor recommendations
    - Improvement suggestions
    - Risk assessment
    """
    
    async def analyze_health_report(
        self,
        report_text: str,
        report_type: str,
        ollama_host: str,
        ollama_model: str
    ) -> Dict[str, Any]:
        """
        Analyze health report using LLM.
        
        Args:
            report_text: Extracted text from health report
            report_type: Type of report (blood_test, imaging, general, etc.)
            ollama_host: Ollama API host
            ollama_model: Model to use for analysis
        """
        
        prompt = f"""You are a knowledgeable health research assistant. Analyze this {report_type} health report and provide a thorough, evidence-based summary.

REPORT:
{report_text[:3000]}  # Limit to avoid token overflow

Please provide:
1. **Summary** (2-3 sentences): What this report shows
2. **Key Findings** (bullet points): Important values or observations
3. **Health Status** (Good/Fair/Needs Attention): Overall assessment
4. **Areas of Concern** (if any): What needs attention, including low or deficient values
5. **Potential Vitamin / Mineral / Nutrient Gaps**: Identify likely deficiencies (e.g., iron, vitamin D, B12, folate, vitamin C, magnesium) based on the results, and list foods or safe supplement options that may help. Use evidence-based guidance.
6. **Actionable Recommendations**: Lifestyle changes, diet, exercise, sleep, hydration tailored to the abnormal values
7. **Doctor Consultation**: Which specialist to see if needed (e.g., Cardiologist, Endocrinologist, Hematologist) and why
8. **Follow-up**: When to get next checkup and any follow-up tests to consider

IMPORTANT DISCLAIMER: This is AI analysis for informational purposes only. Always consult with licensed healthcare professionals for medical advice.

Be specific, practical, empathetic, and cite common clinical associations without overstating certainty."""

        try:
            analysis_text = await llm_generate(
                prompt, task="fast", temperature=0.3, timeout=60,
            )

            if analysis_text:
                # Parse the analysis to extract structured data
                structured_analysis = self._parse_analysis(analysis_text, report_type)

                return {
                    "success": True,
                    "disclaimer": "⚠️ MEDICAL DISCLAIMER: This is AI-generated analysis for informational purposes only. It is NOT medical advice. Always consult with licensed healthcare professionals for diagnosis, treatment, and medical decisions. Do not delay seeking professional medical advice based on this analysis.",
                    "report_type": report_type,
                    "analysis": analysis_text,
                    "structured": structured_analysis,
                    "analyzed_at": datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"Error analyzing health report: {e}")
        
        # Fallback response
        return {
            "success": False,
            "disclaimer": "⚠️ MEDICAL DISCLAIMER: This is AI-generated analysis for informational purposes only. Always consult with licensed healthcare professionals.",
            "message": "Unable to analyze report at this time. Please consult with your healthcare provider.",
            "report_type": report_type
        }
    
    def _parse_analysis(self, analysis_text: str, report_type: str) -> Dict[str, Any]:
        """Parse LLM analysis into structured format."""
        
        # Extract key information using simple parsing
        # In production, use more sophisticated NLP
        
        analysis_lower = analysis_text.lower()
        
        # Determine health status
        if "good" in analysis_lower and "health" in analysis_lower:
            health_status = "Good"
            status_color = "green"
        elif "fair" in analysis_lower or "moderate" in analysis_lower:
            health_status = "Fair"
            status_color = "yellow"
        elif "concern" in analysis_lower or "attention" in analysis_lower:
            health_status = "Needs Attention"
            status_color = "red"
        else:
            health_status = "Review Required"
            status_color = "gray"
        
        # Extract doctor recommendations
        doctors = []
        doctor_keywords = {
            "cardiologist": "Cardiologist (Heart Specialist)",
            "endocrinologist": "Endocrinologist (Hormone/Diabetes Specialist)",
            "nephrologist": "Nephrologist (Kidney Specialist)",
            "pulmonologist": "Pulmonologist (Lung Specialist)",
            "gastroenterologist": "Gastroenterologist (Digestive System)",
            "neurologist": "Neurologist (Brain/Nervous System)",
            "dermatologist": "Dermatologist (Skin Specialist)",
            "orthopedist": "Orthopedist (Bone/Joint Specialist)",
            "primary care": "Primary Care Physician",
            "general practitioner": "General Practitioner"
        }
        
        for keyword, doctor_name in doctor_keywords.items():
            if keyword in analysis_lower:
                doctors.append(doctor_name)
        
        if not doctors:
            doctors.append("Primary Care Physician")
        
        return {
            "health_status": health_status,
            "status_color": status_color,
            "recommended_doctors": doctors,
            "urgency": "routine" if health_status == "Good" else "moderate" if health_status == "Fair" else "high",
            "follow_up_recommended": "3-6 months" if health_status == "Good" else "1-3 months" if health_status == "Fair" else "1-2 weeks"
        }
    
    async def generate_health_summary(
        self,
        reports: list,
        ollama_host: str,
        ollama_model: str
    ) -> Dict[str, Any]:
        """Generate an overall health summary from a chronological list of reports."""

        if not reports:
            return {
                "success": False,
                "message": "No health reports available for summary."
            }

        lines = []
        for r in reports:
            date = r.get("report_date") or r.get("uploaded_at", "")[:10]
            lines.append(f"\n--- Report Date: {date} ({r.get('filename', '')}) ---")
            for lr in r.get("lab_results", []):
                flag = "ABNORMAL" if lr.get("is_abnormal") else "normal"
                lines.append(
                    f"- {lr.get('test_name')}: {lr.get('value')} {lr.get('unit')} "
                    f"(ref: {lr.get('reference_range')}, {flag})"
                )
            for a in r.get("alerts", []):
                lines.append(f"- ALERT: {a.get('message')}")

        report_text = "\n".join(lines)[:5000]

        prompt = f"""You are a health research assistant with broad clinical knowledge. Based on the following lab report timeline, write a comprehensive yet easy-to-understand health summary for the user.

LAB REPORT TIMELINE:
{report_text}

Please provide:
1. **Overall Health Verdict** (Good / Fair / Needs Attention) with a brief justification.
2. **What is going well** — normal values and positive signs.
3. **Low / deficient / abnormal values** — list each with a layperson explanation of what it may mean.
4. **Likely vitamin, mineral, or nutrient gaps** — e.g., iron, vitamin D, B12, folate, vitamin C, magnesium. Recommend foods rich in those nutrients and whether a supplement may be worth discussing with a doctor.
5. **Actionable improvement plan** — specific diet, exercise, sleep, hydration, and lifestyle changes tailored to the user's results.
6. **Anomalies or trends that need follow-up** across the timeline (if more than one report is provided).
7. **Recommended specialist(s)** to consult, with reason and urgency (routine / soon / urgent).
8. **Suggested follow-up tests and timeframe**.
9. **Medical disclaimer** reminding the user to consult a licensed healthcare professional.

Use evidence-based, cautious language. Do not diagnose. Be empathetic and practical. Format with clear headings and bullet points."""

        try:
            summary_text = await llm_generate(
                prompt, task="fast", temperature=0.3, timeout=120,
            )

            if summary_text:
                structured = self._parse_analysis(summary_text, "blood_test")
                return {
                    "success": True,
                    "summary": summary_text,
                    "structured": structured,
                    "generated_at": datetime.now().isoformat(),
                    "report_count": len(reports),
                    "disclaimer": "⚠️ MEDICAL DISCLAIMER: This is AI-generated information for informational purposes only. Always consult with licensed healthcare professionals for diagnosis, treatment, and medical decisions."
                }

        except Exception as e:
            logger.error(f"Error generating health summary: {e}")

        return {
            "success": False,
            "message": "Unable to generate health summary at this time. Please consult your healthcare provider.",
            "disclaimer": "⚠️ MEDICAL DISCLAIMER: This is AI-generated information for informational purposes only. Always consult with licensed healthcare professionals."
        }

    async def get_health_insights(
        self,
        user_id: str,
        reports: list
    ) -> Dict[str, Any]:
        """Get overall health insights from multiple reports. (legacy wrapper)"""

        return {
            "success": True,
            "user_id": user_id,
            "total_reports": len(reports),
            "overall_health": "Good",
            "trends": {
                "improving": [],
                "stable": [],
                "needs_attention": []
            },
            "recommendations": [
                "Continue regular exercise routine",
                "Maintain balanced diet",
                "Schedule annual checkup"
            ]
        }
    
    def get_doctor_directory(self, specialty: Optional[str] = None) -> list:
        """Get directory of doctors by specialty."""
        
        doctors = [
            {
                "specialty": "Cardiologist",
                "description": "Heart and cardiovascular system",
                "when_to_see": "High blood pressure, chest pain, irregular heartbeat, high cholesterol"
            },
            {
                "specialty": "Endocrinologist",
                "description": "Hormones, diabetes, thyroid",
                "when_to_see": "Diabetes, thyroid issues, hormone imbalances, metabolic disorders"
            },
            {
                "specialty": "Nephrologist",
                "description": "Kidneys and urinary system",
                "when_to_see": "Kidney disease, high creatinine, protein in urine, kidney stones"
            },
            {
                "specialty": "Gastroenterologist",
                "description": "Digestive system",
                "when_to_see": "Stomach pain, digestive issues, liver problems, IBS"
            },
            {
                "specialty": "Pulmonologist",
                "description": "Lungs and respiratory system",
                "when_to_see": "Breathing problems, asthma, COPD, lung disease"
            },
            {
                "specialty": "Primary Care Physician",
                "description": "General health and preventive care",
                "when_to_see": "Annual checkups, general health concerns, referrals"
            }
        ]
        
        if specialty:
            return [d for d in doctors if specialty.lower() in d["specialty"].lower()]
        
        return doctors


# Singleton instance
_health_analyzer: Optional[HealthAnalyzer] = None


def get_health_analyzer() -> HealthAnalyzer:
    """Get health analyzer instance."""
    global _health_analyzer
    if _health_analyzer is None:
        _health_analyzer = HealthAnalyzer()
    return _health_analyzer
