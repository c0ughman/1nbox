from *1nbox*ai.models import User, Topic  # Adjust the import to your actual module path
from openai import OpenAI
import os
import json

def generate_answer(topic, body, context):
    print("GENERATING ANSWER")
    print(topic)
    print(body)
    print("Context:", context)

    chosen_topic = Topic.objects.get(name=topic)  # Assuming you have a Topic model
    summary = repr(chosen_topic.summary)
    cluster_summaries = repr(chosen_topic.cluster_summaries)

    client = OpenAI(api_key=os.environ.get('OPENAI_KEY'))

    # Prepare the context for the prompt
    context_messages = []
    for entry in context:
        context_messages.append({"role": "user", "content": entry["question"]})
        context_messages.append({"role": "assistant", "content": entry["answer"]})

    # Make the OpenAI API request
    response = client.chat.completions.create(
        model="gpt-4",  # Make sure to use a valid model name
        max_tokens=1000,
        temperature=0.125,
        messages=[
            {"role": "system", "content": "You are a news assistant. Use the provided information to answer the question concisely. If you don't have the answer to the question in the provided information, say you can't answer the question."},
            {"role": "user", "content": f"Information: {cluster_summaries}\nThis is what the user received: {summary}"},
            *context_messages,
            {"role": "user", "content": f"Question: {body}\n\nProvide a short and concise answer. and refer to one article that has more information on the topic by referring a link, if there is no article that can help, do not provide a link."}
        ]
    )

    # Extract the generated answer
    answer = response.choices[0].message.content.strip()
    return answer