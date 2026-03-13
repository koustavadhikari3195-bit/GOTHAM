import os
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream


def get_twilio_xml() -> str:
    """
    Returns TwiML that tells Twilio:
    1. Say a brief hold message
    2. Open a WebSocket stream to our /ws/phone endpoint
    """
    domain   = os.getenv("APP_DOMAIN", "localhost:8000")
    response = VoiceResponse()

    # Brief hold message while WS handshake completes (~1-2 seconds)
    response.say(
        "Welcome to Gotham Fitness. One moment please.",
        voice="Polly.Joanna",   # AWS Polly via Twilio — free usage
        language="en-US"
    )

    connect = Connect()
    connect.stream(url=f"wss://{domain}/ws/phone")
    response.append(connect)

    return str(response)


def validate_twilio_signature(request_url: str,
                               post_params: dict,
                               signature: str) -> bool:
    """
    Verify that the incoming request actually came from Twilio.
    Use this in production to prevent spoofed webhook calls.
    """
    from twilio.request_validator import RequestValidator
    validator = RequestValidator(os.getenv("TWILIO_AUTH_TOKEN"))
    return validator.validate(request_url, post_params, signature)
