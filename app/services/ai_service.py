"""
AI Service Layer for FansFunFoffer
Handles AI-powered question summarization, sentiment analysis, and multilingual processing
using Azure OpenAI, Azure Speech Services, and Azure Translator.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from uuid import UUID
import json

from openai import AzureOpenAI
from azure.cognitiveservices.speech import (
    SpeechConfig, 
    AudioConfig, 
    SpeechRecognizer,
    ResultReason,
    AutoDetectSourceLanguageConfig
)
import requests

from app.core.config import settings

logger = logging.getLogger(__name__)


class AIService:
    """Azure AI service for processing fan questions."""
    
    def __init__(self):
        """Initialize Azure AI clients."""
        # Azure OpenAI client (following official Azure sample pattern)
        if settings.azure_openai_api_key and settings.azure_openai_endpoint:
            try:
                # Try standard initialization
                self.openai_client = AzureOpenAI(
                    api_version=settings.azure_openai_api_version,
                    azure_endpoint=settings.azure_openai_endpoint,
                    api_key=settings.azure_openai_api_key
                )
                logger.info("Azure OpenAI client initialized successfully")
            except TypeError as e:
                # Fallback: Some environments may have issues with certain parameters
                logger.warning(f"Standard OpenAI init failed ({e}), trying minimal init")
                try:
                    # Minimal initialization without optional parameters
                    self.openai_client = AzureOpenAI(
                        azure_endpoint=settings.azure_openai_endpoint,
                        api_key=settings.azure_openai_api_key,
                        api_version=settings.azure_openai_api_version
                    )
                    logger.info("Azure OpenAI client initialized with fallback method")
                except Exception as fallback_error:
                    logger.error(f"All OpenAI initialization methods failed: {fallback_error}")
                    self.openai_client = None
        else:
            self.openai_client = None
            logger.warning("Azure OpenAI credentials not configured")
        
        # Azure Speech config
        if settings.azure_speech_key and settings.azure_speech_region:
            self.speech_config = SpeechConfig(
                subscription=settings.azure_speech_key,
                region=settings.azure_speech_region
            )
        else:
            self.speech_config = None
            logger.warning("Azure Speech credentials not configured")
    
    async def detect_language(self, text: str) -> str:
        """
        Detect language from text using Azure Translator.
        
        Args:
            text: Input text
            
        Returns:
            Language code (e.g., 'en', 'te', 'hi')
        """
        if not settings.azure_translator_key:
            logger.warning("Azure Translator not configured, defaulting to English")
            return "en"
        
        try:
            endpoint = f"{settings.azure_translator_endpoint}/detect"
            headers = {
                'Ocp-Apim-Subscription-Key': settings.azure_translator_key,
                'Ocp-Apim-Subscription-Region': settings.azure_translator_region,
                'Content-type': 'application/json'
            }
            body = [{'text': text[:1000]}]  # Limit to 1000 chars for detection
            
            response = requests.post(
                endpoint, 
                headers=headers, 
                json=body, 
                params={'api-version': '3.0'},
                timeout=10
            )
            response.raise_for_status()
            
            result = response.json()
            if result and len(result) > 0:
                detected_lang = result[0]['language']
                logger.info(f"Detected language: {detected_lang}")
                return detected_lang
            
            return "en"
        except Exception as e:
            logger.error(f"Language detection failed: {str(e)}")
            return "en"
    
    async def translate_text(self, text: str, target_language: str = "en", source_language: Optional[str] = None) -> str:
        """
        Translate text using Azure Translator.
        
        Args:
            text: Text to translate
            target_language: Target language code
            source_language: Source language code (optional, auto-detect if None)
            
        Returns:
            Translated text
        """
        if not settings.azure_translator_key:
            logger.warning("Azure Translator not configured, returning original text")
            return text
        
        try:
            endpoint = f"{settings.azure_translator_endpoint}/translate"
            headers = {
                'Ocp-Apim-Subscription-Key': settings.azure_translator_key,
                'Ocp-Apim-Subscription-Region': settings.azure_translator_region,
                'Content-type': 'application/json'
            }
            params = {
                'api-version': '3.0',
                'to': target_language
            }
            if source_language:
                params['from'] = source_language
            
            body = [{'text': text}]
            
            response = requests.post(
                endpoint, 
                headers=headers, 
                json=body, 
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            result = response.json()
            if result and len(result) > 0 and 'translations' in result[0]:
                translated = result[0]['translations'][0]['text']
                logger.info(f"Translated from {source_language or 'auto'} to {target_language}")
                return translated
            
            return text
        except Exception as e:
            logger.error(f"Translation failed: {str(e)}")
            return text
    
    async def transcribe_audio_from_url(self, audio_url: str, language_hint: Optional[str] = None) -> Dict[str, Any]:
        """
        Transcribe audio from URL using Azure Speech Services.
        
        Args:
            audio_url: URL to audio file
            language_hint: Optional language hint (e.g., 'te-IN', 'hi-IN', 'en-US')
            
        Returns:
            Dict with 'transcription', 'language', and 'translation' (if not English)
        """
        if not self.speech_config:
            logger.error("Azure Speech not configured")
            return {
                'transcription': '',
                'language': 'en',
                'translation': '',
                'error': 'Azure Speech not configured'
            }
        
        try:
            import tempfile
            import os
            from azure.cognitiveservices.speech import AudioConfig, SpeechRecognizer
            
            logger.info(f"Transcribing audio from: {audio_url}")
            
            # 1. Download audio file from URL
            response = requests.get(audio_url, timeout=30)
            response.raise_for_status()
            
            # 2. Save to temporary file (WebM format from browser)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_webm:
                temp_webm.write(response.content)
                temp_webm_path = temp_webm.name
            
            # 3. Convert WebM to WAV for Azure Speech SDK compatibility
            try:
                from pydub import AudioSegment
                
                # Load WebM and convert to WAV
                audio = AudioSegment.from_file(temp_webm_path, format="webm")
                
                # Export as WAV (16kHz, mono, 16-bit for best Speech SDK compatibility)
                temp_wav_path = temp_webm_path.replace('.webm', '.wav')
                audio.export(
                    temp_wav_path,
                    format="wav",
                    parameters=["-ar", "16000", "-ac", "1"]
                )
                
                logger.info(f"Converted WebM to WAV: {temp_wav_path}")
                
            except ImportError:
                logger.warning("pydub not available, trying WebM directly (may fail)")
                temp_wav_path = temp_webm_path
            except Exception as e:
                logger.error(f"Audio conversion failed: {e}, trying WebM directly")
                temp_wav_path = temp_webm_path
            
            try:
                # 4. Configure audio input
                audio_config = AudioConfig(filename=temp_wav_path)
                
                # 5. Set up auto language detection for Indian languages + English
                if language_hint:
                    # Use specific language if provided
                    self.speech_config.speech_recognition_language = language_hint
                    speech_recognizer = SpeechRecognizer(
                        speech_config=self.speech_config,
                        audio_config=audio_config
                    )
                else:
                    # Auto-detect from common Indian languages + English
                    auto_detect_config = AutoDetectSourceLanguageConfig(
                        languages=["en-US", "hi-IN", "te-IN"]
                    )
                    speech_recognizer = SpeechRecognizer(
                        speech_config=self.speech_config,
                        audio_config=audio_config,
                        auto_detect_source_language_config=auto_detect_config
                    )
                
                # 6. Perform transcription
                result = speech_recognizer.recognize_once()
                
                # 7. Process result
                if result.reason == ResultReason.RecognizedSpeech:
                    transcription = result.text
                    detected_language = result.language if hasattr(result, 'language') else (language_hint or 'en-US')
                    
                    logger.info(f"Transcription successful: {transcription[:100]}...")
                    
                    # 8. Translate to English if needed
                    translation = ''
                    if not detected_language.startswith('en'):
                        translation = await self.translate_text(
                            transcription,
                            source_language=detected_language[:2],
                            target_language='en'
                        )
                    
                    return {
                        'transcription': transcription,
                        'language': detected_language,
                        'translation': translation
                    }
                elif result.reason == ResultReason.Canceled:
                    # Get detailed cancellation reason
                    cancellation = result.cancellation_details
                    error_details = f"Cancellation reason: {cancellation.reason}"
                    if cancellation.error_details:
                        error_details += f", Error: {cancellation.error_details}"
                    
                    logger.error(f"Speech recognition canceled: {error_details}")
                    return {
                        'transcription': '',
                        'language': language_hint or 'en',
                        'translation': '',
                        'error': error_details
                    }
                else:
                    logger.warning(f"Speech recognition failed: {result.reason}")
                    return {
                        'transcription': '',
                        'language': language_hint or 'en',
                        'translation': '',
                        'error': f'Recognition failed: {result.reason}'
                    }
            finally:
                # Clean up temporary files
                if os.path.exists(temp_webm_path):
                    os.unlink(temp_webm_path)
                if 'temp_wav_path' in locals() and os.path.exists(temp_wav_path) and temp_wav_path != temp_webm_path:
                    os.unlink(temp_wav_path)
        except Exception as e:
            logger.error(f"Audio transcription failed: {str(e)}")
            return {
                'transcription': '',
                'language': 'en',
                'translation': '',
                'error': str(e)
            }
    
    async def summarize_question(
        self, 
        text: str, 
        creator_language: str = "en",
        include_sentiment: bool = True
    ) -> Dict[str, Any]:
        """
        Generate AI summary of fan question using Azure OpenAI.
        
        Args:
            text: Combined question text (from all sources)
            creator_language: Creator's preferred language for summary
            include_sentiment: Whether to include sentiment analysis
            
        Returns:
            Dict with 'summary', 'sentiment', 'stakes', 'key_points'
        """
        if not self.openai_client:
            logger.error("Azure OpenAI not configured")
            return {
                'summary': text[:200] + '...' if len(text) > 200 else text,
                'sentiment': 'neutral',
                'stakes': 'medium',
                'key_points': [],
                'error': 'Azure OpenAI not configured'
            }
        
        try:
            # Build prompt for summarization
            prompt = f"""You are an AI assistant helping creators understand fan questions quickly.

