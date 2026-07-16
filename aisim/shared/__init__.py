"""Contracts shared between Hub and Agent: data models / Redis channel names / config.

Code under `shared/` is copied into both the Company Hub image and the Agent image,
so it must not depend on Hub-only or Agent-only modules.
"""
