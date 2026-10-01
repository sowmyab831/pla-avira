"""
AI Property Buyer Agent
Conversational AI assistant supporting Telugu, English, and Hinglish.
Uses LangGraph for stateful multi-turn conversations.
"""
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import openai
from app.config import settings


class ConversationState(str, Enum):
    DISCOVERY = "discovery"
    BUDGET = "budget"
    LOCATION = "location"
    PREFERENCES = "preferences"
    SEARCHING = "searching"
    SHORTLISTING = "shortlisting"
    COMPARING = "comparing"
    NEGOTIATING = "negotiating"


@dataclass
class BuyerProfile:
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    property_type: Optional[str] = None  # apartment, villa, plot
    transaction_type: Optional[str] = None  # buy, rent
    bedrooms: Optional[int] = None
    preferred_areas: List[str] = field(default_factory=list)
    must_have: List[str] = field(default_factory=list)
    nice_to_have: List[str] = field(default_factory=list)
    family_size: Optional[int] = None
    investment_goal: Optional[str] = None  # residential, investment, rental
    vastu_preference: bool = False
    school_proximity: bool = False
    metro_proximity: bool = False
    facing: Optional[str] = None
    possession_timeline: Optional[str] = None
    language: str = "te"


@dataclass
class AgentContext:
    state: ConversationState = ConversationState.DISCOVERY
    profile: BuyerProfile = field(default_factory=BuyerProfile)
    history: List[Dict[str, str]] = field(default_factory=list)
    search_results: List[Dict] = field(default_factory=list)
    shortlisted: List[str] = field(default_factory=list)


SYSTEM_PROMPT = """You are Avira, an AI real estate assistant for Hyderabad, India. You help buyers find the perfect property.

PERSONALITY:
- Friendly, knowledgeable, transparent
- You speak Telugu, English, and Hinglish naturally
- You explain costs clearly with NO hidden charges
- You proactively warn about fraud and legal risks
- You are NOT a sales agent — you are a buyer's advocate

CAPABILITIES:
- Understand budget in lakhs/crores (1 crore = 1,00,00,000 INR)
- Know Hyderabad localities: Gachibowli, Kokapet, Financial District, Kondapur, Madhapur, Jubilee Hills, Hitech City, Narsingi, Tellapur
- Understand vastu preferences (East/North facing preferred)
- Know Telugu-English mixed language ("Anna, Gachibowli lo 2 crore lopala villa kavali")
- Calculate total ownership costs (not just listed price)
- Detect fake listings and overpriced properties
- Provide investment advice based on data

RULES:
1. Always respond in the user's language (Telugu/English/Hinglish)
2. If budget mentioned in crores, convert to INR internally
3. Ask one clarifying question at a time
4. Be transparent about total costs
5. Flag any red flags immediately
6. Recommend properties based on data, not emotions

CURRENT KNOWLEDGE:
- Hyderabad avg price/sqft: Gachibowli ₹8,000-12,000 | Kokapet ₹9,000-15,000 | Kondapur ₹6,000-10,000
- Stamp duty: 5% | Registration: 0.5% | GST (under construction): 5%
- Hot areas: Kokapet, Financial District, Tellapur (metro coming)
- Risky: Pre-launch without RERA, unknown builders, no EC

Based on the conversation, extract the buyer's preferences and recommend suitable properties.
"""

TELUGU_PROMPTS = {
    "greeting": "నమస్కారం! నేను అవిరా, మీ AI రియల్ ఎస్టేట్ అసిస్టెంట్. హైదరాబాద్‌లో ఇల్లు కొనడంలో మీకు సహాయం చేస్తాను. మీ బడ్జెట్ ఎంత?",
    "budget_ask": "మీ బడ్జెట్ ఎంత? (లక్షలలో లేదా కోట్లలో చెప్పండి)",
    "location_ask": "హైదరాబాద్‌లో ఏ ఏరియాలో చూస్తున్నారు?",
    "type_ask": "అపార్ట్‌మెంట్ కావాలా, విల్లా కావాలా, లేదా ప్లాట్ కావాలా?",
    "bedrooms_ask": "ఎన్ని బెడ్‌రూమ్‌లు కావాలి?",
}


