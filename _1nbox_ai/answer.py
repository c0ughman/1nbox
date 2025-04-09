from _1nbox_ai.models import User, Topic  # Adjust the import to your actual module path
import os
import json
from google import generativeai as genai

def generate_answer(topic, body, context):
    print("GENERATING ANSWER")
    print(topic)
    print(body)
    print("Context:", context)

    # Fetch the topic and related summaries
    chosen_topic = Topic.objects.get(id=topic)
    summary = repr(chosen_topic.summaries.first().final_summary)
    cluster_summaries = repr(chosen_topic.summaries.first().cluster_summaries)

    # Set up Gemini API
    gemini_key = os.environ.get("GEMINI_KEY")
    if not gemini_key:
        raise ValueError("Gemini API key not found in environment variables.")

    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    # Construct context for prompt
    context_text = ""
    for entry in context:
        context_text += f"Q: {entry['question']}\nA: {entry['answer']}\n\n"

    # Construct prompt
    prompt = (
        "You are a news assistant. Use the provided news of the day to answer the user's question clearly and completely.\n"
        "If the question cannot be answered using the information provided, say so honestly.\n\n"
        f"Cluster Summaries:\n{cluster_summaries}\n\n"
        f"Summary Sent to User:\n{summary}\n\n"
        f"Past QA Context:\n{context_text}\n"
        f"User's Question:\n{body}\n\n"
        "Respond with a short, factual answer. If possible, include a relevant article URL from the data above. "
        "If no article supports your answer, just answer without a link."
    )

    # Call Gemini
    response = model.generate_content(prompt)
    answer = response.text.strip()
    return answer

