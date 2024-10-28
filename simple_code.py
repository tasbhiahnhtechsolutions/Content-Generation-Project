import docx
from docx import Document
from PyPDF2 import PdfReader
import io
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from Google import Create_Service
import openai
import os
import re
from decouple import config
import zipfile
from groq import Groq
import anthropic
from docx.shared import Inches, Pt, RGBColor
import time
import random
import fitz  
from io import BytesIO

openai.api_key = config('OPENAI_API_KEY')

# Google Drive API setup
CLIENT_SECRET_FILE = 'client_secret.json'
API_NAME = 'drive'
API_VERSION = 'v3'
SCOPES = ['https://www.googleapis.com/auth/drive']
service = Create_Service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPES)

# Function to list files in folder
def list_files_in_folder(folder_id):
    results = service.files().list(
        q=f"'{folder_id}' in parents",
        spaces='drive',
        fields='files(id, name, mimeType)').execute()
    return results.get('files', [])

# Function to read .docx files
def read_docx(file_stream):
    document = Document(file_stream)
    content = []
    for paragraph in document.paragraphs:
        content.append(paragraph.text)
    return '\n'.join(content)

def read_pdf(pdf_stream):
    pdf_reader = PdfReader(pdf_stream)
    raw_text = ''
    for page in pdf_reader.pages:
        text = page.extract_text()
        if text:
            raw_text += text
    return raw_text

# Function to stream file content from Google Drive
def stream_file(service, file_id):
    request = service.files().get_media(fileId=file_id)
    file_stream = io.BytesIO()
    downloader = MediaIoBaseDownload(file_stream, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    file_stream.seek(0)
    return file_stream

# Function to create a folder in Google Drive
def create_drive_folder(service, folder_name, parent_folder_id=None):
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    if parent_folder_id:
        file_metadata['parents'] = [parent_folder_id]
    
    folder = service.files().create(body=file_metadata, fields='id').execute()
    return folder['id']

# Function to upload a file to a specific folder in Google Drive
def upload_to_drive(service, file_name, file_path, folder_id):
    file_metadata = {
        'name': file_name,
        'parents': [folder_id]
    }
    media = MediaFileUpload(file_path, mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file['id']

def zip_folder(folder_path, output_path):
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, start=folder_path)
                zipf.write(file_path, arcname=arcname)

# Function to extract headings using regex from a plain string
def extract_headings(paragraphs):
    headings = []
    for para in paragraphs:
        if re.match(r'^\*\*.*\*\*$', para.strip()):
            headings.append(para.strip().strip('*'))
    return headings

# Function to generate prompt for GPT
# Uncomment and adjust this function if needed for generating prompts

# def prompt_generator(docx_content,user_input,full_months):
#     prompt = f"""..."""  # Adjust content as needed
#     return prompt

def summarize_content(survey):
    max_retries = 3  # Maximum number of retries
    backoff_factor = 1  # Initial backoff factor in seconds

    for attempt in range(max_retries):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": survey}
                    ],
                max_tokens= 1000
            )

            return response.choices[0].message['content']
        except openai.error.RateLimitError:
            if attempt < max_retries - 1:
                time.sleep(backoff_factor * (2 ** attempt))  # Exponential backoff
            else:
                raise

def intro_prompt(docx_content):
    introd_prompt = f"""
    Using the content from the provided document {docx_content}, generate a detailed recruiting message that follows this structure and recruiting message should be templete guide to the recruiters:

            1. **College Name and Sport**: Clearly mention the college and sport at the top.
            2. **Time Period "{user_input}"**: Include the time period of the message.
            3. **TRS Messages**: Provide an overview of the monthly focus topics for each month. Each month should be randomly assigned one of the following topics:
            - {selected_topics[0]}
            - {selected_topics[1]}
            - {selected_topics[2]}
            - {selected_topics[3]}

            For each month, the TRS message should look like this format:
            "In [Month]: The [topic] at [college] will be our focus, [brief description of why this topic matters to recruits]. This aligns with recent feedback from student-athletes at [college] and nationwide research on recruitment preferences."

            TRS message Example:
            In September: The residence halls and general everyday life on campus for students and athletes will be the focus, based on your team’s feedback at <college1> and others nationwide. This is an important topic for this generation of recruits.
            In October: The athletic atmosphere at <college1> will be the focus, giving recruits an idea of what it’s like to compete and live as a student-athlete at <college1>.
            In November: The athletic facilities at <college1> will be highlighted, emphasizing how your training philosophy prepares athletes to compete at the collegiate level.
            In December: We’ll focus on the <sport> team at <college1>, including insights into the team atmosphere, based on recent findings from your focus group survey.
            *VERY IMPORTANT*: Ensure each section contains more content, with longer sentences under each heading to provide comprehensive information.

            output structure:

            **<College Name> <Sport>**
            **{user_input}**
            **TRS Messages**
            In {full_months[0]}: Brief description about the topic {selected_topics[0]}.
            In {full_months[1]}: Brief description about the topic {selected_topics[1]}.
            In {full_months[2]}: Brief description about the topic {selected_topics[2]}.
            In {full_months[3]}: Brief description about the topic {selected_topics[3]}.

            NOTE: only retrun the output structure not other content

    """
    return introd_prompt

