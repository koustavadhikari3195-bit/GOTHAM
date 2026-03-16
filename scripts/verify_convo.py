import asyncio
import json
import websockets
import base64
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("conv-verify")

async def verify_convo():
    uri = "ws://localhost:8000/ws/session"
    async with websockets.connect(uri, open_timeout=60) as ws:
        logger.info("Connected to WebSocket.")
        
        # 1. Wait for the initial greeting
        logger.info("Waiting for initial greeting...")
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            if data["type"] == "tts":
                logger.info(f"AGENT GREETING: {data['text']}")
                break
        
        # 2. Respond with a goal
        logger.info("Sending: I want to build muscle and get stronger.")
        await ws.send(json.dumps({
            "type": "text_input",
            "content": "I want to build muscle and get stronger."
        }))
        
        # 3. Wait for response (should be warm and ask for name/more info)
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            if data["type"] == "tts":
                logger.info(f"AGENT RESPONSE 1: {data['text']}")
                break
        
        # 4. Give name and ask about showers
        logger.info("Sending: I'm John. Do you guys have showers?")
        await ws.send(json.dumps({
            "type": "text_input",
            "content": "I'm John. Do you guys have showers?"
        }))
        
        # 5. Wait for response (should answer the shower question and pivot)
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            if data["type"] == "tts":
                logger.info(f"AGENT RESPONSE 2: {data['text']}")
                break

        # 6. Ask about a specific trainer
        logger.info("Sending: Who is Sarah and what does she do?")
        await ws.send(json.dumps({
            "type": "text_input",
            "content": "Who is Sarah and what does she do?"
        }))

        # 7. Wait for response
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            if data["type"] == "tts":
                logger.info(f"AGENT RESPONSE 3: {data['text']}")
                break

if __name__ == "__main__":
    asyncio.run(verify_convo())
