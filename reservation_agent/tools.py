# tools.py
import os  # For accessing environment variables

import asyncpg  # type: ignore
import sqlalchemy
from google.adk.tools import ToolContext  # For accessing user context
from google.cloud.sql.connector import Connector, IPTypes
from opentelemetry import trace
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

tracer = trace.get_tracer("gcp.vertex.agent")

# note: the use of global state here introduces a potential race condition as
# access and initializing connector / engine is only protected by the GIL
connector = None
engine = None


async def get_engine() -> AsyncEngine:
    global connector, engine

    if not engine:
        conn_kwargs = {
            "user": os.environ.get("DB_USER"),
            "password": os.environ.get("DB_PASSWORD"),
            "db": os.environ.get("DB_NAME"),
        }
        connector = Connector()

        async def getconn() -> asyncpg.Connection:
            conn = await connector.connect_async(  # type: ignore
                os.environ.get("CLOUD_SQL_INSTANCE_CONNECTION_NAME", ""),
                "asyncpg",
                ip_type=IPTypes.PUBLIC,
                **conn_kwargs,
            )
            return conn

        engine = create_async_engine(
            "postgresql+asyncpg://",
            async_creator=getconn,
            pool_size=5,
            max_overflow=2,
            pool_timeout=30,
            pool_recycle=1800,
        )
    return engine


def get_user_id_from_context(tool_context: ToolContext) -> str:
    """Helper function to retrieve user_id from context."""
    user_id = tool_context.state["user_id"]
    return user_id


async def get_user_reservation_by_id(
    tool_context: ToolContext, reservation_id: str
) -> dict:
    """Fetches a specific reservation for the authenticated user using its
    unique reservation ID. Use this if the user provides a reservation ID or
    asks for details of one specific reservation. The function expects
    'reservation_id' as an argument.
    """
    # HERE IS WHERE user_id IS PASSED TO THE QUERY AS AN ARGUMENT INVISIBLE TO THE LLM.
    with tracer.start_as_current_span("validate-user-id") as span:
        tool_context.request_credential
        user_id = get_user_id_from_context(tool_context)

        span.set_attribute("user_id", user_id)

        if not user_id:
            return {"error": "I can only look up reservations if you're logged in,"}

        if not reservation_id:
            return {"error": "Reservation ID was not provided."}

    with tracer.start_span("get-engine") as span:
        pool = await get_engine()

    with tracer.start_as_current_span("pool-connect"):
        async with pool.connect() as conn:
            with tracer.start_as_current_span("pool-execute"):
                # Pass user_id from context into the the query
                result = await conn.execute(
                    sqlalchemy.text(
                        "SELECT id, user_id, reservation_details, reservation_date "
                        "FROM reservations "
                        "WHERE id = :reservation_id_param AND user_id = :user_id_param"
                    ),
                    {"reservation_id_param": reservation_id, "user_id_param": user_id},
                )
                reservation = result.fetchone()

    if not reservation:
        return {
            "message": f"No reservation found with ID {reservation_id} in your name."
        }

    return {
        "id": reservation.id,
        "user_id": reservation.user_id,
        "details": reservation.reservation_details,
        "date": str(reservation.reservation_date),
    }


async def get_latest_user_reservations(tool_context: ToolContext) -> dict:
    """Fetches the 3 most recent reservations for the authenticated user.
    Use this if the user asks for their latest, newest, or recent
    reservations.
    """
    with tracer.start_as_current_span("validate-user-id") as span:
        user_id = get_user_id_from_context(tool_context)
        if not user_id:
            return {"error": "I was unable to find any reservations under your name."}

    reservations_data: list[dict] = []

    with tracer.start_span("get-engine") as span:
        pool = await get_engine()
    
    with tracer.start_as_current_span("pool-connect"):
        async with pool.connect() as conn:
            with tracer.start_as_current_span("pool-execute"):
                # pass user_id from context into the the query
                result = await conn.execute(
                    sqlalchemy.text(
                        "SELECT id, user_id, reservation_details, reservation_date "
                        "FROM reservations "
                        "WHERE user_id = :user_id_param "
                        "ORDER BY reservation_date DESC "
                        "LIMIT 3"
                    ),
                    {"user_id_param": user_id},
                )

                for row in result:
                    reservations_data.append(
                        {
                            "id": row.id,
                            "user_id": row.user_id,
                            "details": row.reservation_details,
                            "date": str(row.reservation_date),
                        }
                    )

    if not reservations_data:
        return {"message": f"No reservations found for user {user_id}."}

    return {"reservations": reservations_data}
