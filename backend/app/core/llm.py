from openai import OpenAI
from .config import settings
from typing import Optional


class LLMClient:
    def __init__(self):
        self.client = None
        if settings.openai_api_key:
            self.client = OpenAI(api_key=settings.openai_api_key)
    
    def test_connection(self):
        """Test OpenAI API connection"""
        if not self.client:
            return False
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            return True
        except Exception as e:
            print(f"OpenAI API test failed: {e}")
            return False
    
    def generate_response(self, messages: list, model: str = "gpt-3.5-turbo"):
        """Generate response using OpenAI API"""
        if not self.client:
            raise Exception("OpenAI client not initialized")
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Response generation failed: {e}")
            return None


llm_client = LLMClient()