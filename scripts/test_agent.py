"""
CLI test - run this FIRST before touching voice or frontend.
Verifies the agent brain + tool calls work correctly.

Usage:
  cd gotham-fitness-agent
  python scripts/test_agent.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from backend.agent.agent_router import AgentRouter

def separator(label=""):
    print(f"\n{'='*52}")
    if label: print(f"  {label}")
    print('='*52)


def run_test():
    separator("GOTHAM FITNESS AI - CLI TEST")

    agent = AgentRouter()

    # Simulated visitor conversation
    conversation = [
        "Hi, I'm interested in joining the gym",
        "My name is Marcus Johnson",
        "My email is marcus.johnson@gmail.com",
        "Phone number is 914-555-0192",
        "I want to lose about 20 pounds and build some muscle. "
        "I used to lift in college but haven't been to a gym in 3 years.",
        "Can I book an intro session this Saturday morning?",
        "The 10am slot works great for me",
    ]

    for user_msg in conversation:
        print(f"\n[User]: {user_msg}")
        try:
            response = agent.chat(user_msg)
            print(f"[Agent] ({agent._mode}): {response}")
        except Exception as e:
            print(f"[Error]: {e}")
            break

    separator("SESSION SUMMARY (for trainer)")
    try:
        summary = agent.get_session_summary()
        print(summary)
    except Exception as e:
        print(f"[Summary error]: {e}")

    separator("LEAD DATA CAPTURED")
    if agent.lead_data:
        for k, v in agent.lead_data.items():
            print(f"  {k:20} {v}")
    else:
        print("  No lead data captured (check tool call logs above)")

    separator("TEST COMPLETE")


if __name__ == "__main__":
    run_test()
