import streamlit as st
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
from  groq import Groq
import anthropic
from docx.shared import Inches, Pt, RGBColor
import time
import random
import fitz  
from io import BytesIO

openai.api_key = config('OPENAI_API_KEY')

# Google Dr)ve API setup
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
    print("-----------------------------------",pdf_stream)
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
    print("_________________google drive response",file_id,request)
    print(type(file_id))
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
                # Preserve folder structure inside the zip
                arcname = os.path.relpath(file_path, start=folder_path)
                zipf.write(file_path, arcname=arcname)


# Function to extract headings using regex from a plain string
def extract_headings(paragraphs):
    headings = []
    for para in paragraphs:
        # No need to access para.text, as para is already a string
        if re.match(r'^\*\*.*\*\*$', para.strip()):  # Check if the line is a heading
            headings.append(para.strip().strip('*'))
    return headings

# Function to generate prompt for GPT
# def prompt_generator(docx_content,user_input,full_months):
#     prompt = f"""
# Using the content from the provided document {docx_content}, generate a detailed recruiting message that follows this structure:

# 1. **College Name and Sport**: Clearly mention the college and sport at the top.
# 2. **Time Period "{user_input}"**: Include the time period of the message.
# 3. **TRS Messages**: Provide an overview of the monthly focus topics for each month. Each month should be randomly assigned one of the following topics:
# History and Vision for the Program
# Athletic Facilities
# Life After College
# Academics
# Athletic Atmosphere at the School
# Dorms and Campus Life
# Coaching
# The Freshman Experience
# Location and Area
# Our Team
# For each month, the TRS message should look like this format:

# In September The residence halls and general everyday life on campus for students and athletes will be the focus, based on your team’s feedback at <college1> and others nationwide. This is an important topic for this generation of recruits.
# In October: The athletic atmosphere at <college1> will be the focus, giving recruits an idea of what it’s like to compete and live as a student-athlete at <college1>.
# In November: The athletic facilities at <college1> will be highlighted, emphasizing how your training philosophy prepares athletes to compete at the collegiate level.
# In December: We’ll focus on the <sport> team at <college1>, including insights into the team atmosphere, based on recent findings from your focus group survey.
# *VERY IMPORTANT*: Ensure each section contains more content, with longer sentences under each heading to provide comprehensive information.

# For each month ({full_months[0]}, {full_months[1]}, {full_months[2]}, and {full_months[3]}), follow this structure:

# For [Month]:

# **Main Topic**: The randomly assigned topic for that month.
# **Talking Points (8 elaborated points in question form)**:  The talking points should explore the student's personal preferences, concerns, and expectations. Make sure the questions are open-ended and encourage the student to reflect on their experiences and aspirations. Use a friendly and informal tone, as if a college recruiter or coach is having a one-on-one conversation with the student.
# Make sure that all the points are detailed.
# **Social Media Topic Ideas (8 elaborated points)**: Generate creative social media post ideas and related social activities for engaging college students and athletes. For each social media platform suggestion, follow it up with a related social activity idea. Ensure that the points alternate between social media content and social activity. The platforms should include Instagram, Snapchat, Twitter (X), Facebook, YouTube, LinkedIn, Reddit, and TikTok. The goal is to balance digital engagement with in-person or virtual team-building activities.
# **Text Messaging Talking Points (8 elaborated points in question form)**: Create engaging questions recruiters can send to prospects via text message, tailored to the main topic of the month.
# Ensure each section contains longer sentences with detailed content that can be easily understood by teenagers. Make sure the headings, subheadings, and bullet points remain well-organized in the final output.

# **IMPORTANT** This is an Example Content for reference for Talking Points, Social Media Topic Ideas, and Text Messaging Talking Points:

# Talking Points Example:

# -What have your parents said when it comes to the idea of living on a college campus and being away at college?
# -Aside from <sport>, do you see yourself getting involved in any other aspects of college life? Have you thought about what you’ll be doing in between classes and practice?
# -What kind of atmosphere do you prefer when it comes to dorm life? (Are you a morning person or a night owl?)
# -What are your feelings about living away from home?
# -How do you picture college life?
# -Walk me through some of the things you’re a little nervous about:
# -Are you more of a private person? Shy or outgoing?
# -How do you feel about the idea of having a roommate?
# --Do you have any food allergies (or just preferences)? Are you a picky eater?

# Social Media Topic Ideas Example:

# -One picture a week inside the dorms - rooms, common areas, etc. Our studies show that your prospects need a peek at what they would see on campus as a way to get them to commit to visiting campus.
# -Encourage your team to get together and do a live stream on social media just for your recruits. Do it from where they live, and let them go around and tell recruits what it’s like on campus.
# -Include your team in as much as possible. Let them show off their dorm rooms and have some fun with it!
# -Try to get someone NOT associated with your team or athletic department to write a quick post with their picture, talking about life on campus and their role. Begin introducing your prospects to the people outside of their sport that they need to hear from.
# -Let your team know we’re talking about this and ask them to create some posts about it. Get them directly involved!
# -Twitter: Tweet your Top 20 short comments from your team about the dorm, spread out over the month. Have them tweet it, and then you retweet it.
# -Video focus: Where they’ll eat. Get a video of your team getting food, where they sit and eat, etc. Post that on all social media video outlets.
# -When it comes to the topic of where they live, your own athletes are the best at coming up with topics and visuals - rely on them to come up with ideas surrounding the space where they live.

# -Text Messaging Talking Points Example:

