from typing import Optional, List, AsyncGenerator
import anthropic
from app.config import settings


class LLMClient:
    def __init__(self):
        self._client: Optional[anthropic.AsyncAnthropic] = None

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client

    async def complete(
        self,
        messages: List[dict],
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        response = await self.client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=max_tokens or settings.CLAUDE_MAX_TOKENS,
            system=system or "",
            messages=messages,
        )
        return response.content[0].text

    async def stream(
        self,
        messages: List[dict],
        system: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        async with self.client.messages.stream(
            model=settings.CLAUDE_MODEL,
            max_tokens=settings.CLAUDE_MAX_TOKENS,
            system=system or "",
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text


llm_client = LLMClient()
