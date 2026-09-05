from transformers import pipeline

# Load the ready-to-use audio emotion model
audio_pipe = pipeline("audio-classification", model="r-f/wav2vec-english-speech-emotion-recognition")

# Just pass your extracted audio file
result = audio_pipe("extracted_audio.wav")
print(result)