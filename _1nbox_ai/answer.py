from _1nbox_ai.models import User, Topic  # Adjust the import to your actual module path
from openai import OpenAI
import os

def generate_answer(topic_name, body):
    # Check if from_number contains ":" and extract the part after it if present
    print("GENERATING ANSWER")
    print(topic_name)
    print(body)
    
    topic = Topic.objects.filter(name=topic_name).first()

    summary = repr(topic.summary)
            
    cluster_summaries = repr(topic.cluster_summaries)

    client = OpenAI(api_key=os.environ.get('OPENAI_KEY'))

    # Make the OpenAI API request
    response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1000,
            temperature=0.125,
            messages=[
            {"role": "system", "content": "You are a news assistant. Use the provided information to answer the question concisely. If you don't have the answer to the question in the provided information, say you cant answer the question."},
            {"role": "user", "content": f"Information: {cluster_summaries}\nThis is what the user received: {summary}\nQuestion: {body}\n\nProvide a short and concise answer. and refer to one article that has more information on the topic by refering a link, if there is no article that can help, do not provide a link."}
            ]
        )
    
    # Extract the generated answer
    answer = response.choices[0].message.content.strip()
   
    return answer