from google import genai

client = genai.Client()

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Hello Gemini from Codespaces!"
)

print(response.text)
