import json
import os

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

from app.services.prompt_builder import (
    PromptBuilder,
)

from app.services.yahoo_service import (
    YahooFinanceService,
)


class AIService:
    """
    Orchestrates the complete AI conversation flow.

    Responsibilities:

    1. Load user
    2. Load user preferences
    3. Load watchlist
    4. Load conversation history
    5. Ask PromptBuilder to build messages
    6. Call Groq
    7. Save conversation
    8. Return AI response

    AIService does NOT contain the actual system prompt.
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
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_quote",
                    "description": "Get current stock price and quote details for a ticker symbol.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticker": {"type": "string", "description": "The stock ticker symbol (e.g. AAPL)"}
                        },
                        "required": ["ticker"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_history",
                    "description": "Get historical stock price data for a ticker.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticker": {"type": "string"},
                            "period": {"type": "string", "description": "Period (e.g. 1mo, 1y)"},
                            "interval": {"type": "string", "description": "Interval (e.g. 1d)"}
                        },
                        "required": ["ticker"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_financials",
                    "description": "Get financial statements for a ticker.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticker": {"type": "string"}
                        },
                        "required": ["ticker"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_news",
                    "description": "Get latest news for a ticker.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticker": {"type": "string"}
                        },
                        "required": ["ticker"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_research",
                    "description": "Get research, recommendations, and sector information for a ticker.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticker": {"type": "string"}
                        },
                        "required": ["ticker"]
                    }
                }
            }
        ]

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
        """
        Complete AI conversation workflow.

        User Question
              ↓
        Load User
              ↓
        Load Preferences
              ↓
        Load Watchlist
              ↓
        Load History
              ↓
        PromptBuilder
              ↓
        Groq
              ↓
        Save Conversation
              ↓
        Return Response
        """

        # -----------------------------------------------
        # 1. Load user
        # -----------------------------------------------

        user = (
            self.user_repository.get_by_id(
                user_id
            )
        )

        if not user:
            raise ValueError(
                f"User with id {user_id} not found."
            )

        # -----------------------------------------------
        # 2. Load user preferences
        # -----------------------------------------------

        user_preference = (
            self.preference_repository.get_by_user_id(
                user_id
            )
        )

        # -----------------------------------------------
        # 3. Load watchlist
        # -----------------------------------------------

        watchlist = (
            self.watchlist_repository.get_by_user_id(
                user_id
            )
        )

        # -----------------------------------------------
        # 4. Load conversation history
        # -----------------------------------------------

        history = (
            self.conversation_service.get_recent_messages(
                user_id=user_id,
                limit=history_limit,
            )
        )

        # -----------------------------------------------
        # 5. Build personalized system prompt
        # -----------------------------------------------

        system_prompt = (
            self.prompt_builder.build_system_prompt(
                user=user,
                user_preference=user_preference,
                watchlist=watchlist,
            )
        )

        # -----------------------------------------------
        # 6. Build complete Groq messages
        # -----------------------------------------------

        messages = (
            self.prompt_builder.build_messages(
                system_prompt=system_prompt,
                history=history,
                current_question=message,
                base64_image=base64_image,
            )
        )

        # Temporarily use vision model if image is provided
        current_model = self.model
        if base64_image:
            current_model = "llama-3.2-90b-vision-preview"

        # -----------------------------------------------
        # 7. Call Groq
        # -----------------------------------------------

        max_iterations = 5
        assistant_response = None
        for _ in range(max_iterations):
            response = await self.client.chat.completions.create(
                model=current_model,
                messages=messages,
                temperature=0.3,
                max_completion_tokens=700,
                tools=self.tools,
                tool_choice="auto",
            )

            # -----------------------------------------------
            # 8. Extract response & Handle Tool Calls
            # -----------------------------------------------

            response_message = response.choices[0].message

            if not response_message.tool_calls:
                assistant_response = response_message.content
                break

            message_dict = {
                "role": response_message.role,
                "content": response_message.content or "",
                "tool_calls": [
                    {
                        "id": t.id,
                        "type": t.type,
                        "function": {
                            "name": t.function.name,
                            "arguments": t.function.arguments,
                        }
                    } for t in response_message.tool_calls
                ]
            }
            messages.append(message_dict)

            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)

                tool_result = ""
                try:
                    if function_name == "get_quote":
                        res = await self.yahoo_service.quote(ticker=function_args.get("ticker"))
                        tool_result = json.dumps(res)
                    elif function_name == "get_history":
                        res = await self.yahoo_service.history(
                            ticker=function_args.get("ticker"), 
                            period=function_args.get("period", "1mo"),
                            interval=function_args.get("interval", "1d")
                        )
                        tool_result = json.dumps(res)
                    elif function_name == "get_financials":
                        res = await self.yahoo_service.financials(ticker=function_args.get("ticker"))
                        tool_result = json.dumps(res)
                    elif function_name == "get_news":
                        res = await self.yahoo_service.news(ticker=function_args.get("ticker"))
                        tool_result = json.dumps(res)
                    elif function_name == "get_research":
                        res = await self.yahoo_service.research(ticker=function_args.get("ticker"))
                        tool_result = json.dumps(res)
                    else:
                        tool_result = f"Unknown function: {function_name}"
                except Exception as e:
                    tool_result = f"Error calling function {function_name}: {str(e)}"

                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": tool_result or "{}",
                    }
                )
        else:
            assistant_response = "I had to call too many functions and couldn't finish."

        if not assistant_response:

            raise ValueError(
                "Groq returned an empty response."
            )

        # -----------------------------------------------
        # 9. Save conversation
        # -----------------------------------------------

        self.conversation_service.save_exchange(
            user_id=user_id,
            user_message=message,
            assistant_response=assistant_response,
        )

        # -----------------------------------------------
        # 10. Return response
        # -----------------------------------------------

        return assistant_response