group = 'Group A'
# model_selection = input("Choose Model:\n 1. ChatGPT-4\n 2. LLaMA3\n, 3. Sonnet\n")
cycle = input("Choose Cycle:\n 1. Jan./Feb./Mar./Apr 2024\n 2. May./Jun./Jul./Aug 2024\n 3. Sep./Oct./Nov./Dec 2024")

import re


user_input = cycle


# Mapping abbreviated months to full names
month_map = {
    "Jan": "January", "Feb": "February", "Mar": "March", "Apr": "April",
    "May": "May", "Jun": "June", "Jul": "July", "Aug": "August",
    "Sept": "September", "Oct": "October", "Nov": "November", "Dec": "December"
}

# Extracting abbreviated month names
abbreviations = re.findall(r'[A-Za-z]+', user_input)

# Standardizing abbreviations to match the dictionary keys (converting to title case)
full_months = [month_map.get(month.title(), month) for month in abbreviations]

import random

topics = [
    "History and Vision for the Program",
    "Athletic Facilities",
    "Life After College",
    "Academics",
    "Athletic Atmosphere at the School",
    "Dorms and Campus Life",
    "Coaching",
    "The Freshman Experience",
    "Location and Area",
    "Our Team"
]

# Select 4 unique topics and store them in a list
selected_topics = random.sample(topics, 4)

# Display the list
print("Selected topics:", selected_topics)

# Displaying full month names
# print(full_months)
# List files in the group folder
response = service.files().list(q=f"name = '{group}' and mimeType = 'application/vnd.google-apps.folder'",
                                spaces='drive').execute()
folders = response.get('files', [])

if not folders:
    print("Folder not found.")
else:
    folder_id = folders[0]['id']
    response_folder = os.path.join(f'{group}_responses', group)  # Create Group A folder inside responses
    if not os.path.exists(response_folder):
        os.makedirs(response_folder)

    # Create a new folder 'Group A responses' in Google Drive
    responses_folder_id = create_drive_folder(service, 'Group A responses')

    pdf_contents = []
    pdf_summaries = []
    subfolders = list_files_in_folder(folder_id)
    for folder in subfolders:
        if folder['mimeType'] == 'application/vnd.google-apps.folder':
            print(f"Subfolder: {folder['name']}")
            files_in_subfolder = list_files_in_folder(folder['id'])
            pdf_count = 0
            for file in files_in_subfolder:
                if file['name'].endswith('.docx'):
                    print(f"Processing File: {file['name']}")
                    file_stream = stream_file(service, file['id'])
                    docx_content = read_docx(file_stream)
                
                elif file['name'].endswith('.pdf'):
                    print(f"Processing PDF File: {file['name']}")
                    pdf_contents = []
                    # Displaying first 100 characters of each PDF content
                    pdf_stream = stream_file(service, file['id'])
                    pdf_content = read_pdf(pdf_stream)
                    pdf_contents.append(pdf_content)
                    summarized_content = summarize_content(pdf_content)
                    pdf_summaries.append(summarized_content)

                # Now you can use pdf_contents[0], pdf_contents[1], and pdf_contents[2] to access each file's content
                summary_1 = pdf_summaries[0] if len(pdf_summaries) > 0 else None
                summary_2 = pdf_summaries[1] if len(pdf_summaries) > 1 else None
                summary_3 = pdf_summaries[2] if len(pdf_summaries) > 2 else None
                

                
def intro_content(introd_prompt):
        print(introd_prompt)
        response = openai.ChatCompletion.create(
                    model="gpt-4o",  # Changed to gpt-4
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": introd_prompt}
                    ],
                    max_tokens=300,
                    temperature=0
                )
        return response.choices[0].message['content']
        
intro = intro_content(intro_prompt)
print(intro)