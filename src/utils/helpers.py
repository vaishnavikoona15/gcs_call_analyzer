import datetime
import re

def format_timestamp(timestamp):
    """Convert timestamp to human-readable format"""
    if isinstance(timestamp, str):
        # If it's already a formatted string, return it
        if ' ' in timestamp:  # Check if it's already in datetime format
            return timestamp
        # If it's a string of a float/int, convert it
        try:
            timestamp = float(timestamp)
        except ValueError:
            return timestamp
    
    try:
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except:
        return str(timestamp)

def format_duration(seconds):
    """Convert duration in seconds to MM:SS format"""
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes:02d}:{remaining_seconds:02d}"

def clean_filename(filename):
    """Clean filename for safe storage"""
    # Remove invalid characters
    cleaned = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace spaces with underscores
    cleaned = cleaned.replace(' ', '_')
    return cleaned

def extract_customer_info(transcript_text):
    """Extract customer information from transcript"""
    customer_info = {
        'verification_complete': False,
        'customer_name': None,
        'account_mentioned': False
    }
    
    # Check for verification completion
    verification_phrases = [
        "verification complete",
        "verified successfully",
        "identity confirmed"
    ]
    for phrase in verification_phrases:
        if phrase in transcript_text.lower():
            customer_info['verification_complete'] = True
            break
    
    # Try to extract customer name (basic implementation)
    name_match = re.search(r'name is ([A-Za-z\s]+)', transcript_text)
    if name_match:
        customer_info['customer_name'] = name_match.group(1).strip()
    
    # Check if account numbers are mentioned
    if re.search(r'account.*?number|account.*?#', transcript_text.lower()):
        customer_info['account_mentioned'] = True
    
    return customer_info

def parse_action_items(insights_text):
    """Extract action items from insights text"""
    action_items = []
    
    # Look for phrases that typically indicate action items
    action_patterns = [
        r'need[s]? to',
        r'should',
        r'must',
        r'required to',
        r'action item[s]?:',
        r'follow[- ]up[s]?:',
        r'next step[s]?:'
    ]
    
    # Split text into sentences
    sentences = insights_text.split('.')
    
    for sentence in sentences:
        for pattern in action_patterns:
            if re.search(pattern, sentence.lower()):
                # Clean up the action item text
                action_item = sentence.strip()
                if action_item and action_item not in action_items:
                    action_items.append(action_item)
                break
    
    return action_items

def calculate_speaker_ratio(transcript_segments):
    """Calculate the speaking ratio between participants"""
    speaker_durations = {}
    
    for segment in transcript_segments:
        speaker = segment.get('speaker', 'Unknown')
        duration = segment.get('end_time', 0) - segment.get('start_time', 0)
        
        speaker_durations[speaker] = speaker_durations.get(speaker, 0) + duration
    
    total_duration = sum(speaker_durations.values())
    
    # Convert to percentages
    speaker_percentages = {
        speaker: (duration / total_duration) * 100 
        for speaker, duration in speaker_durations.items()
    }
    
    return speaker_percentages

def extract_topics(transcript_text):
    """Extract main topics discussed in the call"""
    # This is a simplified implementation
    # In a real application, you might want to use more sophisticated NLP
    common_topics = [
        'payment',
        'account',
        'balance',
        'transfer',
        'loan',
        'complaint',
        'issue',
        'support',
        'help',
        'problem'
    ]
    
    found_topics = set()
    for topic in common_topics:
        if topic in transcript_text.lower():
            found_topics.add(topic)
    
    return list(found_topics)

def format_currency(amount):
    """Format amount as currency"""
    try:
        return f"${float(amount):,.2f}"
    except (ValueError, TypeError):
        return "N/A"