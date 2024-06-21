from zipfile import ZipFile
from flask import Flask, render_template, request, redirect, send_file, send_from_directory, url_for
from moviepy.editor import VideoFileClip, AudioFileClip
import os
import shutil
import subprocess
from googletrans import Translator
from gtts import gTTS
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
GENERATED_TEXT_FOLDER = 'generatedText'
TRANSLATED_AUDIO_FOLDER = 'translatedAudio'

ALLOWED_EXTENSIONS = {'mp4', 'avi'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_audio(input_video_path, output_audio_path):
    video_clip = VideoFileClip(input_video_path)
    audio_clip = video_clip.audio
    audio_clip.write_audiofile(output_audio_path)
    audio_clip.close()
    video_clip.close()
    
    # Run whisper after audio extraction
    if run_whisper(output_audio_path):
        print("Whisper executed successfully.")
    else:
        print("Error executing whisper.")

def run_whisper(audio_file):
    command = f'whisper "{audio_file}"'
    try:
        subprocess.run(command, shell=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print("Error executing command:", e)
        return False

def translate_text(text, output_language='hi'):
    translator = Translator()
    translation = translator.translate(text, dest=output_language)
    return translation.text
        
def text_to_speech(text, output_file, language='en', voice='male'):
    tts = gTTS(text=text, lang=language, slow=False)
    if voice == 'female':
        tts.save(output_file)
    else:
        tts.save(output_file) 

def move_text_files_to_generated_text_folder():
    if not os.path.exists(GENERATED_TEXT_FOLDER):
        os.makedirs(GENERATED_TEXT_FOLDER)
    extensions_to_move = ['.txt', '.json', '.vtt', '.srt', '.tsv']
    files_to_move = [f for f in os.listdir('.') if os.path.isfile(f) and os.path.splitext(f)[1] in extensions_to_move]
    for file in files_to_move:
        shutil.move(os.path.join('.', file), os.path.join(GENERATED_TEXT_FOLDER, file))

# Function to merge audio and video files
def merge_audio_video(video_filename, audio_filename, output_filename):
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)
    audio_path = os.path.join(TRANSLATED_AUDIO_FOLDER, audio_filename)
    output_path = os.path.join(TRANSLATED_AUDIO_FOLDER, output_filename)

    video_clip = VideoFileClip(video_path)
    audio_clip = AudioFileClip(audio_path)
    final_clip = video_clip.set_audio(audio_clip)
    final_clip.write_videofile(output_path) 
    video_clip.close()
    audio_clip.close()
    final_clip.close()

# Function to delete all files in a directory
def clear_folder(folder_path):
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"Error deleting {file_path}: {e}") 

# Clearing the folders at the start of the app
clear_folder('generatedText')
clear_folder('translatedAudio')
clear_folder('uploads')

@app.route('/upload', methods=['GET', 'POST'])
def upload_file(): 
    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template('index.html', message='No file part', color='red')
        
        file = request.files['file']
        
        if file.filename == '':
            return render_template('index.html', message='No selected file', color='red')
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            audio_filename = f"{os.path.splitext(filename)[0]}.wav"
            audio_path = os.path.join(app.config['UPLOAD_FOLDER'], audio_filename)
            
            extract_audio(file_path, audio_path)
            
            return render_template('index.html', message='File uploaded successfully!', color='green')
        else:
            return render_template('index.html', message='Invalid file type. Please upload an mp4 or avi file.', color='red')
    return render_template('index.html')

@app.route('/translate', methods=['POST'])
def translate_text_route():
    move_text_files_to_generated_text_folder()

    txt_files = [f for f in os.listdir(GENERATED_TEXT_FOLDER) if f.endswith('.txt')]
    if not txt_files:
        translated_text = ""
    else:
        filepath = os.path.join(GENERATED_TEXT_FOLDER, txt_files[0])
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()

        translated_text = translate_text(text)

    audio_filename = os.path.splitext(txt_files[0])[0] + ".mp3"
    output_file = os.path.join(TRANSLATED_AUDIO_FOLDER, audio_filename)
    
    text_to_speech(translated_text, output_file)
    
    # Get list of video files in upload folder
    video_files = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if f.endswith('.mp4')]
    
    

    # Assuming only one video file present
    if video_files:
        video_filename = video_files[0]
        merge_audio_video(video_filename, audio_filename, 'output.mp4')
        
        output_file_path = os.path.join(TRANSLATED_AUDIO_FOLDER, 'output.mp4')
        file_exists = os.path.isfile(output_file_path)
        return render_template('index.html', file_exists=file_exists, message='Translation and merging successful!', color='green')
    else:
        return render_template('index.html', message='No video file found.', color='red')
    
    
    
@app.route('/download')
def download_file():
    output_file = 'output.mp4'  # Assuming the file is in the 'translatedAudio' folder
    output_file_path = os.path.join(TRANSLATED_AUDIO_FOLDER, output_file)
    return send_file(output_file_path, as_attachment=True)


@app.route('/')
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
