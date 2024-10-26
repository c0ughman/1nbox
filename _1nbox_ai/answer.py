from _1nbox_ai.models import User, Topic  # Adjust the import to your actual module path
from openai import OpenAI
import os
import json

def generate_answer(topic, body, context):
    print("GENERATING ANSWER")
    print(topic)
    print(body)
    print("Context:", context)

    chosen_topic = Topic.objects.get(id=topic)  # Checks for the topic id
    summary = repr(chosen_topic.summaries.first().final_summary)
    cluster_summaries = repr(chosen_topic.summaries.first().cluster_summaries)

    client = OpenAI(api_key=os.environ.get('OPENAI_KEY'))

    # Prepare the context for the prompt
    context_messages = []
    for entry in context:
        context_messages.append({"role": "user", "content": entry["question"]})
        context_messages.append({"role": "assistant", "content": entry["answer"]})

    # Make the OpenAI API request
    response = client.chat.completions.create(
        model="gpt-4o-mini", 
        max_tokens=1000,
        temperature=0.125,
        messages=[
            {"role": "system", "content": "You are a news assistant. Use the provided news of the day to answer the question concisely but completely. If you don't have the answer to the question in the provided information, say you can't answer the question."},
            {"role": "user", "content": f"These are today's news about the topic (The user has no access to these other than what you send): {cluster_summaries}\nThis is what the user received: {summary}"},
            *context_messages,
            {"role": "user", "content": f"Question: {body}\n\nProvide a concise but complete. and refer to one article that has more information on the topic by referring a link, if there is no article that can help, do not provide a link."}
        ]
    )

    # Extract the generated answer
    answer = response.choices[0].message.content.strip()
    return answer
