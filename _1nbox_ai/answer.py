from _1nbox_ai.models import User, Topic  # Adjust the import to your actual module path
from openai import OpenAI
import os

def generate_answer(from_number, body):
    # Check if from_number contains ":" and extract the part after it if present
    if ":" in from_number:
        from_number = from_number.split(":", 1)[1]
    print("GENERATING ANSWER")
    print(from_number)
    print(body)
    
    # Find the user with the matching phone number
    user = User.objects.filter(phone_number=from_number).first()
    if not user:
        return "Error: User not found."

    summaries = []
    general_list = []
    # Iterate through the user's topics
    for topic in user.topics:
        try:
            chosen_topic = Topic.objects.get(name=topic)
            # Add the Topic summary to the general list
            summaries.append(repr(chosen_topic.summary))
            
            # Add each cluster summary to the general list
            general_list.append(repr(chosen_topic.cluster_summaries))
                    
        except Topic.DoesNotExist:
            # Skip to the next topic if the Topic instance does not exist
            continue
    
    client = OpenAI(api_key=os.environ.get('OPENAI_KEY'))

    # Make the OpenAI API request
    response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1000,
            temperature=0.125,
            messages=[
            {"role": "system", "content": "You are a news assistant. Use the provided information to answer the question concisely."},
            {"role": "user", "content": f"Information: {general_list}\nThis is what the user received: {summaries}\nQuestion: {body}\n\nProvide a short and concise answer."}
            ]
        )
    
    # Extract the generated answer
    answer = response.choices[0].message.content.strip()
    
    # Print the generated answer
    print(answer)
    
    return answer
