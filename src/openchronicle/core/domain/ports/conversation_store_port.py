from __future__ import annotations

from abc import ABC, abstractmethod

from openchronicle.core.domain.models.conversation import Conversation, Turn


class ConversationStorePort(ABC):
    @abstractmethod
    def add_conversation(self, conversation: Conversation) -> None: ...

    @abstractmethod
    def get_conversation(self, conversation_id: str) -> Conversation | None: ...

    @abstractmethod
    def list_conversations(self, limit: int | None = None) -> list[Conversation]: ...

    @abstractmethod
    def get_conversation_mode(self, conversation_id: str) -> str: ...

    @abstractmethod
    def set_conversation_mode(self, conversation_id: str, mode: str) -> None: ...

    @abstractmethod
    def add_turn(self, turn: Turn) -> None: ...

    @abstractmethod
    def next_turn_index(self, conversation_id: str) -> int: ...

    @abstractmethod
    def list_turns(self, conversation_id: str, limit: int | None = None) -> list[Turn]: ...

    @abstractmethod
    def get_turn_by_index(self, conversation_id: str, turn_index: int) -> Turn | None: ...

    @abstractmethod
    def link_memory_to_turn(self, turn_id: str, memory_id: str) -> None: ...
