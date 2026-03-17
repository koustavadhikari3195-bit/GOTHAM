import os
import re
import json
import logging
from google import genai
from google.genai import types
from .system_prompt import SYSTEM_PROMPT
from .tools import GEMINI_TOOLS

logger = logging.getLogger("gotham-agent.gemini")

# Regex to match text-based function calls like <function=name>{...}</function>
FUNCTION_CALL_PATTERN = re.compile(
    r'<function[=\s]+([\w]+)>\s*(.+?)\s*</function>',
    re.DOTALL
)


class GeminiAgent:
    def __init__(self, model: str = "gemini-1.5-flash"):
        self.client    = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model     = model
        self.history   = []
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
        fn     = skill_map.get(name)
        result = fn(**args) if fn else {"error": f"Unknown tool: {name}"}

        if name == "save_lead_to_db":
            self.lead_data.update({k: v for k, v in args.items() if v})

        return result

    def _sanitize_response(self, text: str) -> str:
        """
        Strip raw function-call XML from text responses.
        Sometimes Gemini 1.5 Flash emits <function=name>{...}</function>
        in text instead of using the proper function_call API.
        """
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

        # Remove the function call XML from the text
        cleaned = FUNCTION_CALL_PATTERN.sub('', text)

        # Also clean up any other common markup artifacts
        cleaned = re.sub(r'</?function[^>]*>', '', cleaned)
        cleaned = re.sub(r'\{"name"\s*:.*?\}', '', cleaned)  # stray JSON objects

        # Clean up extra whitespace left behind
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        cleaned = cleaned.strip()

        if not cleaned:
            return "Got it! I'm processing that for you. What else can I help with?"

        return cleaned

    def chat(self, user_message: str) -> str:
        self.history.append(
            types.Content(role="user",
                          parts=[types.Part.from_text(text=user_message)])
        )

        resp = self.client.models.generate_content(
            model=self.model,
            contents=self.history,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=[GEMINI_TOOLS],
                temperature=0.7,
            )
        )

        candidate = resp.candidates[0]
        fcs = [p.function_call
               for p in candidate.content.parts if p.function_call]

        # No tool call — plain text response
        if not fcs:
            text = resp.text or "I'm sorry, I didn't quite catch that. Could you repeat?"
            text = self._sanitize_response(text)
            self.history.append(
                types.Content(role="model",
                              parts=[types.Part.from_text(text=text)])
            )
            return text

        # Tool calls — execute and return final response
        self.history.append(candidate.content)

        tool_parts = []
        for fc in fcs:
            result = self._dispatch_tool(fc.name, dict(fc.args))
            tool_parts.append(
                types.Part.from_function_response(
                    name=fc.name,
                    response={"result": result}
                )
            )

        self.history.append(types.Content(role="user", parts=tool_parts))

        final = self.client.models.generate_content(
            model=self.model,
            contents=self.history,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=[GEMINI_TOOLS],
            )
        )
        text = final.text
        text = self._sanitize_response(text)
        self.history.append(
            types.Content(role="model",
                          parts=[types.Part.from_text(text=text)])
        )
        return text

    def get_session_summary(self) -> str:
        return self.chat(
            "Session ended. Generate a concise trainer summary covering: "
            "visitor full name, all contact info captured, stated fitness "
            "goals, experience level, booked session slot if any, and any "
            "special notes for the coaching team."
        )
