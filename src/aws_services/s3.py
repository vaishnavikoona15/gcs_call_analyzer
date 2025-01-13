import boto3
import os

class S3Service:
    def __init__(self):
        self.s3 = boto3.client('s3')
        self.bucket = os.getenv('S3_BUCKET')
        
    def list_audio_files(self):
        """List all audio files in the S3 bucket"""
        try:
            response = self.s3.list_objects_v2(
                Bucket=self.bucket,
                Prefix='gcs-calls/'
            )
            
            files = []
            for item in response.get('Contents', []):
                if item['Key'].endswith('.mp3'):
                    files.append({
                        'key': item['Key'],
                        'size': item['Size'],
                        'last_modified': item['LastModified'].strftime('%Y-%m-%d %H:%M:%S')  # Convert datetime to string
                    })
            
            return files
            
        except Exception as e:
            raise Exception(f"Error listing files: {str(e)}")
            
    def upload_file(self, file_object, filename):
        """Upload a file to S3"""
        try:
            key = f"gcs-calls/{filename}"
            self.s3.upload_fileobj(file_object, self.bucket, key)
            return key
            
        except Exception as e:
            raise Exception(f"Error uploading file: {str(e)}")
            
    def get_file_url(self, key):
        """Get a temporary URL for a file"""
        try:
            url = self.s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket,
                    'Key': key
                },
                ExpiresIn=3600
            )
            return url
            
        except Exception as e:
            raise Exception(f"Error generating URL: {str(e)}")