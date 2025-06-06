# tools.py
import sqlalchemy
from sqlalchemy.orm import sessionmaker
from google.cloud.sql.connector import Connector, IPTypes
from google.adk.tools import ToolContext # For accessing user context

import config # The configuration file holding database credentials etc. not included for brevity

# Global connector and engine to manage the connection pool
connector = None
engine = None
SessionLocal = None

def init_connection_pool() -> None:
    """Initializes the Cloud SQL connection pool."""
    global connector, engine, SessionLocal

    if engine: # Already initialized
        return

    connector = Connector()

    def getconn() -> sqlalchemy.engine.base.Connection:
        conn_kwargs = {"user": config.DB_USER, "password": config.DB_PASSWORD, "db": config.DB_NAME}
        conn = connector.connect(
            config.CLOUD_SQL_INSTANCE_CONNECTION_NAME,
            config.DB_DRIVER, 
            ip_type=IPTypes.PUBLIC, 
            **conn_kwargs
        )
        return conn
"""Creates the Cloud SQL connection pool."""
    engine = sqlalchemy.create_engine(
        f"{config.DB_DRIVER.replace('pymysql', 'mysql+pymysql').replace('pg8000', 'postgresql+pg8000')}://",
        creator=getconn,
        pool_size=5,
        max_overflow=2,
        pool_timeout=30,
        pool_recycle=1800
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

init_connection_pool()

def get_user_id_from_context(tool_context: ToolContext) -> str | None:
    """Helper function to retrieve user_id from ToolContext."""
    user_id = None
    if tool_context and tool_context.state:
        user_id = tool_context.state.get("user_id_from_oauth") # Primary method
    
    # Fallback or alternative methods if your ADK setup provides user_id differently
    # For example, if user_id is directly on tool_context or in auth_response:
    # if not user_id and tool_context and hasattr(tool_context, 'user_id'):
    #     user_id = tool_context.user_id
    # if not user_id and tool_context and tool_context.auth_response:
    # user_id = tool_context.auth_response.get("user_id") # Or relevant field
    
    return user_id

def get_user_reservation_by_id(tool_context: ToolContext, reservation_id: str) -> dict:
    """
    Fetches a specific reservation by its ID for the authenticated user.
    Requires reservation_id as input.
    """
# HERE IS WHERE user_id IS PASSED TO THE QUERY AS AN ARGUMENT INVISIBLE TO THE LLM.
    user_id = get_user_id_from_context(tool_context)
    if not user_id:
        return {"error": "I can only look up reservations if you're logged in,"}

    if not reservation_id:
        return {"error": "Reservation ID was not provided."}

    if not SessionLocal:
        return {"error": "Database session not initialized."}

    db = SessionLocal()
    try:
        # Ensure reservation_id can be cast to integer if your DB column is an integer type
        try:
            # Assuming reservation_id in the database is an integer.
            # If it's a string, this conversion is not needed, but ensure your query matches.
            reservation_id_int = int(reservation_id)
        except ValueError:
            return {"error": f"Invalid reservation ID format: {reservation_id}. Expected an integer or numeric string."}

        stmt = sqlalchemy.text(
            "SELECT id, user_id, reservation_details, reservation_date "
            "FROM reservations "
            "WHERE id = :reservation_id_param AND user_id = :user_id_param"
        )
       # Pass user_id from context into the the query
        result = db.execute(stmt, {"reservation_id_param": reservation_id_int, "user_id_param": user_id})
        reservation = result.fetchone() 
        
        if reservation:
            return {
                "id": reservation.id,
                "user_id": reservation.user_id,
                "details": reservation.reservation_details,
                "date": str(reservation.reservation_date)
            }
        else:
            return {"message": f"No reservation found with ID {reservation_id} in your name."}

    except sqlalchemy.exc.SQLAlchemyError as e:
        print(f"Database query error: {e}")
        return {"error": f"An error occurred while fetching the reservation: {str(e)}"}
    except AttributeError as e:
        print(f"Data attribute error: {e}. Check column names.")
        return {"error": f"Error processing reservation data: {str(e)}"}
    finally:
        db.close()

def get_latest_user_reservations(tool_context: ToolContext) -> dict:
    """
    Fetches the 3 latest reservation details for the authenticated user.
    """
    user_id = get_user_id_from_context(tool_context)
    if not user_id:
        return {"error": "I was unable to find any reservations under your name."}

    if not SessionLocal:
        return {"error": "Database session not initialized."}

    db = SessionLocal()
    reservations_data = []
    try:
        # Fetch the 3 latest reservations, ordered by reservation_date descending
        stmt = sqlalchemy.text(
            "SELECT id, user_id, reservation_details, reservation_date "
            "FROM reservations "
            "WHERE user_id = :user_id_param "
            "ORDER BY reservation_date DESC "
            "LIMIT 3"
        )
        
        result = db.execute(stmt, {"user_id_param": user_id})
        for row in result:
            reservations_data.append({
                "id": row.id,
                "user_id": row.user_id,
                "details": row.reservation_details,
                "date": str(row.reservation_date)
            })
        
        if not reservations_data:
            return {"message": f"No reservations found for user {user_id}."}
        return {"reservations": reservations_data}

    except sqlalchemy.exc.SQLAlchemyError as e:
        print(f"Database query error: {e}")
        return {"error": f"An error occurred while fetching latest reservations: {str(e)}"}
    except AttributeError as e:
        print(f"Data attribute error: {e}. Check column names.")
        return {"error": f"Error processing reservation data: {str(e)}"}
    finally:
        db.close()