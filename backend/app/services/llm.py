"""Groq chat completions. The API key is read server-side only and never sent to the browser."""
from __future__ import annotations

import logging
import re
from typing import Protocol

from .prompts import ANSWER_SYSTEM_PROMPT, REWRITE_SYSTEM_PROMPT
from .vector_store import Passage

log = logging.getLogger("rag.llm")


class LLMError(Exception):
    """Message is safe to show to the user."""


class LLMClient(Protocol):
    def rewrite_question(self, history: list[dict], question: str) -> str: ...
    def answer(self, question: str, passages: list[Passage], history: list[dict]) -> str: ...


_TAG = re.compile(r"</?\s*context\s*>", re.IGNORECASE)


def build_context(passages: list[Passage]) -> str:
    """Label passages S1..Sn. Strip any <context> tags inside the text so a document can't break out of the block."""
    blocks = []
    for i, p in enumerate(passages, start=1):
        where = f"page {p.page}" if p.page else f"passage {p.chunk_index + 1}"
        safe = _TAG.sub("[tag removed]", p.text)
        blocks.append(f"[S{i}] ({p.filename}, {where})\n{safe}")
    return "<context>\n" + "\n\n".join(blocks) + "\n</context>"


class GroqLLM:
    def __init__(self, api_key: str, model: str, rewrite_model: str, timeout: float = 45.0):
        self.api_key = api_key
        self.model = model
        self.rewrite_model = rewrite_model
        self.timeout = timeout
        self._client = None

    def _get_client(self):
        if self._client is None:
            from groq import Groq

            self._client = Groq(api_key=self.api_key, timeout=self.timeout, max_retries=1)
        return self._client

    def _complete(self, model: str, messages: list[dict], max_tokens: int) -> str:
        import groq

        try:
            resp = self._get_client().chat.completions.create(
                model=model, messages=messages, temperature=0.1, max_tokens=max_tokens
            )
        except groq.AuthenticationError as exc:
            raise LLMError("Groq rejected the API key. Check GROQ_API_KEY in backend/.env.") from exc
        except groq.RateLimitError as exc:
            raise LLMError("Groq rate limit reached. Wait a moment and try again.") from exc
        except groq.NotFoundError as exc:
            raise LLMError(f"Groq model '{model}' was not found. Update GROQ_MODEL in backend/.env.") from exc
        except groq.APIConnectionError as exc:
            raise LLMError("Could not reach Groq. Check your internet connection.") from exc
        except groq.APIError as exc:
            raise LLMError("The language model request failed. Please try again.") from exc
        content = (resp.choices[0].message.content or "").strip()
        if not content:
            raise LLMError("The language model returned an empty answer. Please try again.")
        return content

    def rewrite_question(self, history: list[dict], question: str) -> str:
        transcript = "\n".join(f"{m['role']}: {m['content'][:500]}" for m in history[-6:])
        messages = [
            {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Chat history:\n{transcript}\n\nLatest question: {question}"},
        ]
        rewritten = self._complete(self.rewrite_model, messages, max_tokens=120)
        return rewritten.strip().strip('"')[:500] or question

    def answer(self, question: str, passages: list[Passage], history: list[dict]) -> str:
        messages: list[dict] = [{"role": "system", "content": ANSWER_SYSTEM_PROMPT}]
        # History gives conversational continuity, but facts must still come from <context>.
        messages += [{"role": m["role"], "content": m["content"][:1500]} for m in history[-6:]]
        messages.append(
            {"role": "user", "content": f"{build_context(passages)}\n\nQuestion: {question}"}
        )
        return self._complete(self.model, messages, max_tokens=700)
