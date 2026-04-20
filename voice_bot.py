#!/usr/bin/env python3
"""Silent Chaos Voice Bot — speak commands, hear responses.

Usage:
    export OPENAI_API_KEY=sk-...
    python voice_bot.py

Push-to-talk: press Enter to start recording, Enter again to stop.
Ctrl+C to exit.
"""

import copy
import getpass
import json
import os
import subprocess
import sys
import tempfile
import threading

import numpy as np
import requests
import sounddevice as sd
from scipy.io import wavfile
import openai

# ── Config ────────────────────────────────────────────────────────────────────

MCP_URL = "https://silentchaos.net/mcp"
OPENAI_MODEL = "gpt-4o"
TTS_VOICE = "onyx"
SAMPLE_RATE = 16000
CHANNELS = 1
MAX_TOOL_ITERATIONS = 10
MAX_CONVERSATION_MESSAGES = 60  # trimmed to keep system + last 40

SYSTEM_PROMPT = """You are NAVIGATOR, tactical AI officer aboard a Silent Chaos submarine.
Speak in crisp military brevity — 1 to 3 sentences unless a full status report is requested.
Use NATO phonetic alphabet for bearings (e.g. "bearing zero-four-five", not "45 degrees").
Express urgency when the sub is in danger: low battery, hull damage, or incoming torpedo.

GAME CONTEXT:
- 2D submarine battlefield. Compass: 0=North, 90=East, 180=South, 270=West.
- Drones are your weapons: explosive=torpedo, detection=ISR, decoy=EMCON, emp=electronic warfare.
- Active sonar reveals your position. Passive sonar is stealthy but less precise.
- Battery is critical — snorkel to recharge but it raises acoustic signature.
- Depth matters: deeper = harder to detect.

TOOL RULES:
1. Always call get_state first when you need a sub_id or don't know current position.
2. After ping_sonar, call get_event_buffer with event_types=["echo"] and since_seconds=8 to read returns.
3. Resolve "my sub" or "the sub" from the most recent get_state result in conversation history.
4. Resolve "the torpedo" or "that drone" from the most recent launch_drone result in history.
5. Do NOT call login or signup — authentication is handled at startup.
6. Range defaults: close=800m, medium=2000m, long=4000m.

FIRST USER MESSAGE ONLY:
- Call get_rules once to learn game constants.
- Call has_subs to check if a sub is already registered.
- If no subs, call register_sub automatically.
- Report position and battery in 2 sentences, then await orders."""


# ── MCP Client ────────────────────────────────────────────────────────────────

class MCPClient:
    def __init__(self, url: str = MCP_URL):
        self.url = url
        self.session_id: str | None = None
        self._req_id = 0
        self._lock = threading.Lock()

    def _next_id(self) -> int:
        with self._lock:
            self._req_id += 1
            return self._req_id

    def _post(self, payload: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        resp = requests.post(self.url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        # Capture session ID from any response that carries it
        if "Mcp-Session-Id" in resp.headers and not self.session_id:
            self.session_id = resp.headers["Mcp-Session-Id"]
        if not resp.content:
            return {}
        return resp.json()

    def initialize(self) -> None:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "voice-bot", "version": "1.0"},
            },
        }
        self._post(payload)
        if not self.session_id:
            raise RuntimeError("MCP server did not return Mcp-Session-Id")

    def list_tools(self) -> list[dict]:
        payload = {"jsonrpc": "2.0", "id": self._next_id(), "method": "tools/list"}
        result = self._post(payload)
        return result.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> str:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        result = self._post(payload)
        rpc_result = result.get("result", {})
        if "error" in result:
            err = result["error"]
            return json.dumps({"ok": False, "error": err.get("message", str(err))})
        content = rpc_result.get("content", [])
        if content and content[0].get("type") == "text":
            return content[0]["text"]
        return json.dumps(rpc_result)


# ── Schema sanitization ───────────────────────────────────────────────────────

def _sanitize_schema(schema: dict) -> None:
    """Replace {"type": ["X", "null"]} with {"type": "X"} — OpenAI rejects union types."""
    if not isinstance(schema, dict):
        return
    if "type" in schema and isinstance(schema["type"], list):
        non_null = [t for t in schema["type"] if t != "null"]
        schema["type"] = non_null[0] if len(non_null) == 1 else non_null
    for value in schema.values():
        if isinstance(value, dict):
            _sanitize_schema(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _sanitize_schema(item)


def mcp_tools_to_openai(mcp_tools: list[dict]) -> list[dict]:
    result = []
    for t in mcp_tools:
        schema = copy.deepcopy(t.get("inputSchema", {"type": "object", "properties": {}}))
        _sanitize_schema(schema)
        result.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": schema,
            },
        })
    return result


# ── Audio capture ─────────────────────────────────────────────────────────────

