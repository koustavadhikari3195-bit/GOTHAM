from google.genai import types

# ─── GEMINI FORMAT ─────────────────────────────────────────────────────────────
GEMINI_TOOLS = types.Tool(function_declarations=[

    types.FunctionDeclaration(
        name="check_calendar",
        description=(
            "Check the Gotham Fitness Google Calendar for available introductory "
            "session slots. ALWAYS call this before confirming any booking."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "date_preference": types.Schema(
                    type=types.Type.STRING,
                    description="User's preferred date. E.g. 'this Saturday', "
                                "'next Monday', '2025-08-15'"
                ),
                "time_preference": types.Schema(
                    type=types.Type.STRING,
                    description="Preferred time of day: 'morning', 'afternoon', "
                                "'evening', or 'any'"
                ),
            },
            required=["date_preference"]
        )
    ),

    types.FunctionDeclaration(
        name="book_slot",
        description=(
            "Book an introductory session on the calendar. Only call after the "
            "customer has verbally confirmed a specific slot."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "event_id":   types.Schema(type=types.Type.STRING,
                              description="Event ID from check_calendar results"),
                "lead_name":  types.Schema(type=types.Type.STRING),
                "lead_email": types.Schema(type=types.Type.STRING),
                "lead_phone": types.Schema(type=types.Type.STRING),
            },
            required=["event_id", "lead_name"]
        )
    ),

    types.FunctionDeclaration(
        name="save_lead_to_db",
        description=(
            "Save prospect contact info to Supabase. Call immediately once "
            "name + any contact info is confirmed. Can be called multiple times "
            "to update the same lead as more info is captured."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "name":          types.Schema(type=types.Type.STRING),
                "email":         types.Schema(type=types.Type.STRING),
                "phone":         types.Schema(type=types.Type.STRING),
                "fitness_goals": types.Schema(type=types.Type.STRING),
                "booked_slot":   types.Schema(type=types.Type.STRING,
                                 description="ISO datetime if session booked"),
            },
            required=["name"]
        )
    ),
])

# ─── GROQ / OPENAI FORMAT ──────────────────────────────────────────────────────
GROQ_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_calendar",
            "description": "Check available intro session slots on the Gotham Fitness calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_preference": {"type": "string",
                        "description": "e.g. 'this Saturday', 'next Monday'"},
                    "time_preference": {"type": "string",
                        "description": "morning / afternoon / evening / any"},
                },
                "required": ["date_preference"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_slot",
            "description": "Book a confirmed intro session on the calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id":   {"type": "string"},
                    "lead_name":  {"type": "string"},
                    "lead_email": {"type": "string"},
                    "lead_phone": {"type": "string"},
                },
                "required": ["event_id", "lead_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_lead_to_db",
            "description": "Save prospect contact info to the database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name":          {"type": "string"},
                    "email":         {"type": "string"},
                    "phone":         {"type": "string"},
                    "fitness_goals": {"type": "string"},
                    "booked_slot":   {"type": "string"},
                },
                "required": ["name"]
            }
        }
    }
]
