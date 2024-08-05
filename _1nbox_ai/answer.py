from models import User, Topic

def generate_answer(from_number, body):
    # Check if from_number contains ":" and extract the part after it if present
    if ":" in from_number:
        from_number = from_number.split(":", 1)[1]

    # Find the user with the matching phone number
    user = User.query.filter_by(phone_number=from_number).first()
    
    if not user:
        return "Error: User not found."

    general_list = []

    # Iterate through the user's topics
    for topic_name in user.topics:
        # Find the matching Topic instance
        topic = Topic.query.filter_by(name=topic_name).first()
        
        if topic:
            # Add the Topic summary to the general list
            general_list.append(topic.summary)
            
            # Add each cluster summary to the general list
            general_list.extend(topic.cluster_summaries)

    # Print the general list
    print(general_list)

    # You might want to return the list as well, depending on your needs
    return general_list
