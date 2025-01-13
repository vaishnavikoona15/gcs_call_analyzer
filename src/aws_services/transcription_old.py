import boto3
import json
import requests
from datetime import datetime

class TranscriptionService:
    def __init__(self):
        self.transcribe = boto3.client('transcribe')
        self.comprehend = boto3.client('comprehend')
        
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

    def get_transcription_result(self, job_name):
        """Get the result of a completed transcription job"""
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
                            
                        # Update duration
                        if float(item['end_time']) > duration:
                            duration = float(item['end_time'])
                    
                    elif item['type'] == 'punctuation':
                        current_line += item['alternatives'][0]['content']
                
                if current_line:
                    transcript_text += current_line + "\n"
                
                return {
                    'transcript_text': transcript_text,
                    'duration': duration,
                    'speakers': list(set(speaker_map.values()))
                }
            
            return None
            
        except Exception as e:
            raise Exception(f"Error getting transcription result: {str(e)}")

    def analyze_sentiment(self, text):
        """Analyze sentiment of text using Amazon Comprehend"""
        try:
            # Split text into chunks if it's too long (Comprehend has a 5000 byte limit)
            max_chunk_size = 4800  # Leaving some buffer
            chunks = [text[i:i + max_chunk_size] for i in range(0, len(text), max_chunk_size)]
            
            # Analyze each chunk
            sentiments = []
            for chunk in chunks:
                if chunk.strip():  # Only analyze non-empty chunks
                    response = self.comprehend.detect_sentiment(
                        Text=chunk,
                        LanguageCode='en'
                    )
                    sentiments.append(response['Sentiment'])
            
            # Determine overall sentiment
            if not sentiments:
                return 'NEUTRAL'
                
            # Count sentiments
            sentiment_counts = {
                'POSITIVE': sentiments.count('POSITIVE'),
                'NEGATIVE': sentiments.count('NEGATIVE'),
                'NEUTRAL': sentiments.count('NEUTRAL'),
                'MIXED': sentiments.count('MIXED')
            }
            
            # Return the most common sentiment
            return max(sentiment_counts, key=sentiment_counts.get)
            
        except Exception as e:
            raise Exception(f"Error analyzing sentiment: {str(e)}")