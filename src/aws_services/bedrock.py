import boto3
import json

class BedrockService:
    def __init__(self):
        self.bedrock = boto3.client('bedrock-runtime')
        
    def generate_summary(self, transcript_text):
        """Generate a summary of the transcript using Bedrock"""
        try:
            prompt_text = (
                "Human: Analyze this corporate banking call transcript. This is a non-retail customer call handling major business accounts and bad debt cases. "
                "List only the following points without any additional text:\n"
                "- Main purpose of call\n"
                "- Reason for payment default\n"
                "- Financial amounts discussed\n"
                "- Decisions made\n"
                "- Next steps agreed\n\n"
                f"Transcript:\n{transcript_text}\n\n"
                "Assistant: Here are the key points:"
            )
            
            body = {
                "prompt": prompt_text,
                "max_tokens_to_sample": 300,
                "temperature": 0.3,
                "top_p": 0.9
            }
            
            response = self.bedrock.invoke_model(
                modelId='anthropic.claude-v2',
                body=json.dumps(body),
                contentType="application/json"
            )
            
            response_body = json.loads(response.get('body').read())
            return response_body.get('completion', '')
        except Exception as e:
            print(f"Error generating summary: {str(e)}")
            return "An error occurred while generating the summary."
            
    def extract_insights(self, transcript_text):
        """Extract actionable insights from the transcript"""
        try:
            prompt_text = (
                "Human: From this corporate banking call transcript, list only the following without any additional text:\n\n"
                "ACTIONS FOR BANK EMPLOYEE:\n"
                "- List specific tasks the bank employee must complete\n"
                "- Include deadlines if mentioned\n"
                "- Prioritize urgent items\n\n"
                f"Transcript:\n{transcript_text}\n\n"
                "Assistant: ACTIONS FOR BANK EMPLOYEE:"
            )
            
            body = {
                "prompt": prompt_text,
                "max_tokens_to_sample": 400,
                "temperature": 0.3,
                "top_p": 0.9
            }
            
            response = self.bedrock.invoke_model(
                modelId='anthropic.claude-v2',
                body=json.dumps(body),
                contentType="application/json"
            )
            
            response_body = json.loads(response.get('body').read())
            return response_body.get('completion', '')
            
        except Exception as e:
            raise Exception(f"Error extracting insights: {str(e)}")

    def analyze_call_sentiment(self, transcript_text):
        """Generate detailed sentiment analysis using Claude"""
        try:
            prompt_text = (
                "Human: Analyze this corporate banking call transcript and provide sentiment analysis in this exact format:\n\n"
                "CUSTOMER_INITIAL_TONE: [1 sentence about how customer started the conversation]\n"
                "CUSTOMER_MIDDLE_TONE: [1 sentence about customer's reaction when discussing financial matters]\n"
                "CUSTOMER_FINAL_TONE: [1 sentence about how customer ended the call]\n"
                "EMPLOYEE_OVERALL_TONE: [1 sentence summarizing the employee's tone throughout the call]\n\n"
                f"Transcript:\n{transcript_text}\n\n"
                "Assistant: Here's the sentiment analysis:"
            )
            
            body = {
                "prompt": prompt_text,
                "max_tokens_to_sample": 500,
                "temperature": 0.3,
                "top_p": 0.9
            }
            
            response = self.bedrock.invoke_model(
                modelId='anthropic.claude-v2',
                body=json.dumps(body),
                contentType="application/json"
            )
            
            response_body = json.loads(response.get('body').read())
            response_text = response_body.get('completion', '')
            
            # Parse the response into a structured format
            sentiment_data = {}
            for line in response_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    sentiment_data[key.strip()] = value.strip()
            
            return sentiment_data
                
        except Exception as e:
            print(f"Error analyzing call sentiment: {str(e)}")
            return None