def record_audio() -> np.ndarray:
    frames: list[np.ndarray] = []
    stop_event = threading.Event()

    def callback(indata, frame_count, time_info, status):
        frames.append(indata.copy())

    input("\n[Push-to-talk] Press Enter to start recording...")
    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS,
                             dtype="int16", callback=callback)
    stream.start()
    input("  Recording... Press Enter to stop.")
    stream.stop()
    stream.close()

    if not frames:
        return np.array([], dtype=np.int16)
    return np.concatenate(frames, axis=0).flatten()


# ── STT ───────────────────────────────────────────────────────────────────────

def transcribe(audio: np.ndarray, client: openai.OpenAI) -> str:
    if audio.size == 0:
        return ""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wavfile.write(tmp.name, SAMPLE_RATE, audio)
        tmp_path = tmp.name
    try:
        with open(tmp_path, "rb") as f:
            result = client.audio.transcriptions.create(model="whisper-1", file=f)
        return result.text.strip()
    finally:
        os.unlink(tmp_path)


# ── LLM turn with tool execution ──────────────────────────────────────────────

def run_llm_turn(
    openai_client: openai.OpenAI,
    conversation: list[dict],
    openai_tools: list[dict],
    mcp: MCPClient,
) -> str:
    for iteration in range(MAX_TOOL_ITERATIONS):
        kwargs: dict = dict(
            model=OPENAI_MODEL,
            messages=conversation,
        )
        if iteration < MAX_TOOL_ITERATIONS - 1:
            kwargs["tools"] = openai_tools
            kwargs["tool_choice"] = "auto"

        response = openai_client.chat.completions.create(**kwargs)
        msg = response.choices[0].message

        # Append assistant message to history
        conversation.append(msg.model_dump(exclude_unset=False, exclude_none=True))

        if not msg.tool_calls:
            return msg.content or ""

        # Execute tool calls
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            print(f"  [tool] {name}({json.dumps(args, separators=(',', ':'))})")
            try:
                result_text = mcp.call_tool(name, args)
            except Exception as exc:
                result_text = json.dumps({"ok": False, "error": str(exc)})
            conversation.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_text,
            })

    return "I've completed the requested actions."


# ── TTS playback ──────────────────────────────────────────────────────────────

def speak(text: str, client: openai.OpenAI) -> None:
    try:
        response = client.audio.speech.create(model="tts-1", voice=TTS_VOICE, input=text)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name
        try:
            _play_audio(tmp_path)
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        print(f"  [TTS error: {e}]")


def _play_audio(path: str) -> None:
    for cmd in [["mpg123", "-q", path], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]]:
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    print("  [Audio playback unavailable — install mpg123 or ffmpeg]")


# ── Conversation trim ─────────────────────────────────────────────────────────

def trim_conversation(conversation: list[dict]) -> None:
    if len(conversation) <= MAX_CONVERSATION_MESSAGES:
        return
    system = [m for m in conversation if m.get("role") == "system"]
    rest = [m for m in conversation if m.get("role") != "system"]
    keep = rest[-40:]
    conversation.clear()
    conversation.extend(system + keep)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("Error: OPENAI_API_KEY environment variable not set.")

    openai_client = openai.OpenAI(api_key=api_key)

    print("Connecting to Silent Chaos MCP server...")
    mcp = MCPClient()
    try:
        mcp.initialize()
    except Exception as e:
        sys.exit(f"Failed to connect to MCP server: {e}")

    tools_raw = mcp.list_tools()
    openai_tools = mcp_tools_to_openai(tools_raw)
    print(f"Connected. {len(openai_tools)} tools loaded.")

    username = input("Game username: ").strip()
    password = getpass.getpass("Game password: ")

    print("Logging in...")
    try:
        login_result = json.loads(mcp.call_tool("login", {"username": username, "password": password}))
    except Exception as e:
        sys.exit(f"Login error: {e}")
    if not login_result.get("ok"):
        sys.exit(f"Login failed: {login_result.get('error', 'unknown error')}")
    print("Logged in. NAVIGATOR online.\n")

    conversation: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Trigger startup sequence
    conversation.append({"role": "user", "content": "Initialize and report status."})
    print("NAVIGATOR initializing...")
    try:
        response_text = run_llm_turn(openai_client, conversation, openai_tools, mcp)
        print(f"\nNAVIGATOR: {response_text}\n")
        speak(response_text, openai_client)
    except Exception as e:
        print(f"[Startup error: {e}]")

    # Main voice loop
    while True:
        try:
            audio = record_audio()
            transcript = transcribe(audio, openai_client)
            if not transcript:
                print("  (no speech detected, try again)")
                continue
            print(f"\nYou: {transcript}")
            conversation.append({"role": "user", "content": transcript})
            response_text = run_llm_turn(openai_client, conversation, openai_tools, mcp)
            print(f"\nNAVIGATOR: {response_text}\n")
            speak(response_text, openai_client)
            trim_conversation(conversation)
        except KeyboardInterrupt:
            print("\nSigning off. Good hunting.")
            break
        except openai.APIError as e:
            print(f"[OpenAI error: {e}]")
        except Exception as e:
            print(f"[Error: {e}]")


if __name__ == "__main__":
    main()
