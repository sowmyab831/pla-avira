"""
Family Service - Family Member Management and Personalized Recommendations
Manages family profiles and provides age/gender-based recommendations
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from enum import Enum

logger = logging.getLogger(__name__)


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class AgeGroup(str, Enum):
    INFANT = "infant"  # 0-2
    TODDLER = "toddler"  # 3-5
    CHILD = "child"  # 6-12
    TEEN = "teen"  # 13-17
    ADULT = "adult"  # 18-64
    SENIOR = "senior"  # 65+


class FamilyMember:
    """Family member profile."""
    
    def __init__(
        self,
        member_id: str,
        name: str,
        age: int,
        gender: Gender,
        birth_date: Optional[str] = None,
        relationship: str = "family",
        health_conditions: Optional[List[str]] = None,
        dietary_preferences: Optional[List[str]] = None,
        interests: Optional[List[str]] = None
    ):
        self.member_id = member_id
        self.name = name
        self.age = age
        self.gender = gender
        self.birth_date = birth_date
        self.relationship = relationship
        self.health_conditions = health_conditions or []
        self.dietary_preferences = dietary_preferences or []
        self.interests = interests or []
        self.age_group = self._determine_age_group(age)
        self.created_at = datetime.now().isoformat()
    
    def _determine_age_group(self, age: int) -> AgeGroup:
        """Determine age group from age."""
        if age <= 2:
            return AgeGroup.INFANT
        elif age <= 5:
            return AgeGroup.TODDLER
        elif age <= 12:
            return AgeGroup.CHILD
        elif age <= 17:
            return AgeGroup.TEEN
        elif age <= 64:
            return AgeGroup.ADULT
        else:
            return AgeGroup.SENIOR
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "member_id": self.member_id,
            "name": self.name,
            "age": self.age,
            "gender": self.gender.value,
            "birth_date": self.birth_date,
            "relationship": self.relationship,
            "age_group": self.age_group.value,
            "health_conditions": self.health_conditions,
            "dietary_preferences": self.dietary_preferences,
            "interests": self.interests,
            "created_at": self.created_at
        }


class FamilyService:
    """
    Family management service with:
    - Member profile management
    - Age/gender-based recommendations
    - Family wellness tracking
    - Personalized content
    """
    
    def __init__(self):
        # In-memory storage (replace with database in production)
        self.members: Dict[str, FamilyMember] = {}
    
    def add_member(
        self,
        member_id: str,
        name: str,
        age: int,
        gender: str,
        birth_date: Optional[str] = None,
        relationship: str = "family",
        health_conditions: Optional[List[str]] = None,
        dietary_preferences: Optional[List[str]] = None,
        interests: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Add family member."""
        
        try:
            gender_enum = Gender(gender.lower())
        except ValueError:
            gender_enum = Gender.PREFER_NOT_TO_SAY
        
        member = FamilyMember(
            member_id=member_id,
            name=name,
            age=age,
            gender=gender_enum,
            birth_date=birth_date,
            relationship=relationship,
            health_conditions=health_conditions,
            dietary_preferences=dietary_preferences,
            interests=interests
        )
        
        self.members[member_id] = member
        
        logger.info(f"Added family member: {name} (age {age}, {gender})")
        
        return {
            "success": True,
            "message": f"Added {name} to family",
            "member": member.to_dict()
        }
    
    def get_member(self, member_id: str) -> Optional[Dict[str, Any]]:
        """Get family member by ID."""
        member = self.members.get(member_id)
        return member.to_dict() if member else None
    
    def get_all_members(self, user_id: str = "default") -> List[Dict[str, Any]]:
        """Get all family members."""
        return [member.to_dict() for member in self.members.values()]
    
    def update_member(
        self,
        member_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update family member."""
        
        member = self.members.get(member_id)
        if not member:
            return {
                "success": False,
                "message": "Member not found"
            }
        
        # Update fields
        if "name" in updates:
            member.name = updates["name"]
        if "age" in updates:
            member.age = updates["age"]
            member.age_group = member._determine_age_group(updates["age"])
        if "health_conditions" in updates:
            member.health_conditions = updates["health_conditions"]
        if "dietary_preferences" in updates:
            member.dietary_preferences = updates["dietary_preferences"]
        if "interests" in updates:
            member.interests = updates["interests"]
        
        return {
            "success": True,
            "message": f"Updated {member.name}",
            "member": member.to_dict()
        }
    
    def delete_member(self, member_id: str) -> Dict[str, Any]:
        """Delete family member."""
        
        if member_id in self.members:
            member = self.members.pop(member_id)
            return {
                "success": True,
                "message": f"Removed {member.name} from family"
            }
        
        return {
            "success": False,
            "message": "Member not found"
        }
    
    def get_recommendations_for_member(
        self,
        member_id: str
    ) -> Dict[str, Any]:
        """Get personalized recommendations for family member."""
        
        member = self.members.get(member_id)
        if not member:
            return {
                "success": False,
                "message": "Member not found"
            }
        
        recommendations = {
            "member_id": member_id,
            "name": member.name,
            "age": member.age,
            "age_group": member.age_group.value,
            "health": self._get_health_recommendations(member),
            "nutrition": self._get_nutrition_recommendations(member),
            "activities": self._get_activity_recommendations(member),
            "education": self._get_education_recommendations(member)
        }
        
        return {
            "success": True,
            "recommendations": recommendations
        }
    
    def _get_health_recommendations(self, member: FamilyMember) -> List[str]:
        """Get health recommendations based on age/gender."""
        
        recommendations = []
        
        if member.age_group == AgeGroup.INFANT:
            recommendations = [
                "Regular pediatric checkups every 2-3 months",
                "Vaccination schedule adherence",
                "Monitor developmental milestones",
                "Ensure adequate sleep (14-17 hours/day)"
            ]
        elif member.age_group == AgeGroup.TODDLER:
            recommendations = [
                "Annual pediatric checkups",
                "Dental checkup starting at age 3",
                "Encourage physical play (3+ hours/day)",
                "Monitor speech and social development"
            ]
        elif member.age_group == AgeGroup.CHILD:
            recommendations = [
                "Annual physical exam",
                "Dental checkup every 6 months",
                "Vision screening",
                "60+ minutes of physical activity daily",
                "9-12 hours of sleep per night"
            ]
        elif member.age_group == AgeGroup.TEEN:
            recommendations = [
                "Annual physical exam",
                "Mental health screening",
                "Sports physical if needed",
                "60+ minutes of physical activity daily",
                "8-10 hours of sleep per night"
            ]
        elif member.age_group == AgeGroup.ADULT:
            if member.gender == Gender.FEMALE:
                recommendations = [
                    "Annual physical exam",
                    "Mammogram starting at age 40",
                    "Pap smear every 3 years",
                    "150+ minutes moderate exercise weekly",
                    "7-9 hours of sleep per night"
                ]
            else:
                recommendations = [
                    "Annual physical exam",
                    "Blood pressure check",
                    "Cholesterol screening every 5 years",
                    "150+ minutes moderate exercise weekly",
                    "7-9 hours of sleep per night"
                ]
        else:  # SENIOR
            recommendations = [
                "Annual physical exam",
                "Bone density scan",
                "Colonoscopy every 10 years",
                "Fall prevention assessment",
                "150+ minutes moderate exercise weekly",
                "7-8 hours of sleep per night"
            ]
        
        return recommendations
    
    def _get_nutrition_recommendations(self, member: FamilyMember) -> List[str]:
        """Get nutrition recommendations based on age/gender."""
        
        recommendations = []
        
        if member.age_group == AgeGroup.INFANT:
            recommendations = [
                "Breast milk or formula (primary nutrition)",
                "Introduce solid foods at 6 months",
                "Avoid honey until age 1",
                "Iron-fortified cereals"
            ]
        elif member.age_group == AgeGroup.TODDLER:
            recommendations = [
                "Whole milk (2-3 cups/day)",
                "Variety of fruits and vegetables",
                "Whole grains",
                "Protein from multiple sources",
                "Limit sugar and processed foods"
            ]
        elif member.age_group == AgeGroup.CHILD:
            recommendations = [
                "Balanced meals with all food groups",
                "5+ servings fruits/vegetables daily",
                "Whole grains over refined",
                "Lean proteins",
                "Limit sugary drinks and snacks",
                "Adequate calcium for bone growth"
            ]
        elif member.age_group == AgeGroup.TEEN:
            recommendations = [
                "Increased calorie needs for growth",
                "Calcium and vitamin D for bone health",
                "Iron-rich foods (especially for females)",
                "Lean proteins for muscle development",
                "Healthy fats (nuts, avocado, fish)",
                "Limit fast food and energy drinks"
            ]
        elif member.age_group == AgeGroup.ADULT:
            recommendations = [
                "Balanced diet with portion control",
                "5+ servings fruits/vegetables daily",
                "Whole grains and fiber",
                "Lean proteins",
                "Healthy fats (omega-3)",
                "Limit sodium, sugar, saturated fats",
                "Stay hydrated (8+ glasses water)"
            ]
        else:  # SENIOR
            recommendations = [
                "Nutrient-dense foods",
                "Adequate protein to maintain muscle",
                "Calcium and vitamin D for bone health",
                "Fiber for digestive health",
                "B12 supplementation if needed",
                "Limit sodium for blood pressure",
                "Stay hydrated"
            ]
        
        return recommendations
    
    def _get_activity_recommendations(self, member: FamilyMember) -> List[str]:
        """Get activity recommendations based on age."""
        
        if member.age_group in [AgeGroup.INFANT, AgeGroup.TODDLER]:
            return [
                "Tummy time for infants",
                "Free play and exploration",
                "Outdoor time daily",
                "Interactive games with parents"
            ]
        elif member.age_group == AgeGroup.CHILD:
            return [
                "60+ minutes active play daily",
                "Team sports or activities",
                "Swimming lessons",
                "Bike riding",
                "Limit screen time to 2 hours/day"
            ]
        elif member.age_group == AgeGroup.TEEN:
            return [
                "60+ minutes physical activity daily",
                "Sports or fitness activities",
                "Strength training 3x/week",
                "Social activities with peers",
                "Limit screen time"
            ]
        elif member.age_group == AgeGroup.ADULT:
            return [
                "150+ minutes moderate exercise weekly",
                "Strength training 2x/week",
                "Flexibility exercises",
                "Active hobbies",
                "Work-life balance"
            ]
        else:  # SENIOR
            return [
                "150+ minutes moderate exercise weekly",
                "Balance exercises to prevent falls",
                "Strength training to maintain muscle",
                "Low-impact activities (walking, swimming)",
                "Social engagement activities"
            ]
    
    def _get_education_recommendations(self, member: FamilyMember) -> List[str]:
        """Get education/development recommendations."""
        
        if member.age_group == AgeGroup.INFANT:
            return [
                "Read to baby daily",
                "Talk and sing frequently",
                "Sensory play activities",
                "Parent-child bonding time"
            ]
        elif member.age_group == AgeGroup.TODDLER:
            return [
                "Read together daily",
                "Encourage language development",
                "Preschool or playgroups",
                "Creative play (art, music)"
            ]
        elif member.age_group == AgeGroup.CHILD:
            return [
                "Support homework and learning",
                "Encourage reading for pleasure",
                "Extracurricular activities",
                "Develop social skills"
            ]
        elif member.age_group == AgeGroup.TEEN:
            return [
                "Academic support and guidance",
                "Career exploration",
                "College/vocational planning",
                "Life skills development",
                "Financial literacy"
            ]
        elif member.age_group == AgeGroup.ADULT:
            return [
                "Continuous learning opportunities",
                "Professional development",
                "Skill enhancement",
                "Personal growth activities"
            ]
        else:  # SENIOR
            return [
                "Lifelong learning programs",
                "Technology education",
                "Social engagement",
                "Memory and cognitive activities"
            ]
    
    def get_family_wellness_score(self, user_id: str = "default") -> Dict[str, Any]:
        """Calculate overall family wellness score."""
        
        members = self.get_all_members(user_id)
        
        if not members:
            return {
                "success": False,
                "message": "No family members found"
            }
        
        # Simple wellness calculation
        # In production, this would analyze health data, activities, etc.
        
        wellness_score = 75  # Base score
        
        # Bonus for having diverse age groups
        age_groups = set(m["age_group"] for m in members)
        wellness_score += len(age_groups) * 2
        
        # Cap at 100
        wellness_score = min(wellness_score, 100)
        
        return {
            "success": True,
            "family_size": len(members),
            "wellness_score": wellness_score,
            "rating": "Good" if wellness_score >= 70 else "Fair" if wellness_score >= 50 else "Needs Attention",
            "members": members
        }


# Singleton instance
_family_service: Optional[FamilyService] = None


def get_family_service() -> FamilyService:
    """Get family service instance."""
    global _family_service
    if _family_service is None:
        _family_service = FamilyService()
    return _family_service
