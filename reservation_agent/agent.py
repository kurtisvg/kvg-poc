# agent.py
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from .tools import (
    get_latest_user_reservations,
    get_user_reservation_by_id,
)

# --- Tool for fetching a specific reservation by ID ---
# Note that same descriptions would need to be provided in MCP Toolbox YAML
fetch_reservation_by_id_tool = FunctionTool(get_user_reservation_by_id)

# --- Tool for fetching the latest reservations ---
# Note that same descriptions would need to be provided in MCP Toolbox YAML
fetch_latest_reservations_tool = FunctionTool(get_latest_user_reservations)

# Define the LLM Agent
root_agent = LlmAgent(
    model="gemini-2.5-pro-preview-03-25",
    name="ReservationsInquiryAgent",
    description="An agent that can look up a user's reservations, either a specific one by ID or their latest ones.",
    instruction=(
        "You are a helpful assistant for managing user reservations. "
        "The user must be authenticated for you to access their reservations. "
        "If the user provides a specific reservation ID (e.g., 'check reservation 123', 'details for my booking 456'), "
        "use the 'get_user_reservation_by_id' tool. You must extract the 'reservation_id' from the user's query and pass it to the tool. "
        "If the user asks for their 'latest reservations', 'recent bookings', or 'newest reservations', "
        "use the 'get_latest_user_reservations' tool. This tool does not require any arguments from you besides the context. "
        "If a tool returns an error about User ID, inform the user they might need to sign in or link their account. "
        "If no reservations are found, inform the user politely. "
        "Present any reservation details clearly."
    ),
    tools=[fetch_reservation_by_id_tool, fetch_latest_reservations_tool],
)