class AIBuyerAgent:
    """Conversational AI buyer agent with Telugu, English, Hinglish support."""

    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        self.contexts: Dict[str, AgentContext] = {}

    async def chat(
        self,
        user_id: str,
        message: str,
        language: str = "auto",
    ) -> Dict[str, Any]:
        """Process user message and return AI response with extracted preferences."""
        
        # Get or create context
        if user_id not in self.contexts:
            self.contexts[user_id] = AgentContext()
        
        ctx = self.contexts[user_id]
        
        # Detect language if auto
        if language == "auto":
            language = self._detect_language(message)
        ctx.profile.language = language

        # Add to history
        ctx.history.append({"role": "user", "content": message})

        # Extract preferences from message
        extracted = self._extract_preferences(message, ctx)
        
        # Generate AI response
        if self.client:
            response = await self._generate_response(ctx)
        else:
            response = self._fallback_response(ctx, message)

        ctx.history.append({"role": "assistant", "content": response})

        # Determine if we should search
        should_search = self._should_search(ctx.profile)

        return {
            "response": response,
            "language": language,
            "state": ctx.state.value,
            "profile": self._profile_to_dict(ctx.profile),
            "extracted_this_turn": extracted,
            "should_search": should_search,
            "search_criteria": self._build_search_criteria(ctx.profile) if should_search else None,
        }

    def _detect_language(self, text: str) -> str:
        """Detect if text is Telugu, Hindi, or English."""
        # Telugu Unicode range: 0C00-0C7F
        telugu_chars = sum(1 for c in text if '\u0C00' <= c <= '\u0C7F')
        # Hindi/Devanagari: 0900-097F
        hindi_chars = sum(1 for c in text if '\u0900' <= c <= '\u097F')
        
        total = len(text)
        if total == 0:
            return "en"
        
        if telugu_chars / total > 0.2:
            return "te"
        elif hindi_chars / total > 0.2:
            return "hi"
        
        # Check for Hinglish patterns
        hinglish_words = ["bhai", "yaar", "chahiye", "kitna", "kahan", "wala", "crore", "lakh"]
        if any(w in text.lower() for w in hinglish_words):
            return "hi"
        
        # Telugu romanized patterns
        telugu_words = ["anna", "kavali", "lopala", "entha", "ekkada", "inka", "chala"]
        if any(w in text.lower() for w in telugu_words):
            return "te"
        
        return "en"

    def _extract_preferences(self, message: str, ctx: AgentContext) -> Dict:
        """Extract buyer preferences from message."""
        extracted = {}
        msg_lower = message.lower()

        # Budget extraction
        import re
        
        # Crore patterns
        crore_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:crore|cr|కోటి)', msg_lower)
        if crore_match:
            amount = float(crore_match.group(1))
            ctx.profile.budget_max = int(amount * 10000000)
            ctx.profile.budget_min = int(amount * 0.8 * 10000000)
            extracted["budget"] = f"₹{amount} Cr"

        # Lakh patterns
        lakh_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|lac|లక్ష)', msg_lower)
        if lakh_match:
            amount = float(lakh_match.group(1))
            ctx.profile.budget_max = int(amount * 100000)
            ctx.profile.budget_min = int(amount * 0.8 * 100000)
            extracted["budget"] = f"₹{amount} Lakh"

        # Property type
        if any(w in msg_lower for w in ["apartment", "flat", "అపార్ట్‌మెంట్", "ఫ్లాట్"]):
            ctx.profile.property_type = "apartment"
            extracted["property_type"] = "apartment"
        elif any(w in msg_lower for w in ["villa", "independent house", "విల్లా"]):
            ctx.profile.property_type = "villa"
            extracted["property_type"] = "villa"
        elif any(w in msg_lower for w in ["plot", "land", "ప్లాట్"]):
            ctx.profile.property_type = "plot"
            extracted["property_type"] = "plot"

        # Location
        areas = {
            "gachibowli": ["gachibowli", "గచ్చిబౌలి"],
            "kokapet": ["kokapet", "కోకాపేట"],
            "financial_district": ["financial district", "fin district", "fd"],
            "kondapur": ["kondapur", "కొండాపూర్"],
            "madhapur": ["madhapur", "మాధాపూర్"],
            "jubilee_hills": ["jubilee hills", "jubilee", "జూబ్లీ హిల్స్"],
            "hitech_city": ["hitech city", "hitec city", "హైటెక్ సిటీ"],
            "narsingi": ["narsingi", "నార్సింగి"],
            "tellapur": ["tellapur", "తెల్లాపూర్"],
        }
        
        for area_key, keywords in areas.items():
            if any(k in msg_lower for k in keywords):
                if area_key not in ctx.profile.preferred_areas:
                    ctx.profile.preferred_areas.append(area_key)
                    extracted["area"] = area_key

        # Bedrooms
        bhk_match = re.search(r'(\d)\s*(?:bhk|bed|bedroom|బెడ్‌రూమ్)', msg_lower)
        if bhk_match:
            ctx.profile.bedrooms = int(bhk_match.group(1))
            extracted["bedrooms"] = ctx.profile.bedrooms

        # Vastu
        if any(w in msg_lower for w in ["vastu", "వాస్తు", "east facing", "north facing"]):
            ctx.profile.vastu_preference = True
            extracted["vastu"] = True

        # Facing
        for facing in ["east", "west", "north", "south"]:
            if f"{facing} facing" in msg_lower or f"{facing}-facing" in msg_lower:
                ctx.profile.facing = facing.capitalize()
                extracted["facing"] = ctx.profile.facing

        # Update state
        if ctx.profile.budget_max and ctx.profile.preferred_areas and ctx.profile.property_type:
            ctx.state = ConversationState.SEARCHING
        elif ctx.profile.budget_max:
            ctx.state = ConversationState.LOCATION
        elif ctx.profile.preferred_areas:
            ctx.state = ConversationState.BUDGET

        return extracted

    async def _generate_response(self, ctx: AgentContext) -> str:
        """Generate AI response using OpenAI."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Add profile context
        profile_ctx = f"\nCurrent buyer profile: {json.dumps(self._profile_to_dict(ctx.profile), indent=2)}"
        profile_ctx += f"\nConversation state: {ctx.state.value}"
        messages[0]["content"] += profile_ctx

        # Add conversation history (last 10 messages)
        for msg in ctx.history[-10:]:
            messages.append(msg)

        try:
            response = await self.client.chat.completions.create(
                model=settings.AI_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=500,
            )
            return response.choices[0].message.content
        except Exception as e:
            return self._fallback_response(ctx, ctx.history[-1]["content"] if ctx.history else "")

    def _fallback_response(self, ctx: AgentContext, message: str) -> str:
        """Fallback response when AI is unavailable."""
        lang = ctx.profile.language

        if ctx.state == ConversationState.DISCOVERY:
            if lang == "te":
                return TELUGU_PROMPTS["greeting"]
            return "Hello! I'm Avira, your AI real estate assistant for Hyderabad. What's your budget and preferred area?"

        if ctx.state == ConversationState.BUDGET:
            if lang == "te":
                return TELUGU_PROMPTS["budget_ask"]
            return "What's your budget? (You can tell me in lakhs or crores)"

        if ctx.state == ConversationState.LOCATION:
            areas_str = "Gachibowli, Kokapet, Financial District, Kondapur, Madhapur, Jubilee Hills, Hitech City, Narsingi, Tellapur"
            if lang == "te":
                return f"హైదరాబాద్‌లో ఏ ఏరియాలో చూస్తున్నారు? పాపులర్ ఏరియాలు: {areas_str}"
            return f"Which area in Hyderabad are you looking at? Popular areas: {areas_str}"

        if ctx.state == ConversationState.SEARCHING:
            profile = ctx.profile
            if lang == "te":
                return f"బాగుంది! {', '.join(profile.preferred_areas)}లో ₹{profile.budget_max // 10000000} కోట్ల లోపు {profile.property_type} కోసం వెతుకుతున్నాను..."
            return f"Got it! Searching for {profile.property_type}s in {', '.join(profile.preferred_areas)} under ₹{profile.budget_max // 10000000} Cr..."

        return "I'm here to help you find the perfect property in Hyderabad. Tell me about your requirements!"

    def _should_search(self, profile: BuyerProfile) -> bool:
        """Determine if we have enough info to search."""
        return bool(profile.budget_max and (profile.preferred_areas or profile.property_type))

    def _build_search_criteria(self, profile: BuyerProfile) -> Dict:
        """Build search criteria from profile."""
        criteria = {}
        if profile.budget_min:
            criteria["price_min"] = profile.budget_min
        if profile.budget_max:
            criteria["price_max"] = profile.budget_max
        if profile.property_type:
            criteria["property_type"] = profile.property_type
        if profile.preferred_areas:
            criteria["areas"] = profile.preferred_areas
        if profile.bedrooms:
            criteria["bedrooms"] = profile.bedrooms
        if profile.facing:
            criteria["facing"] = profile.facing
        if profile.vastu_preference:
            criteria["vastu_compliant"] = True
        return criteria

    def _profile_to_dict(self, profile: BuyerProfile) -> Dict:
        """Convert profile to dict for API response."""
        return {
            "budget_min": profile.budget_min,
            "budget_max": profile.budget_max,
            "property_type": profile.property_type,
            "bedrooms": profile.bedrooms,
            "preferred_areas": profile.preferred_areas,
            "vastu_preference": profile.vastu_preference,
            "facing": profile.facing,
            "investment_goal": profile.investment_goal,
            "language": profile.language,
        }

    def reset_context(self, user_id: str):
        """Reset conversation context for user."""
        if user_id in self.contexts:
            del self.contexts[user_id]


ai_buyer_agent = AIBuyerAgent()
