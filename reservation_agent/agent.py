# agent.py
import os

from google.adk.agents import LlmAgent
from toolbox_core import ToolboxSyncClient


def get_oauth2_token():
    return os.environ.get("MY_OAUTH2_TOKEN", "")


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
    tools=ToolboxSyncClient("http://127.0.0.1:5000").load_toolset(  # type: ignore
        auth_token_getters={"my-google-auth": get_oauth2_token}
    ),
)
