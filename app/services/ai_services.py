import os

from groq import Groq
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

        self.client = Groq(
            api_key=os.getenv("GROQ_API_KEY")
        )

        self.model = os.getenv(
            "MODEL_NAME",
            "llama-3.3-70b-versatile",
        )

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

    def chat(
        self,
        user_id: int,
        message: str,
        history_limit: int = 10,
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
            )
        )

        # -----------------------------------------------
        # 7. Call Groq
        # -----------------------------------------------

        response = (
            self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_completion_tokens=1024,
            )
        )

        # -----------------------------------------------
        # 8. Extract response
        # -----------------------------------------------

        assistant_response = (
            response.choices[0].message.content
        )

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