Fan's question:
{text}

Please provide:
1. A concise 1-2 sentence summary of the fan's main concern
2. The emotional sentiment (choose one: anxious, excited, confused, neutral, grateful, frustrated)
3. The stakes level (choose one: high, medium, low)
4. 3-5 key points the creator should address

Respond in JSON format:
{{
    "summary": "...",
    "sentiment": "...",
    "stakes": "...",
    "key_points": ["point 1", "point 2", ...]
}}"""

            # Call Azure OpenAI
            response = self.openai_client.chat.completions.create(
                model=settings.azure_openai_deployment_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes fan questions for creators."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"},
                timeout=30.0
            )
            
            # Parse response
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            logger.info(f"Generated AI summary: {result.get('summary', '')[:100]}...")
            
            return {
                'summary': result.get('summary', ''),
                'sentiment': result.get('sentiment', 'neutral'),
                'stakes': result.get('stakes', 'medium'),
                'key_points': result.get('key_points', [])
            }
        except Exception as e:
            logger.error(f"AI summarization failed: {str(e)}")
            return {
                'summary': text[:200] + '...' if len(text) > 200 else text,
                'sentiment': 'neutral',
                'stakes': 'medium',
                'key_points': [],
                'error': str(e)
            }
    
    async def process_booking_question(
        self,
        question_text: Optional[str] = None,
        question_audio_urls: Optional[List[str]] = None,
        question_video_urls: Optional[List[str]] = None,
        question_image_urls: Optional[List[str]] = None,
        creator_language: str = "en"
    ) -> Dict[str, Any]:
        """
        Process all question inputs and generate unified AI summary.
        Supports multiple media files per type.
        
        Args:
            question_text: Text question
            question_audio_urls: List of audio file URLs
            question_video_urls: List of video file URLs
            question_image_urls: List of image file URLs
            creator_language: Creator's preferred language
            
        Returns:
            Dict with AI processing results
        """
        try:
            all_text_content = []
            detected_languages = {}
            transcriptions = {}
            translations = {}
            
            # Process text
            if question_text:
                all_text_content.append(question_text)
                detected_lang = await self.detect_language(question_text)
                detected_languages['text'] = detected_lang
                
                # Translate if not English
                if detected_lang != 'en':
                    translation = await self.translate_text(question_text, target_language='en', source_language=detected_lang)
                    translations['text_en'] = translation
            
            # Process multiple audio files
            if question_audio_urls:
                for idx, audio_url in enumerate(question_audio_urls):
                    audio_result = await self.transcribe_audio_from_url(audio_url)
                    transcriptions[f'audio_{idx}'] = audio_result['transcription']
                    detected_languages[f'audio_{idx}'] = audio_result['language']
                    
                    if audio_result['language'] != 'en' and audio_result['translation']:
                        translations[f'audio_{idx}_en'] = audio_result['translation']
                        all_text_content.append(f"Audio {idx+1}: {audio_result['translation']}")
                    else:
                        all_text_content.append(f"Audio {idx+1}: {audio_result['transcription']}")
            
            # Process multiple video files
            if question_video_urls:
                for idx, video_url in enumerate(question_video_urls):
                    # For now, treat video same as audio (extract audio and transcribe)
                    video_result = await self.transcribe_audio_from_url(video_url)
                    transcriptions[f'video_{idx}'] = video_result['transcription']
                    detected_languages[f'video_{idx}'] = video_result['language']
                    
                    if video_result['language'] != 'en' and video_result['translation']:
                        translations[f'video_{idx}_en'] = video_result['translation']
                        all_text_content.append(f"Video {idx+1}: {video_result['translation']}")
                    else:
                        all_text_content.append(f"Video {idx+1}: {video_result['transcription']}")
            
            # Process multiple images (placeholder for future)
            if question_image_urls:
                for idx, image_url in enumerate(question_image_urls):
                    # Placeholder: Image analysis will be added in Phase 2
                    all_text_content.append(f"Image {idx+1}: [Image analysis placeholder]")
            
            # Combine all content
            combined_text = "\n\n".join(filter(None, all_text_content))
            
            if not combined_text:
                return {
                    'ai_summary': 'No question content provided',
                    'ai_sentiment': 'neutral',
                    'ai_stakes': 'low',
                    'ai_key_points': [],
                    'detected_languages': detected_languages,
                    'transcriptions': transcriptions,
                    'translations': translations,
                    'ai_processing_status': 'completed'
                }
            
            # Generate AI summary
            summary_result = await self.summarize_question(combined_text, creator_language)
            
            return {
                'ai_summary': summary_result['summary'],
                'ai_summary_language': creator_language,
                'ai_sentiment': summary_result['sentiment'],
                'ai_stakes': summary_result['stakes'],
                'ai_key_points': summary_result['key_points'],
                'detected_languages': detected_languages,
                'transcriptions': transcriptions,
                'translations': translations,
                'ai_processing_status': 'completed'
            }
        except Exception as e:
            logger.error(f"Booking question processing failed: {str(e)}")
            return {
                'ai_processing_status': 'failed',
                'ai_processing_error': str(e)
            }


# Global AI service instance (lazy-loaded)
_ai_service_instance: Optional[AIService] = None


def get_ai_service() -> AIService:
    """Get or create the global AI service instance."""
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = AIService()
    return _ai_service_instance