# -What do you think your life is going to look like when you aren’t practicing or in class? Have you thought about that yet?
# -[Coach: If there’s any particularly fun campus event that goes on, feel free to text your recruits about it. Include a picture!]
# -Reply back with your first instinct…now that you know a little bit about us, can you see yourself enjoying life on <college1>’s campus?
# -<Prospect Name>…what’s your favorite post-practice meal? My athletes love <mention food/snacks available on campus>.
# -What are some things you’d like to know about our dorms—the place where you would be living as a student-athlete here? [OR IF ALREADY VISITED: “I’m wondering…what do you remember about our dorms when you visited? Did you like them?”]
# Keep in mind that this is just for reference donot use its content in the content you will be generating.

# Ensure the output aligns with the template format below:

# **<College Name> <Sport>**
# **{user_input}**
# **TRS Messages**
# In {full_months[0]} Brief description about randomly assigned topic 1 in the same format as provide above.
# In {full_months[1]}: Brief description about randomly assigned topic 2 in the same format as provide above.
# In {full_months[2]}: Brief description about randomly assigned topic 3 in the same format as provide above.
# In {full_months[3]}: Brief description about randomly assigned topic 4 in the same format as provide above.
# **For {full_months[0]}: Main Topic**
# **Talking Points**
# **Social Media Topic Ideas**
# **Text Messaging Talking Points**

# **For {full_months[1]}: Main Topic**
# **Talking Points**
# **Social Media Topic Ideas**
# **Text Messaging Talking Points**

# **For {full_months[2]}: Main Topic**
# **Talking Points**
# **Social Media Topic Ideas**
# **Text Messaging Talking Points**

# **For {full_months[3]}: Main Topic**
# **Talking Points**
# **Social Media Topic Ideas**
# **Text Messaging Talking Points**

# Make the text more conversational, and write it in a way that would make a 16 to 18 year old teenager engage with the content and be prompted to respond and interact with the coach who is sending these
# Look for any grammatical errors and correct them.
# VERY IMPORTANT: Place the proper spacing between paragraphs in the revised text
# Keep the same layout format in place when you construct your revised text
# Use the content from the {docx_content} to fill in the placeholders for the talking points, social media ideas, and text messaging points.
# Ensure that the headings, subheadings, and bullet points remain organized in the final output.
# Make sure every college follows the same template structure.
# ONLY include the content necessary for generating the recruiting message. Do not add any extra or irrelevant details.

# """

#     return prompt


def summarize_content(survey):
    """
    Summarizes the provided survey content using OpenAI's GPT-4.

    This function includes a retry mechanism with exponential backoff
    to handle rate limit errors.

    Args:
        survey (str): The survey content to be summarized.

    Returns:
        str: The summarized content generated by GPT-4.
    """
    max_retries = 3  # Maximum number of retries
    retry_delay = 1  # Initial retry delay in seconds

    for attempt in range(max_retries):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",  # Changed to gpt-4
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": f"Summarize the following content: {survey}"}
                ],
                max_tokens=2000,
                temperature=0
            )
            return response.choices[0].message['content']
        except openai.error.RateLimitError as e:
            if attempt < max_retries - 1:  # Retry only if not the last attempt
                print(f"Rate limit error: {e}. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                raise  # Raise the error if all retries failed


# Streamlit UI
st.title("Content Generator")
group = st.text_input("Enter group name:")
model_selection = st.selectbox("Choose Model", ["ChatGPT-4"])
cycle = st.selectbox("Choose Cycle", ["Jan./Feb./Mar./Apr 2024", "May./Jun./July./August 2024", "Sep./Oct./Nov./Dec 2024"])
run_process = st.button("Generate Responses")
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

# Displaying full month names
# print(full_months)

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



#
if run_process and group:
    # List files in the group folder
    response = service.files().list(q=f"name = '{group}' and mimeType = 'application/vnd.google-apps.folder'",
                                    spaces='drive').execute()
    folders = response.get('files', [])

    if not folders:
        st.error("Folder not found.")
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
                st.write(f"Subfolder: {folder['name']}")
                files_in_subfolder = list_files_in_folder(folder['id'])
                pdf_count = 0
                for file in files_in_subfolder:
                    if file['name'].endswith('.docx'):
                        st.write(f"Processing File: {file['name']}")
                        file_stream = stream_file(service, file['id'])
                        docx_content = read_docx(file_stream)
                    
                    elif file['name'].endswith('.pdf'):
                        st.write(f"Processing PDF File: {file['name']}")
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
                    

                    if model_selection == "ChatGPT-4":
                            def intro_content(introd_prompt):
                                        """

                                        """
                                        max_retries = 3  # Maximum number of retries
                                        retry_delay = 1  # Initial retry delay in seconds

                                        for attempt in range(max_retries):
                                            try:
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
                                            except openai.error.RateLimitError as e:
                                                if attempt < max_retries - 1:  # Retry only if not the last attempt
                                                    print(f"Rate limit error: {e}. Retrying in {retry_delay} seconds...")
                                                    time.sleep(retry_delay)
                                                    retry_delay *= 2  # Exponential backoff
                                                else:
                                                    raise  # Raise the error if all retries failed
                            
                            intro = intro_content(intro_prompt)
                            st.write(intro)

                    
                    
                    
                    
                    
                    
                    
                    
                    
                    
                    # # Display the content or use it as needed
                    # if content_1:
                    #     st.write("Content of PDF 1:", content_1)
                    # if content_2:
                    #     st.write("Content of PDF 2:", content_2)
                    # if content_3:
                    #     st.write("Content of PDF 3:", content_3)

                    