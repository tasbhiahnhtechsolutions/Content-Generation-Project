from PyPDF2 import PdfReader
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from Google import Create_Service
import io

# Google Dr)ve API setup
CLIENT_SECRET_FILE = 'client_secret.json'
API_NAME = 'drive'
API_VERSION = 'v3'
SCOPES = ['https://www.googleapis.com/auth/drive']
service = Create_Service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPES)




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
    file_stream = io.BytesIO()
    downloader = MediaIoBaseDownload(file_stream, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    file_stream.seek(0)
    return file_stream


s = stream_file(service,"1Blf_sZD_IF2KVySyKZU3XyV5w_QYcETx")
p = read_pdf(s)
print(p)