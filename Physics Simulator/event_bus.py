"""
core/event_bus.py

A tiny synchronous publish/subscribe event bus used to decouple the physics
engine, the scene manager, and the UI from one another.

Why this exists
----------------
Without an event bus, the UI would need direct references to the physics
world, the renderer, and the scene manager - and vice versa. That creates a
tangle of imports and makes each piece hard to test or replace in isolation.

Instead, every module publishes events describing "what happened" (an object
was added, an object was selected, the sun moved, etc.) and any other module
that cares can subscribe to that event name. Nobody needs to know who is
listening.

Extension point
----------------
To add a new kind of notification, just publish a new string event name
from wherever it happens (`bus.publish("my.new.event", payload)`), and
subscribe to it wherever you need to react (`bus.subscribe("my.new.event",
callback)`). No changes to this file are required.
"""

from collections import defaultdict
from typing import Any, Callable, Dict, List


class EventBus:
    """A minimal synchronous event bus.

    Handlers are called synchronously, in subscription order, on the thread
    that calls `publish`. Exceptions raised by a handler are caught and
    printed so that one broken listener cannot take down the whole
    application (e.g. a buggy UI callback should not crash the physics
    step).
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[..., None]]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: Callable[..., None]) -> None:
        """Register `handler` to be called whenever `event_name` is published."""
        self._subscribers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: Callable[..., None]) -> None:
        """Remove a previously registered handler. Safe to call even if not present."""
        handlers = self._subscribers.get(event_name)
        if handlers and handler in handlers:
            handlers.remove(handler)

    def publish(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        """Notify all subscribers of `event_name`, passing along any arguments."""
        for handler in self._subscribers.get(event_name, ()):
            try:
                handler(*args, **kwargs)
            except Exception as exc:  # pragma: no cover - defensive guard
                print(f"[EventBus] handler for '{event_name}' raised: {exc}")


# A single shared bus for the whole application. Modules import this
# directly rather than passing a bus instance around everywhere - simple
# and sufficient for a single-process desktop app.
bus = EventBus()
