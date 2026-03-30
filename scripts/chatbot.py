import os
import json
from google import genai
from google.genai import types

client = genai.Client(api_key="AIzaSyDFDI3N5puygt-YZftJl7_eIPv7JwnwoUs")

# Create the model config
generation_config = types.GenerateContentConfig(
  temperature=1,
  top_p=0.95,
  top_k=40,
  max_output_tokens=3000,
  response_mime_type="application/json",
)

system_instruction = "You are an assistant for an imus, philippines accident dashboard that concisely answers questions for users. Anything unrelated to road accidents are unanswerable to you."


def answer_gemini(prompt):
    chat = client.chats.create(
        model="gemini-2.0-flash-exp",
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=generation_config.temperature,
            top_p=generation_config.top_p,
            top_k=generation_config.top_k,
            max_output_tokens=generation_config.max_output_tokens,
            response_mime_type=generation_config.response_mime_type,
        ),
    )
    print('Loading...')
    response = chat.send_message(message=prompt)

    model_response = json.loads(response.text)

    # Extract all values from the dictionary
    text_values = []
    for value in model_response.values():
        # If the value is a list, extend the result
        if isinstance(value, list):
            text_values.extend(value)
        else:
            text_values.append(value)
    
    # Join all text values into a single string (or return the list if preferred)
    return "\n".join(text_values)  # Combine with newlines for readability

# Example usage
#print(answer_gemini('what to do to avoid peak hours'))