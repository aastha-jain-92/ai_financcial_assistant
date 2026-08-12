import asyncio
import json
import logging
import os
from typing import Any, Dict, List

from groq import AsyncGroq
from sqlalchemy.orm import Session

from app.repositories.user_repository import (
    SQLAlchemyUserRepository,
)

from app.repositories.user_preference_repository import (
    SQLAlchemyUserPreferenceRepository,
)

from app.repositories.watchlist_repository import (
    SQLAlchemyWatchlistRepository,
)

from app.services.conversation_service import (
    ConversationService,
)

from app.services.google.google_service import (
    GoogleDataService,
)

from app.services.prompt_builder import (
    PromptBuilder,
)

from app.services.tools import (
    ToolRegistry,
    build_finance_tools,
    build_google_tools,
    google_tools_prompt,
)

from app.services.yahoo_service import (
    YahooFinanceService,
)

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = int(os.getenv("MAX_TOOL_ITERATIONS", "5"))
VISION_MODEL = os.getenv(
    "VISION_MODEL_NAME",
    "meta-llama/llama-4-scout-17b-16e-instruct",
)


class AIService:
    """
    Orchestrates the complete AI conversation flow.

    User question (Telegram)
          ↓
    Load user, preferences, watchlist, history
          ↓
    Build prompt + the tool set the user actually has access to
    (market data + their connected Google services)
          ↓
    Groq decides which tools to call
          ↓
    Tools hit Yahoo Finance / Google APIs with the user's OAuth token
          ↓
    Results are fed back to Groq
          ↓
    Final answer is saved and returned to Telegram
    """

    def __init__(self, db: Session):

        self.db = db

        # -----------------------------------------------
        # Groq client
        # -----------------------------------------------

        self.client = AsyncGroq(
            api_key=os.getenv("GROQ_API_KEY")
        )

        self.model = os.getenv(
            "MODEL_NAME",
            "openai/gpt-oss-120b",
        )

        self.yahoo_service = YahooFinanceService()

        # -----------------------------------------------
        # Repositories
        # -----------------------------------------------

        self.user_repository = (
            SQLAlchemyUserRepository(db)
        )

        self.preference_repository = (
            SQLAlchemyUserPreferenceRepository(db)
        )

        self.watchlist_repository = (
            SQLAlchemyWatchlistRepository(db)
        )

        # -----------------------------------------------
        # Services
        # -----------------------------------------------

        self.conversation_service = (
            ConversationService(db)
        )

        # -----------------------------------------------
        # Prompt Builder
        # -----------------------------------------------

        self.prompt_builder = PromptBuilder()

    # ===================================================
    # MAIN CHAT METHOD
    # ===================================================

    async def chat(
        self,
        user_id: int,
        message: str,
        history_limit: int = 10,
        base64_image: str = None,
    ) -> str:

        user = self.user_repository.get_by_id(user_id)

        if not user:
            raise ValueError(
                f"User with id {user_id} not found."
            )

        user_preference = (
            self.preference_repository.get_by_user_id(user_id)
        )

        watchlist = (
            self.watchlist_repository.get_by_user_id(user_id)
        )

        history = (
            self.conversation_service.get_recent_messages(
                user_id=user_id,
                limit=history_limit,
            )
        )

        # -----------------------------------------------
        # Tools available to this specific user
        # -----------------------------------------------

        google_service = GoogleDataService(self.db, user_id)
        connected_services = google_service.connected_services()

        registry = ToolRegistry(
            build_finance_tools(self.yahoo_service)
        )
        registry.extend(
            build_google_tools(google_service, connected_services)
        )

        # -----------------------------------------------
        # Prompt
        # -----------------------------------------------

        system_prompt = (
            self.prompt_builder.build_system_prompt(
                user=user,
                user_preference=user_preference,
                watchlist=watchlist,
            )
            + "\n\n"
            + google_tools_prompt(connected_services)
        )

        messages = self.prompt_builder.build_messages(
            system_prompt=system_prompt,
            history=history,
            current_question=message,
            base64_image=base64_image,
        )

        # Vision requests use a different model that has no tool support.
        current_model = VISION_MODEL if base64_image else self.model
        tools_enabled = not base64_image

        assistant_response = await self._run_completion_loop(
            model=current_model,
            messages=messages,
            registry=registry,
            tools_enabled=tools_enabled,
        )

        self.conversation_service.save_exchange(
            user_id=user_id,
            user_message=message,
            assistant_response=assistant_response,
        )

        return assistant_response

    # ===================================================
    # GROQ + TOOL CALLING LOOP
    # ===================================================

    async def _run_completion_loop(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        registry: ToolRegistry,
        tools_enabled: bool,
    ) -> str:

        for iteration in range(MAX_TOOL_ITERATIONS):

            request: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": 0.3,
                "max_completion_tokens": 700,
            }

            if tools_enabled and len(registry):
                request["tools"] = registry.schemas
                request["tool_choice"] = "auto"

            response = await self.client.chat.completions.create(
                **request
            )

            response_message = response.choices[0].message
            tool_calls = getattr(
                response_message, "tool_calls", None
            )

            if not tool_calls:
                content = (response_message.content or "").strip()

                if content:
                    return content

                logger.warning(
                    "Groq returned an empty response (iteration %s)",
                    iteration,
                )
                return (
                    "I couldn't produce an answer for that. "
                    "Could you rephrase your question?"
                )

            messages.append(
                {
                    "role": "assistant",
                    "content": response_message.content or "",
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": call.type,
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments,
                            },
                        }
                        for call in tool_calls
                    ],
                }
            )

            results = await asyncio.gather(
                *[
                    registry.execute(
                        call.function.name,
                        _parse_arguments(call.function.arguments),
                    )
                    for call in tool_calls
                ]
            )

            for call, result in zip(tool_calls, results):
                messages.append(
                    {
                        "tool_call_id": call.id,
                        "role": "tool",
                        "name": call.function.name,
                        "content": result,
                    }
                )

        logger.warning(
            "Tool-calling loop hit the %s iteration limit",
            MAX_TOOL_ITERATIONS,
        )

        return (
            "I looked up quite a lot of data but couldn't finish the "
            "answer. Could you narrow the question down a little?"
        )


def _parse_arguments(raw_arguments: str) -> Dict[str, Any]:

    if not raw_arguments:
        return {}

    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError:
        logger.warning("Invalid tool arguments: %s", raw_arguments)
        return {}

    return parsed if isinstance(parsed, dict) else {}
