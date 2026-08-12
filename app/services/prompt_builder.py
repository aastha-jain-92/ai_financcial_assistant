from typing import Any, Dict, List


class PromptBuilder:
    """
    Responsible only for constructing prompts/messages
    for the AI model.

    This class does NOT:
    - access the database
    - call Groq
    - save conversations
    - access Telegram
    """

    BASE_SYSTEM_PROMPT = """
You are FinMate, an AI Financial Assistant.

Your role is to provide clear, educational and responsible
financial information.

IMPORTANT RULES:

1. Use the user's profile and preferences whenever relevant.

2. When the user asks a general question about "the market",
   interpret "the market" using the user's preferred market.

3. If the user explicitly asks about another market,
   follow the user's explicit request.

4. Use the user's watchlist when relevant.

5. Do not claim to be a licensed financial advisor.

6. Do not provide guaranteed returns.

7. Do not present personalized investment recommendations
   as guaranteed or professional financial advice.

8. When uncertain, clearly say so.

9. Never invent current prices, market movements,
   earnings figures, or other financial data. However, you
   MAY use your internal knowledge to answer general questions
   about consumer products, technology, or historical facts.

10. Use previous conversation history to understand
    follow-up questions naturally.

11. Answer the user's LATEST question directly. Do not
    simply repeat your previous answers.
"""

    def build_system_prompt(
        self,
        user: Any,
        user_preference: Any = None,
        watchlist: List[Any] | None = None,
    ) -> str:
        """
        Build a personalized system prompt.

        This method only transforms supplied data into text.
        """

        watchlist = watchlist or []

        # -----------------------------------------------
        # User information
        # -----------------------------------------------

        user_name = (
            getattr(user, "full_name", None)
            or "User"
        )

        # -----------------------------------------------
        # Preference information
        # -----------------------------------------------

        role = (
            getattr(user_preference, "role", None)
            or "Not specified"
        )

        market = (
            getattr(user_preference, "market", None)
            or "Not specified"
        )

        # -----------------------------------------------
        # Watchlist
        # -----------------------------------------------

        companies = self._extract_watchlist(
            watchlist
        )

        watchlist_text = (
            ", ".join(companies)
            if companies
            else "No companies specified"
        )

        # -----------------------------------------------
        # Build prompt
        # -----------------------------------------------

        return f"""
{self.BASE_SYSTEM_PROMPT}

========================================
USER PROFILE
========================================

Name:
{user_name}

Role:
{role}

Preferred Market:
{market}

Watchlist:
{watchlist_text}

========================================
PERSONALIZATION
========================================

The user's preferred market is:

{market}

When the user asks broad questions such as:

"What is today's market?"
"How is the market doing?"
"What's happening in the market?"

interpret "the market" as:

{market}

If the preferred market is Indian Market,
focus on Indian markets such as NIFTY, SENSEX,
NSE and BSE when relevant.

If the preferred market is US Market,
focus on US markets such as S&P 500, NASDAQ
and Dow Jones when relevant.

If the preferred market is Global,
provide a broader international perspective.

The user's watchlist is:

{watchlist_text}

Use the watchlist when relevant to the user's question.

If the user explicitly asks about another market,
follow that explicit request instead of the preferred market.

Do not invent real-time or current market information.
For general knowledge and product information (like the latest iPhone),
you may use your internal knowledge if the provided tools do not return relevant data.
"""

    @staticmethod
    def _extract_watchlist(
        watchlist: List[Any],
    ) -> List[str]:
        """
        Convert watchlist records/objects into company names.
        """

        companies: List[str] = []

        for item in watchlist:

            # If repository returns strings
            if isinstance(item, str):
                companies.append(item)
                continue

            # Support common model field names
            company_name = (
                getattr(
                    item,
                    "company_name",
                    None,
                )
                or getattr(
                    item,
                    "symbol",
                    None,
                )
                or getattr(
                    item,
                    "name",
                    None,
                )
            )

            if company_name:
                companies.append(
                    str(company_name)
                )

        return companies

    def build_messages(
        self,
        system_prompt: str,
        history: List[Any],
        current_question: str,
        base64_image: str = None,
    ) -> List[Dict[str, str]]:
        """
        Build the final messages sent to the LLM.

        Order:

        System Prompt
             ↓
        Conversation History
             ↓
        Current Question
        """

        messages: List[Dict[str, str]] = []

        # -----------------------------------------------
        # System prompt
        # -----------------------------------------------

        messages.append(
            {
                "role": "system",
                "content": system_prompt,
            }
        )

        # -----------------------------------------------
        # Conversation history
        # -----------------------------------------------

        for conversation in history:

            if conversation.role not in {
                "user",
                "assistant",
            }:
                continue

            messages.append(
                {
                    "role": conversation.role,
                    "content": conversation.message,
                }
            )

        # -----------------------------------------------
        # Current question
        # -----------------------------------------------

        if base64_image:
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"New Question: {current_question}"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        },
                    ],
                }
            )
        else:
            messages.append(
                {
                    "role": "user",
                    "content": f"New Question: {current_question}",
                }
            )

        return messages

