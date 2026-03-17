import os
from google import genai
from google.genai import types
from .system_prompt import SYSTEM_PROMPT
from .tools import GEMINI_TOOLS


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
