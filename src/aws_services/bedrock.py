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
            # Handle any exceptions that occur during the request or processing
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