import os
from groq import AsyncGroq

class AudioService:
    def __init__(self):
        self.client = AsyncGroq(
            api_key=os.getenv("GROQ_API_KEY")
        )
        self.model = "whisper-large-v3"

    async def transcribe(self, file_bytes: bytes, filename: str = "audio.ogg") -> str:
        """
        Transcribe an audio file using Groq's Whisper model.
        """
        # Groq's API expects a tuple of (filename, bytes) or a file-like object
        audio_tuple = (filename, file_bytes)
        
        try:
            transcription = await self.client.audio.transcriptions.create(
                file=audio_tuple,
                model=self.model,
                response_format="json",
            )
            return transcription.text
        except Exception as e:
            raise ValueError(f"Failed to transcribe audio: {str(e)}")
