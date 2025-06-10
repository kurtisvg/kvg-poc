# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import os
import time

from google.adk.agents.run_config import RunConfig
from google.adk.runners import InMemoryRunner
from google.adk.sessions import Session
from google.genai import types
from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.sdk.trace import TracerProvider, export

from reservation_agent import agent


async def run_prompt(
    runner: InMemoryRunner, session: Session, user_id: str, new_message: str
):
    """Helper function to run a prompt."""
    content = types.Content(role="user", parts=[types.Part.from_text(text=new_message)])
    print("** User says:", content.model_dump(exclude_none=True))
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=content,
    ):
        print(event)
        if event.content and event.content.parts and event.content.parts[0].text:
            print(f"** {event.author}: {event.content.parts[0].text}")


async def main():
    app_name = "my_app"
    user_id = "user1"
    runner = InMemoryRunner(
        agent=agent.root_agent,
        app_name=app_name,
    )

    # WARNING: don't use 'user:id' as that will cause the token to persist the rest of
    # the session for the user
    state = {"user_token": os.environ.get("MY_OAUTH2_TOKEN")}

    session = await runner.session_service.create_session(
        app_name=app_name, user_id=user_id, state=state
    )

    session.state["user:id"] = "user_123"

    await run_prompt(runner, session, user_id, "Hi")
    await run_prompt(runner, session, user_id, "Please lookup my recent reservations.")


if __name__ == "__main__":
    # ADK doesn't provide a way to configure telemetry without adding a custom runner

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT environment variable is not set.")

    print(f"Tracing to project{project_id}")

    provider = TracerProvider()
    processor = export.BatchSpanProcessor(CloudTraceSpanExporter(project_id=project_id))
    # processor = export.SimpleSpanProcessor(export.ConsoleSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    asyncio.run(main())

    provider.force_flush()
    print("Done tracing to project", project_id)
