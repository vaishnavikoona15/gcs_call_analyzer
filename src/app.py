import os
import json
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv
from aws_services.s3 import S3Service
from aws_services.transcription import TranscriptionService
from aws_services.bedrock import BedrockService
from aws_services.dynamodb import DynamoDBService
from utils.helpers import (
    format_timestamp,
    format_duration,
    clean_filename,
    extract_customer_info,
    parse_action_items,
    calculate_speaker_ratio,
    extract_topics
)
import time
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize services
s3_service = S3Service()
transcription_service = TranscriptionService()
bedrock_service = BedrockService()
dynamodb_service = DynamoDBService()

def init_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'current_file' not in st.session_state:
        st.session_state.current_file = None

def login_page():
    """Display centered login page"""
    
    # Custom CSS for layout and styling
    st.markdown("""
        <style>
        /* Main heading */
        .page-heading {
            color: #333333;
            font-size: 28px;
            font-weight: bold;
            text-align: center;
            margin-bottom: 30px;
            margin-top: 50px;
        }
        
        /* Center all content */
        .stApp {
            max-width: 800px !important;
            margin: 0 auto !important;
        }
        
        /* Input container styling */
        .stTextInput {
            margin-bottom: 10px !important;
            display: flex !important;
            justify-content: center !important;
        }
        
        /* Base input field styling */
        .stTextInput > div {
            width: 125px !important;
        }
        
        /* Input box styling */
        .stTextInput > div > div > input {
            font-size: 12px !important;
            height: 25px !important;
            width: 125px !important;
            border: 1px solid #ccc !important;
            border-radius: 4px !important;
            background-color: white !important;
            padding: 0 8px !important;
        }
        
        /* Password field specific */
        [type="password"] {
            padding-right: 25px !important;
        }
        
        /* Password eye icon */
        button[aria-label="View password"] {
            position: absolute !important;
            right: -5px !important;
            top: 50% !important;
            transform: translateY(-50%) !important;
            height: 100% !important;
            padding: 0 !important;
            background: transparent !important;
            border: none !important;
            z-index: 2 !important;
        }
        
        /* Label styling */
        .stTextInput label {
            color: #333333 !important;
            font-size: 12px !important;
            margin-bottom: 5px !important;
            text-align: left !important;
            display: block !important;
        }
        
        /* Button container */
        .stButton {
            display: flex !important;
            justify-content: center !important;
        }
        
        /* Button styling */
        .stButton button {
            width: 125px !important;
            background-color: #FFCD00 !important;
            color: #000000 !important;
            border: none !important;
            border-radius: 4px !important;
            padding: 5px 0 !important;
            font-size: 12px !important;
            height: 25px !important;
            cursor: pointer !important;
        }
        
        /* Error message */
        .stAlert {
            width: 125px !important;
            margin: 10px auto !important;
        }
        
        /* Hide Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

    # Initialize session state for authentication
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'logged_in_username' not in st.session_state:
        st.session_state.logged_in_username = None

    # Heading
    st.markdown('<h1 class="page-heading">GCS Call Analyzer</h1>', unsafe_allow_html=True)

    # Login form elements (directly in the page, no columns)
    username = st.text_input("Username", key="username_input")
    password = st.text_input("Password", type="password", key="password_input")
    
    if st.button("Login"):
        if username == "Admin" and password == "admin":
            st.session_state.authenticated = True
            st.session_state.logged_in_username = username
            st.session_state.username = username
            st.rerun()
        else:
            st.error("Invalid credentials")

def process_audio_file(file_key):
    """Process a new audio file"""
    try:
        # Check if analysis already exists
        existing_analysis = dynamodb_service.get_analysis(file_key)
        if existing_analysis:
            st.success("Analysis already exists!")
            return existing_analysis

        # Start transcription
        with st.status("Processing audio file...", expanded=True) as status:
            status.write("Starting transcription...")
            job_name = transcription_service.start_transcription(os.getenv('S3_BUCKET'), file_key)
            
            # Show transcription in progress message once
            status.write("Transcription in progress...")
            
            # Wait for transcription
            while True:
                transcript_status = transcription_service.get_transcription_status(job_name)
                if transcript_status == 'COMPLETED':
                    break
                elif transcript_status == 'FAILED':
                    st.error("Transcription failed")
                    return None
                time.sleep(10)
            
            # Get transcription result
            status.write("Getting transcription results...")
            transcript_result = transcription_service.get_transcription_result(job_name)
            
            # Extract customer information and analyze
            status.write("Analyzing call content...")
            customer_info = extract_customer_info(transcript_result['transcript_text'])
            topics = extract_topics(transcript_result['transcript_text'])
            speaker_ratios = calculate_speaker_ratio(transcript_result.get('segments', []))
            
            # Generate summary using Bedrock
            status.write("Generating summary...")
            summary = bedrock_service.generate_summary(transcript_result['transcript_text'])
            
            # Extract insights
            status.write("Extracting insights...")
            insights = bedrock_service.extract_insights(transcript_result['transcript_text'])
            action_items = parse_action_items(insights)
            
             # Store results
            status.write("Storing results...")
            
            # Ensure sentiment_analysis exists and contains required structure
            sentiment_analysis = transcript_result.get('sentiment_analysis', {})
            if not isinstance(sentiment_analysis, dict):
                sentiment_analysis = {
                    'per_speaker': {},
                    'timeline': [],
                    'overall_sentiment': 'NEUTRAL'
                }
            
            analysis_data = {
                'transcript': transcript_result['transcript_text'],
                'speakers': transcript_result['speakers'],
                'sentiment': sentiment_analysis.get('overall_sentiment', 'NEUTRAL'),  # Store overall sentiment
                'sentiment_analysis': sentiment_analysis,  # Store detailed analysis
                'summary': summary,
                'insights': insights,
                'processed_date': datetime.now().isoformat(),
                'customer_info': customer_info,
                'topics_discussed': topics,
                'speaker_ratios': speaker_ratios,
                'action_items': action_items,
                'duration': transcript_result.get('duration', 0),
                'filename': clean_filename(file_key.split('/')[-1])
            }
            
            # Ensure the sentiment_analysis is JSON serializable
            analysis_data['sentiment_analysis'] = json.loads(
                json.dumps(analysis_data['sentiment_analysis'], default=str)
            )
            
            dynamodb_service.store_analysis(file_key, analysis_data)
            status.update(label="Processing complete!", state="complete", expanded=False)
            
            return analysis_data
            
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return None
            
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return None

# Update the tab structure in display_analysis function:
def display_analysis(file_key):
    """Display analysis results for a file"""
    try:
        # Get analysis from DynamoDB
        analysis = dynamodb_service.get_analysis(file_key)
        
        # Add debugging information
        st.sidebar.expander("Debug Info").write({
            "Has sentiment_analysis": 'sentiment_analysis' in analysis if analysis else False,
            "Sentiment keys": analysis.get('sentiment_analysis', {}).keys() if analysis else None,
            "Sentiment": analysis.get('sentiment', 'Not found') if analysis else None,
            "Raw analysis keys": analysis.keys() if analysis else None
        })
        
        if not analysis:
            analysis = process_audio_file(file_key)
            if not analysis:
                return

        # Common styles for all boxes
        st.markdown("""
            <style>
            .info-box {
                padding: 15px;
                background-color: #f8f9fa;
                border-radius: 5px;
                margin: 10px 0;
            }
            .summary-box {
                padding: 15px;
                background-color: #f0f8ff;
                border-left: 5px solid #FFCD00;
                margin: 10px 0;
                border-radius: 5px;
            }
            .action-item {
                padding: 15px;
                background-color: #ffe5e5;
                border-left: 5px solid #ff0000;
                margin: 10px 0;
                border-radius: 5px;
            }
            .participant-box {
                padding: 10px 15px;
                background-color: #f8f9fa;
                border-radius: 5px;
                margin: 5px 0;
            }
            .sentiment-card {
                background-color: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                padding: 20px;
                margin: 10px 0;
            }
            </style>
        """, unsafe_allow_html=True)
        
        # Updated tab structure with new Sentiment Analysis tab
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["👤 Call Details", "📊 Summary", "💭 Sentiment Analysis", "💡 Actions Required", "📝 Transcript"])
       
        with tab1:
            st.header("Call Details")
            
            # Participants section
            st.subheader("Participants")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f'<div class="participant-box"> {("Bank Employee: spk_0")} </div>', unsafe_allow_html=True)
                # st.markdown("**Bank Employee**: spk_0")
                # st.markdown('</div>', unsafe_allow_html=True)
            with col2:
                st.markdown(f'<div class="participant-box">{("Customer: spk_1")} </div>', unsafe_allow_html=True)
                # st.markdown("**Customer**: spk_1")
                # st.markdown('</div>', unsafe_allow_html=True)
        
            # Call Information
            st.subheader("Call Information")
            file_name = analysis.get('file_key', '').split('/')[-1]
            call_date = format_timestamp(analysis.get('timestamp', ''))
            duration = float(analysis.get('duration', 0))
            
            if file_name:
                st.markdown(f'<div class="info-box">{(f"File Name: {file_name}")} </div>', unsafe_allow_html=True)
                # st.markdown(f"**File Name**: {file_name}")
                # st.markdown('</div>', unsafe_allow_html=True)
            
            if call_date:
                st.markdown(f'<div class="info-box"> {(f"Call Date: {call_date}")} </div>', unsafe_allow_html=True)
                # st.markdown(f"**Call Date**: {call_date}")
                # st.markdown('</div>', unsafe_allow_html=True)
            
            if duration > 0:
                st.markdown(f'<div class="info-box"> {(f"Call Duration: {format_duration(duration)}")} </div>', unsafe_allow_html=True)
                # st.markdown(f"**Call Duration**: {format_duration(duration)}")
                # st.markdown('</div>', unsafe_allow_html=True)
        
        with tab2:
            st.header("Call Summary")
            # Summary points - each in its own box
            if analysis.get('summary'):
                summary_points = analysis['summary'].split('\n')
                for point in summary_points:
                    if point.strip():
                        st.markdown(f'<div class="summary-box">{point.strip()}</div>', 
                                  unsafe_allow_html=True)
            
            # Add metrics
            col1, col2 = st.columns(2)
            with col1:
                duration = float(analysis.get('duration', 0))
                if duration > 0:
                    st.markdown(f'<div class="info-box">Call Duration: {format_duration(duration)}</div>', 
                              unsafe_allow_html=True)
        with tab3:
            st.header("Sentiment Analysis")
            
            if 'sentiment_analysis' in analysis and 'per_speaker' in analysis['sentiment_analysis']:
                # Overall Tone Summary Section
                st.subheader("Speaker Tone Analysis")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(
                        '<div class="sentiment-card">'
                        '<h3 style="color: #003366; margin-bottom: 10px;">Bank Employee Tone</h3>'
                        f'{analysis["sentiment_analysis"]["per_speaker"]["spk_0"]["tone_summary"]}'
                        '</div>',
                        unsafe_allow_html=True
                    )
                
                with col2:
                    st.markdown(
                        '<div class="sentiment-card">'
                        '<h3 style="color: #660033; margin-bottom: 10px;">Customer Tone</h3>'
                        f'{analysis["sentiment_analysis"]["per_speaker"]["spk_1"]["tone_summary"]}'
                        '</div>',
                        unsafe_allow_html=True
                    )
                
                # # Sentiment Timeline Section
                # st.subheader("Sentiment Timeline")
                
                # def sentiment_to_value(sentiment):
                #     sentiment_map = {
                #         'POSITIVE': 1,
                #         'NEUTRAL': 0,
                #         'NEGATIVE': -1,
                #         'MIXED': 0.5
                #     }
                #     return sentiment_map.get(sentiment, 0)
                
                # # Process timeline data
                # timeline = analysis['sentiment_analysis']['timeline']
                
                # # Separate data for each speaker
                # bank_employee_data = [(item['timestamp'], sentiment_to_value(item['sentiment'])) 
                #                    for item in timeline if item['speaker'] == 'spk_0']
                # customer_data = [(item['timestamp'], sentiment_to_value(item['sentiment'])) 
                #                for item in timeline if item['speaker'] == 'spk_1']
                
                # # Create figure
                # fig = go.Figure()
                
                # # Add traces for each speaker
                # if bank_employee_data:
                #     x_bank, y_bank = zip(*bank_employee_data)
                #     fig.add_trace(go.Scatter(
                #         x=x_bank,
                #         y=y_bank,
                #         name='Bank Employee',
                #         line=dict(color='#003366', width=2),
                #         hovertemplate='Time: %{x:.1f}s<br>Sentiment: %{text}<extra></extra>',
                #         text=['Positive' if y==1 else 'Negative' if y==-1 else 'Neutral' if y==0 else 'Mixed' for y in y_bank]
                #     ))
                
                # if customer_data:
                #     x_cust, y_cust = zip(*customer_data)
                #     fig.add_trace(go.Scatter(
                #         x=x_cust,
                #         y=y_cust,
                #         name='Customer',
                #         line=dict(color='#660033', width=2),
                #         hovertemplate='Time: %{x:.1f}s<br>Sentiment: %{text}<extra></extra>',
                #         text=['Positive' if y==1 else 'Negative' if y==-1 else 'Neutral' if y==0 else 'Mixed' for y in y_cust]
                #     ))
                
                # # Update layout
                # fig.update_layout(
                #     title='Sentiment Changes Throughout Call',
                #     xaxis_title='Time (seconds)',
                #     yaxis_title='Sentiment',
                #     yaxis=dict(
                #         ticktext=['Negative', 'Neutral', 'Positive'],
                #         tickvals=[-1, 0, 1],
                #         range=[-1.2, 1.2]
                #     ),
                #     hovermode='x unified',
                #     height=400,
                #     showlegend=True,
                #     legend=dict(
                #         yanchor="top",
                #         y=0.99,
                #         xanchor="left",
                #         x=0.01
                #     ),
                #     plot_bgcolor='rgba(255,255,255,0.9)',
                #     paper_bgcolor='rgba(255,255,255,0)'
                # )
                
                # # Display the plot
                # st.plotly_chart(fig, use_container_width=True)
                
                # Sentiment Distribution Section
                st.subheader("Sentiment Distribution")
                
                # Create distribution charts for each speaker
                bank_sentiment_counts = analysis["sentiment_analysis"]["per_speaker"]["spk_0"]["sentiment_counts"]
                customer_sentiment_counts = analysis["sentiment_analysis"]["per_speaker"]["spk_1"]["sentiment_counts"]
                
                # Create bar charts
                fig_dist = make_subplots(rows=1, cols=2, subplot_titles=(
                    "<b>Bank Employee Sentiment Distribution</b>", 
                    "<b>Customer Sentiment Distribution</b>"
                ))
                
                # Bank Employee distribution
                fig_dist.add_trace(
                    go.Bar(
                        x=list(bank_sentiment_counts.keys()),
                        y=list(bank_sentiment_counts.values()),
                        name="Bank Employee",
                        marker_color='#003366'
                    ),
                    row=1, col=1
                )
                
                # Customer distribution
                fig_dist.add_trace(
                    go.Bar(
                        x=list(customer_sentiment_counts.keys()),
                        y=list(customer_sentiment_counts.values()),
                        name="Customer",
                        marker_color='#660033'
                    ),
                    row=1, col=2
                )
                
                fig_dist.update_layout(
                    height=300,
                    showlegend=False,
                    title_text="Distribution of Sentiments by Speaker",
                    plot_bgcolor='rgba(255,255,255,0.9)',
                    paper_bgcolor='rgba(255,255,255,0)'
                )
                
                # Update y-axis titles
                fig_dist.update_yaxes(title_text="Frequency", row=1, col=1)
                fig_dist.update_yaxes(title_text="Frequency", row=1, col=2)
                
                st.plotly_chart(fig_dist, use_container_width=True)
                
                # Add insights section
                st.subheader("Key Sentiment Insights")
                
                # Calculate some basic insights
                bank_dominant = analysis["sentiment_analysis"]["per_speaker"]["spk_0"]["dominant_sentiment"]
                customer_dominant = analysis["sentiment_analysis"]["per_speaker"]["spk_1"]["dominant_sentiment"]
                
                with st.container():
                    st.markdown(
                        '<div class="sentiment-card">'
                        '<ul>'
                        f'<li>The bank employee maintained primarily a <b>{bank_dominant.lower()}</b> tone throughout the call</li>'
                        f'<li>The customer expressed predominantly <b>{customer_dominant.lower()}</b> sentiment</li>'
                        '</ul>'
                        '</div>',
                        unsafe_allow_html=True
                    )
            else:
                st.error("Sentiment analysis data not available for this call")

        with tab4:
            st.header("Actions Required")
            if analysis.get('insights'):
                actions = [action.strip() for action in analysis['insights'].split('\n') 
                         if action.strip() and not action.strip().startswith('ACTIONS FOR BANK EMPLOYEE')]
                if actions:
                    for action in actions:
                        st.markdown(f'<div class="action-item">{action}</div>', unsafe_allow_html=True)
        
        with tab5:
            st.header("Call Transcript")
            transcript = analysis.get('transcript', '')
            if transcript:
                st.markdown("""
                    <style>
                    .transcript-container {
                        height: 500px;
                        overflow-y: scroll;
                        padding: 20px;
                        border: 1px solid #ddd;
                        border-radius: 5px;
                        background-color: #f8f9fa;
                        margin: 10px 0;
                        line-height: 1.6;
                    }
                    .spk-0 {
                        color: #003366;
                        font-weight: bold;
                        margin-top: 15px;
                    }
                    .spk-1 {
                        color: #660033;
                        font-weight: bold;
                        margin-top: 15px;
                    }
                    </style>
                """, unsafe_allow_html=True)
                
                formatted_lines = []
                for line in transcript.split('\n'):
                    if line.strip():
                        if line.startswith('spk_0:'):
                            formatted_line = f'<div class="spk-0">{line}</div>'
                        elif line.startswith('spk_1:'):
                            formatted_line = f'<div class="spk-1">{line}</div>'
                        else:
                            formatted_line = line
                        formatted_lines.append(formatted_line)
                
                formatted_transcript = '\n'.join(formatted_lines)
                st.markdown(f'<div class="transcript-container">{formatted_transcript}</div>', 
                          unsafe_allow_html=True)
            else:
                st.error("Transcript not available for this call")
                
    except Exception as e:
        st.error(f"Error displaying analysis: {str(e)}")

def main():
    # Initialize session state
    init_session_state()
    
    # Check authentication
    if not st.session_state.authenticated:
        login_page()
        return
    
    # Main application
    st.set_page_config(
        page_title="GCS Call Analyzer",
        page_icon="📞",
        layout="wide"
    )
    
    # Add CBA styling
    st.markdown("""
        <style>
        .main {
            background-color: #FFFFFF;
        }
        .stButton>button {
            background-color: #FFCD00;
            color: #000000;
            font-weight: bold;
        }
        </style>
        """, unsafe_allow_html=True)
    
    # Header with logout
    col1, col2, col3 = st.columns([4,1,1])
    with col1:
        st.title("GCS Call Analyzer")
    with col2:
        st.write(f"Welcome, {st.session_state.username}")
    with col3:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()
    
    # Sidebar for file management
    with st.sidebar:
        st.header("Audio Files")
        
        # File upload
        uploaded_file = st.file_uploader("Upload new audio file", type=['mp3'])
        if uploaded_file:
            with st.spinner("Uploading file..."):
                try:
                    clean_name = clean_filename(uploaded_file.name)
                    file_key = s3_service.upload_file(uploaded_file, clean_name)
                    st.success("File uploaded successfully!")
                    st.session_state.current_file = file_key
                    st.rerun()
                except Exception as e:
                    st.error(f"Error uploading file: {str(e)}")
        
        st.divider()
        
        # File list
        st.subheader("Existing Files")
        try:
            files = s3_service.list_audio_files()
            if not files:
                st.info("No audio files found")
            else:
                for file in files:
                    filename = file['key'].split('/')[-1]
                    # Simple button for each file
                    if st.button(f"📞 {filename}", key=file['key']):
                        st.session_state.current_file = file['key']
                        st.rerun()
                        
        except Exception as e:
            st.error(f"Error listing files: {str(e)}")
        
        # Refresh button
        if st.button("🔄 Refresh List", use_container_width=True):
            st.rerun()
    
    # Main area content
    if st.session_state.current_file:
        # Show breadcrumb
        st.markdown(f"**Current File:** {st.session_state.current_file.split('/')[-1]}")
        st.divider()
        
        # Display analysis in main area
        display_analysis(st.session_state.current_file)
    else:
        # Welcome message when no file is selected
        st.info("👈 Select a file from the sidebar or upload a new one to begin analysis")

# def main():
#     # Initialize session state
#     init_session_state()
    
#     # Check authentication
#     if not st.session_state.authenticated:
#         login_page()
#         return
    
#     # Main application
#     st.set_page_config(
#         page_title="GCS Call Analyzer",
#         page_icon="📞",
#         layout="wide"
#     )
    
#     # Add CBA styling
#     st.markdown("""
#         <style>
#         .main {
#             background-color: #FFFFFF;
#         }
#         .stButton>button {
#             background-color: #FFCD00;
#             color: #000000;
#             font-weight: bold;
#         }
#         .css-1d391kg {
#             background-color: #FFCD00;
#         }
#         .stTabs [data-baseweb="tab-list"] {
#             gap: 1px;
#             background-color: #FFCD00;
#         }
#         .stTabs [data-baseweb="tab"] {
#             background-color: #FFFFFF;
#             border: 1px solid #FFCD00;
#         }
#         </style>
#         """, unsafe_allow_html=True)
    
#     # Header with logout
#     col1, col2, col3 = st.columns([4,1,1])
#     with col1:
#         st.title("GCS Call Analyzer")
#     with col2:
#         st.write(f"Welcome, {st.session_state.username}")
#     with col3:
#         if st.button("🚪 Logout", use_container_width=True):
#             st.session_state.authenticated = False
#             st.rerun()
    
#     # Sidebar for file management
#     with st.sidebar:
#         st.header("Audio Files")
        
#         # File upload
#         uploaded_file = st.file_uploader("Upload new audio file", type=['mp3'])
#         if uploaded_file:
#             with st.spinner("Uploading file..."):
#                 try:
#                     clean_name = clean_filename(uploaded_file.name)
#                     file_key = s3_service.upload_file(uploaded_file, clean_name)
#                     st.success("File uploaded successfully!")
#                     process_audio_file(file_key)
#                 except Exception as e:
#                     st.error(f"Error uploading file: {str(e)}")
        
#         st.divider()
        
#         # File list
#         # In the main() function, update the file listing part:
#         # File list
#         st.subheader("Existing Files")
#         try:
#             files = s3_service.list_audio_files()
#             if not files:
#                 st.info("No audio files found")
#             else:
#                 for file in files:
#                     filename = file['key'].split('/')[-1]
#                     col1, col2 = st.columns([4,1])
#                     with col1:
#                         if st.button(f"📞 {filename}", key=file['key']):
#                             display_analysis(file['key'])
#                     with col2:
#                         st.write(file['last_modified'])  # Using the string format directly
#         except Exception as e:
#             st.error(f"Error listing files: {str(e)}")
        
#         # Refresh button
#         if st.button("🔄 Refresh List", use_container_width=True):
#             st.rerun()
    
#     # Display welcome message if no file is selected
#     if not st.session_state.current_file:
#         st.info("👈 Select a file from the sidebar or upload a new one to begin analysis")

if __name__ == "__main__":
    main()