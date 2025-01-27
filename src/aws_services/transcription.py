import boto3
import json
import requests
from datetime import datetime
from aws_services.bedrock import BedrockService 

class TranscriptionService:
    def __init__(self):
        self.transcribe = boto3.client('transcribe')
        self.comprehend = boto3.client('comprehend')
        self.bedrock_service = BedrockService()
        
    def start_transcription(self, bucket, key):
        """Start a transcription job"""
        try:
            job_name = f"Transcription_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            self.transcribe.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={
                    'MediaFileUri': f"s3://{bucket}/{key}"
                },
                MediaFormat='mp3',
                LanguageCode='en-US',
                Settings={
                    'ShowSpeakerLabels': True,
                    'MaxSpeakerLabels': 2
                }
            )
            
            return job_name
        except Exception as e:
            raise Exception(f"Error starting transcription: {str(e)}")

    def get_transcription_status(self, job_name):
        """Get the status of a transcription job"""
        try:
            response = self.transcribe.get_transcription_job(
                TranscriptionJobName=job_name
            )
            return response['TranscriptionJob']['TranscriptionJobStatus']
        except Exception as e:
            raise Exception(f"Error getting transcription status: {str(e)}")

    def analyze_sentiment(self, text, speakers_text):
        """
        Analyze sentiment of text per speaker using Amazon Comprehend
        
        Parameters:
        text (str): Full transcript text
        speakers_text (dict): Dictionary mapping speaker IDs to their utterances
        
        Returns:
        dict: Sentiment analysis results per speaker and overall summary
        """
        try:
            sentiment_results = {}
            all_sentiments = []  # Track all sentiments for overall calculation
            
            # Analyze each speaker's text separately
            for speaker, utterances in speakers_text.items():
                speaker_sentiments = []
                
                # Split text into chunks if it's too long (Comprehend has a 5000 byte limit)
                max_chunk_size = 4800
                chunks = [utterances[i:i + max_chunk_size] for i in range(0, len(utterances), max_chunk_size)]
                
                # Analyze each chunk
                for chunk in chunks:
                    if chunk.strip():
                        response = self.comprehend.detect_sentiment(
                            Text=chunk,
                            LanguageCode='en'
                        )
                        speaker_sentiments.append(response['Sentiment'])
                        all_sentiments.append(response['Sentiment'])
                
                # Calculate speaker summary
                if speaker_sentiments:
                    sentiment_counts = {
                        'POSITIVE': speaker_sentiments.count('POSITIVE'),
                        'NEGATIVE': speaker_sentiments.count('NEGATIVE'),
                        'NEUTRAL': speaker_sentiments.count('NEUTRAL'),
                        'MIXED': speaker_sentiments.count('MIXED')
                    }
                    
                    # Get the most common sentiment
                    dominant_sentiment = max(sentiment_counts, key=sentiment_counts.get)
                    
                    # Generate detailed tone analysis
                    if speaker == 'spk_1':  # Customer
                        tone_description = self._analyze_customer_tone(utterances, dominant_sentiment)
                    else:  # Bank employee
                        tone_description = self._analyze_employee_tone(dominant_sentiment)
                    
                    sentiment_results[speaker] = {
                        'dominant_sentiment': dominant_sentiment,
                        'sentiment_counts': sentiment_counts,
                        'tone_summary': dominant_sentiment,
                        'tone_description': tone_description
                    }
            
            # Calculate overall sentiment
            if all_sentiments:
                sentiment_counts = {
                    'POSITIVE': all_sentiments.count('POSITIVE'),
                    'NEGATIVE': all_sentiments.count('NEGATIVE'),
                    'NEUTRAL': all_sentiments.count('NEUTRAL'),
                    'MIXED': all_sentiments.count('MIXED')
                }
                overall_sentiment = max(sentiment_counts, key=sentiment_counts.get)
            else:
                overall_sentiment = 'NEUTRAL'
            
            return {
                'per_speaker': sentiment_results,
                'overall_sentiment': overall_sentiment
            }
                
        except Exception as e:
            raise Exception(f"Error analyzing sentiment: {str(e)}")

    def _analyze_customer_tone(self, text, sentiment):
        """Helper function to analyze customer tone in detail"""
        text_lower = text.lower()
        
        # Financial distress indicators
        distress_keywords = ['debt', 'payment', 'difficult', 'problem', 'worried', 
                            'stress', 'cannot', 'unable', 'help', 'late', 'behind']
        
        # Positive indicators
        positive_keywords = ['thank', 'appreciate', 'good', 'great', 'excellent', 
                            'happy', 'satisfied', 'agree', 'perfect']
        
        if sentiment == 'NEGATIVE':
            if any(keyword in text_lower for keyword in distress_keywords):
                return "Customer showed signs of financial distress and expressed concerns about their financial situation"
            return "Customer expressed dissatisfaction during the conversation"
            
        elif sentiment == 'POSITIVE':
            if any(keyword in text_lower for keyword in positive_keywords):
                return "Customer showed appreciation and maintained a positive attitude throughout the discussion"
            return "Customer maintained a constructive and optimistic approach"
            
        elif sentiment == 'MIXED':
            return "Customer showed varying emotions, mixing both concerns and positive engagement"
            
        else:  # NEUTRAL
            return "Customer maintained a professional and balanced tone throughout the conversation"

    def _analyze_employee_tone(self, sentiment):
        """Helper function to analyze bank employee tone"""
        if sentiment == 'POSITIVE':
            return "Demonstrated strong customer service with an encouraging and supportive approach"
        elif sentiment == 'NEGATIVE':
            return "Showed signs of tension in communication style"
        elif sentiment == 'MIXED':
            return "Displayed varying levels of engagement throughout the conversation"
        else:  # NEUTRAL
            return "Maintained a professional and consistent tone throughout the call"

    def get_transcription_result(self, job_name):
        """Get the result of a completed transcription job with speaker-specific text"""
        try:
            response = self.transcribe.get_transcription_job(
                TranscriptionJobName=job_name
            )
            
            if response['TranscriptionJob']['TranscriptionJobStatus'] == 'COMPLETED':
                transcript_uri = response['TranscriptionJob']['Transcript']['TranscriptFileUri']
                
                # Download transcript
                transcript_response = requests.get(transcript_uri)
                transcript_data = transcript_response.json()
                
                # Process the transcript with speaker labels
                transcript_text = ""
                duration = 0
                speakers_text = {'spk_0': '', 'spk_1': ''}  # Initialize speaker-specific text
                
                # Get speaker segments
                items = transcript_data['results'].get('items', [])
                segments = transcript_data['results'].get('speaker_labels', {}).get('segments', [])
                
                # Create a mapping of start time to speaker label
                speaker_map = {}
                for segment in segments:
                    for item in segment['items']:
                        speaker_map[item['start_time']] = segment['speaker_label']
                
                # Build transcript with speaker labels
                current_speaker = None
                current_line = ""
                
                for item in items:
                    if item['type'] == 'pronunciation':
                        speaker = speaker_map.get(item['start_time'])
                        content = item.get('alternatives', [{}])[0].get('content', '')
                        
                        if speaker != current_speaker:
                            if current_line:
                                transcript_text += current_line + "\n"
                            current_speaker = speaker
                            current_line = f"{speaker}: {content}"
                        else:
                            current_line += f" {content}"
                        
                        # Add to speaker-specific text
                        if speaker in speakers_text:
                            speakers_text[speaker] += f" {content}"
                            
                        # Update duration
                        if float(item['end_time']) > duration:
                            duration = float(item['end_time'])
                    
                    elif item['type'] == 'punctuation':
                        current_line += item['alternatives'][0]['content']
                        if current_speaker in speakers_text:
                            speakers_text[current_speaker] += item['alternatives'][0]['content']
                
                if current_line:
                    transcript_text += current_line + "\n"
                
                # Analyze sentiment for each speaker
                sentiment_analysis = self.analyze_sentiment(transcript_text, speakers_text)
            
                # Get detailed LLM sentiment analysis from Bedrock
                # bedrock_service = BedrockService()  # Create instance
                llm_sentiment = self.bedrock_service.analyze_call_sentiment(transcript_text)
                
                # Combine both sentiment analyses
                combined_sentiment = {
                    'comprehend_analysis': sentiment_analysis,
                    'llm_analysis': llm_sentiment
                }
                
                return {
                    'transcript_text': transcript_text,
                    'duration': duration,
                    'speakers': list(set(speaker_map.values())),
                    'speakers_text': speakers_text,
                    'sentiment_analysis': combined_sentiment
                }
                
            return None
                
        except Exception as e:
            raise Exception(f"Error getting transcription result: {str(e)}")