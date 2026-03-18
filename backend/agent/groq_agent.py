import os
import re
import json
import logging
from groq import Groq
from .system_prompt import SYSTEM_PROMPT
from .tools import GROQ_TOOLS

logger = logging.getLogger("gotham-agent.groq")

# Regex to match text-based function calls like <function=name>{...}</function>
FUNCTION_CALL_PATTERN = re.compile(
    r'<function[=\s]+([\w]+)>\s*(.+?)\s*</function>',
    re.DOTALL
)


class GroqAgent:
    """
    Fallback agent using Groq Llama 3.3 70B.
    Free tier: 14,400 RPD — large overflow buffer.
    Auto-activated when Gemini hits rate limits.
    """
    def __init__(self):
        self.client    = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model     = "llama-3.3-70b-versatile"
        self.history   = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.lead_data = {}

    def _dispatch_tool(self, name: str, args: dict) -> dict:
        from backend.skills.check_calendar  import run as check_cal
        from backend.skills.book_slot       import run as book
        from backend.skills.save_lead_to_db import run as save

        skill_map = {
            "check_calendar":  check_cal,
            "book_slot":       book,
            "save_lead_to_db": save,
        }
        fn = skill_map.get(name)
        if not fn:
            return {"error": f"Unknown tool: {name}"}
        try:
            result = fn(**args)
        except Exception as e:
            logger.error(f"Tool {name} raised exception: {e}", exc_info=True)
            result = {"error": f"Tool {name} encountered an issue. Please try again."}

        if name == "save_lead_to_db":
            self.lead_data.update({k: v for k, v in args.items() if v})

        return result

    def _sanitize_response(self, text: str) -> str:
        """Strip raw function-call XML from text responses."""
        if not text:
            return text

        # Find and execute any embedded function calls
        matches = FUNCTION_CALL_PATTERN.findall(text)
        for fn_name, fn_args_str in matches:
            try:
                fn_args = json.loads(fn_args_str)
                logger.info(f"Executing embedded function call: {fn_name}({fn_args})")
                self._dispatch_tool(fn_name, fn_args)
            except Exception as e:
                logger.warning(f"Failed to execute embedded function call {fn_name}: {e}")

        cleaned = FUNCTION_CALL_PATTERN.sub('', text)
        cleaned = re.sub(r'</?function[^>]*>', '', cleaned)
        cleaned = re.sub(r'\{"name"\s*:\s*"(check_calendar|book_slot|save_lead_to_db)"[^}]*\}', '', cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        cleaned = cleaned.strip()

        if not cleaned:
            return "Got it! I'm processing that for you. What else can I help with?"

        return cleaned

    def chat(self, user_message: str) -> str:
        self.history.append({"role": "user", "content": user_message})

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=self.history,
            tools=GROQ_TOOLS,
            tool_choice="auto",
            max_tokens=512,
            temperature=0.7,
        )

        msg = resp.choices[0].message

        if not msg.tool_calls:
            text = msg.content
            text = self._sanitize_response(text)
            self.history.append({"role": "assistant", "content": text})
            return text

        # Execute tool calls
        self.history.append(msg)

        for tc in msg.tool_calls:
            args   = json.loads(tc.function.arguments)
            result = self._dispatch_tool(tc.function.name, args)
            self.history.append({
                "role":         "tool",
                "tool_call_id": tc.id,
                "content":      json.dumps(result)
            })

        final = self.client.chat.completions.create(
            model=self.model,
            messages=self.history,
            max_tokens=512,
        )
        text = final.choices[0].message.content
        text = self._sanitize_response(text)
        self.history.append({"role": "assistant", "content": text})
        return text

    def get_session_summary(self) -> str:
        return self.chat(
            "Session ended. Generate a concise trainer summary covering: "
            "visitor full name, all contact info captured, stated fitness "
            "goals, experience level, booked session slot if any, and any "
            "special notes for the coaching team."
        )
