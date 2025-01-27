import boto3
import os
import json
from datetime import datetime
from decimal import Decimal
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class DynamoDBService:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_DEFAULT_REGION')
        )
        self.table = self.dynamodb.Table(os.getenv('DYNAMODB_TABLE'))

    def _float_to_decimal(self, obj):
        """Convert float values to Decimal for DynamoDB"""
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: self._float_to_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._float_to_decimal(i) for i in obj]
        return obj

    def _validate_transcript(self, transcript_text):
        """Validate and format transcript text"""
        if not transcript_text:
            return ""
            
        formatted_lines = []
        current_speaker = "spk_0"
        
        lines = transcript_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Handle lines that already have speaker labels
            if line.startswith('spk_0:') or line.startswith('spk_1:'):
                formatted_lines.append(line)
                current_speaker = line[:5]
            else:
                # Add speaker label if missing
                formatted_lines.append(f"{current_speaker}: {line}")
                current_speaker = 'spk_1' if current_speaker == 'spk_0' else 'spk_0'
        
        return '\n'.join(formatted_lines)

    def store_analysis(self, file_key, analysis_data):
        """Store analysis results in DynamoDB with enhanced validation"""
        try:
            # Validate and prepare transcript
            if 'transcript_text' in analysis_data:
                analysis_data['transcript_text'] = self._validate_transcript(
                    analysis_data['transcript_text']
                )

            # Ensure required fields exist
            required_fields = {
                'speakers_text': {'spk_0': '', 'spk_1': ''},
                'sentiment_analysis': {
                    'per_speaker': {
                        'spk_0': {'tone_summary': 'Analysis not available'},
                        'spk_1': {'tone_summary': 'Analysis not available'}
                    },
                    'timeline': [],
                    'overall_sentiment': 'NEUTRAL'
                }
            }

            # Add missing required fields
            for field, default_value in required_fields.items():
                if field not in analysis_data or not analysis_data[field]:
                    analysis_data[field] = default_value

            # Convert float values to Decimal
            analysis_data = self._float_to_decimal(analysis_data)

            # Ensure sentiment_analysis is properly formatted
            if 'sentiment_analysis' in analysis_data:
                sentiment_analysis_str = json.dumps(
                    analysis_data['sentiment_analysis'], 
                    default=str
                )
                analysis_data['sentiment_analysis'] = json.loads(
                    sentiment_analysis_str, 
                    parse_float=Decimal
                )

            # Store the item
            item = {
                'file_key': file_key,
                'timestamp': datetime.now().isoformat(),
                **analysis_data
            }
            
            print(f"Storing analysis for file: {file_key}")
            print(f"Transcript length: {len(item.get('transcript_text', ''))}")
            
            response = self.table.put_item(Item=item)
            print(f"Store response: {response}")
            
            return response
            
        except Exception as e:
            print(f"Error storing analysis: {str(e)}")
            raise Exception(f"Error storing analysis: {str(e)}")

    def get_analysis(self, file_key):
        """Get analysis results from DynamoDB with enhanced handling"""
        try:
            response = self.table.get_item(
                Key={'file_key': file_key}
            )
            
            if 'Item' in response:
                item = response['Item']
                
                # Convert Decimal back to float
                def decimal_to_float(obj):
                    if isinstance(obj, Decimal):
                        return float(obj)
                    elif isinstance(obj, dict):
                        return {k: decimal_to_float(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [decimal_to_float(i) for i in obj]
                    return obj
                
                item = decimal_to_float(item)
                
                # Ensure proper sentiment_analysis structure
                if 'sentiment_analysis' in item:
                    try:
                        if isinstance(item['sentiment_analysis'], str):
                            item['sentiment_analysis'] = json.loads(item['sentiment_analysis'])
                    except json.JSONDecodeError:
                        item['sentiment_analysis'] = {
                            'per_speaker': {
                                'spk_0': {'tone_summary': 'Analysis not available'},
                                'spk_1': {'tone_summary': 'Analysis not available'}
                            },
                            'timeline': [],
                            'overall_sentiment': item.get('sentiment', 'NEUTRAL')
                        }
                else:
                    item['sentiment_analysis'] = {
                        'per_speaker': {
                            'spk_0': {'tone_summary': 'Analysis not available'},
                            'spk_1': {'tone_summary': 'Analysis not available'}
                        },
                        'timeline': [],
                        'overall_sentiment': item.get('sentiment', 'NEUTRAL')
                    }
                
                # Validate transcript format
                if 'transcript_text' in item:
                    item['transcript_text'] = self._validate_transcript(item['transcript_text'])
                
                return item
                
            return None
            
        except Exception as e:
            print(f"Error getting analysis: {str(e)}")
            raise Exception(f"Error getting analysis: {str(e)}")

    def list_analyses(self):
        """List all analyses"""
        try:
            response = self.table.scan()
            items = response.get('Items', [])
            
            # Convert Decimal back to float
            def decimal_to_float(obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                elif isinstance(obj, dict):
                    return {k: decimal_to_float(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [decimal_to_float(i) for i in obj]
                return obj
            
            return [decimal_to_float(item) for item in items]
            
        except Exception as e:
            raise Exception(f"Error listing analyses: {str(e)}")