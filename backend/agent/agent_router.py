"""
3-Layer Agent Router
────────────────────
Layer 1: Gemini 1.5 Flash   → simple tasks, greetings, FAQs   (1,000 RPD free)
Layer 2: Gemini 2.0 Flash   → complex tasks, tool calling      (250 RPD free)
Layer 3: Groq Llama 3.3 70B → overflow fallback               (14,400 RPD free)

Combined free capacity: ~15,650 requests/day
Your usage at 500 customers/month: ~167/day = 1% of capacity
"""
from .gemini_agent import GeminiAgent
from .groq_agent   import GroqAgent
import logging

logger = logging.getLogger("gotham-agent.router")

COMPLEX_KEYWORDS = [
    "book", "schedule", "calendar", "appointment", "session",
    "available", "slot", "time", "date", "sign up", "register",
    "summary", "confirm", "reserve"
]

RATE_LIMIT_SIGNALS = [
    "429", "quota", "rate_limit", "rate limit",
    "resource_exhausted", "exhausted", "too many requests"
]


class AgentRouter:
    def __init__(self):
        self.lite      = GeminiAgent(model="gemini-1.5-flash")
        self.flash     = GeminiAgent(model="gemini-2.0-flash")
        self.groq      = GroqAgent()
        self._mode     = "gemini"   # "gemini" | "groq"
        self.lead_data = {}

    def _is_complex(self, msg: str) -> bool:
        return any(k in msg.lower() for k in COMPLEX_KEYWORDS)

    def _is_rate_limit(self, error: Exception) -> bool:
        return any(s in str(error).lower() for s in RATE_LIMIT_SIGNALS)

    def _pick_gemini_agent(self, message: str) -> GeminiAgent:
        return self.flash if self._is_complex(message) else self.lite

    def _sync_context_to_groq(self):
        """Mirror lead data into Groq so fallback has full context."""
        if self.lead_data:
            self.groq.history.append({
                "role":    "system",
                "content": (
                    f"[Context from previous conversation] "
                    f"Lead data captured so far: {self.lead_data}. "
                    f"Continue the Gotham Fitness conversation naturally."
                )
            })

    def chat(self, user_message: str) -> str:
        # Already in Groq fallback mode
        if self._mode == "groq":
            result = self.groq.chat(user_message)
            self.lead_data.update(self.groq.lead_data)
            return result

        # Try Gemini (lite or flash based on complexity)
        agent = self._pick_gemini_agent(user_message)
        try:
            result = agent.chat(user_message)
            self.lead_data.update(agent.lead_data)
            return result

        except Exception as e:
            if self._is_rate_limit(e):
                logger.warning("Gemini rate limit hit -> switching to Groq fallback")
                self._mode = "groq"
                self._sync_context_to_groq()
                try:
                    result = self.groq.chat(user_message)
                    self.lead_data.update(self.groq.lead_data)
                    return result
                except Exception as inner_e:
                    if self._is_rate_limit(inner_e):
                        return (
                            "I'm sorry, I'm getting a lot of visitors right now and my brain "
                            "is a bit overloaded! 🏋️ Could you please try again in a few minutes?"
                        )
                    raise
            raise  # re-raise non-rate-limit errors

    def get_session_summary(self) -> str:
        agent = self.groq if self._mode == "groq" else self.flash
        summary = agent.get_session_summary()
        self.lead_data.update(agent.lead_data)
        return summary
