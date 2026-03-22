"""
decision_engine.py - Decision Model (Brain) placeholder.

In the future this module will analyse the user's input and decide
what action to take (respond, search, react, stay silent, etc.).

For now it simply passes the transcription through as a "respond"
instruction.
"""


def decide(transcription: str) -> dict:
    """
    Decide what action to take based on the user's transcription.

    Args:
        transcription: The text from the STT module.

    Returns:
        An instruction dict consumed by the response engine.

        Current structure (placeholder):
            {
                "action": "respond",
                "input":  <transcription text>
            }

        Future fields may include: emotion, context, memory refs, etc.
    """
    # -------------------------------------------------------------------
    # PLACEHOLDER – no decision logic yet.
    # Replace this with the real decision model in a future iteration.
    # -------------------------------------------------------------------
    instruction = {
        "action": "respond",
        "input": transcription,
    }

    print(f"🧠  Decision: {instruction['action']}")
    return instruction
